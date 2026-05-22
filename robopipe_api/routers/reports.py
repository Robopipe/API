import csv
import io
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Path as PathParam,
    status,
)
from fastapi.responses import FileResponse

from ..dashboard.reports_store import ReportsStore, reports_store_factory
from ..models.dashboard.report import (
    CreateReportRequest,
    DashboardReportSummary,
)
from ..paths import get_data_dir

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dashboard/{dashboard_id}/report",
    tags=["dashboard-reports"],
)

DashboardId = Annotated[int, PathParam(ge=1)]
ReportsStoreDep = Annotated[ReportsStore, Depends(reports_store_factory)]

CSV_HEADER = [
    "Session ID",
    "Session Start",
    "Session End",
    "Timestamp",
    "Test Case",
    "Passed",
    "Defects",
    "Picture",
]


def _format_defect(violated: dict) -> str:
    display = violated["display_id"] if violated["display_id"] is not None else "-"
    parent = (
        violated["parent_display_id"]
        if violated["parent_display_id"] is not None
        else "-"
    )
    return f"{violated['limit_name']} ({display}, {parent})"


def _format_defects_cell(violated_limits: list[dict]) -> str:
    return "; ".join(_format_defect(v) for v in violated_limits)


def _to_utc(dt: datetime) -> datetime:
    """Normalize a datetime to tz-aware UTC.

    Naive values are treated as UTC, matching `_to_sqlite_timestamp` in
    reports_store.py, so endpoint validation and DB filtering agree.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _summary_from_row(row: dict) -> DashboardReportSummary:
    return DashboardReportSummary(
        id=row["id"],
        dashboard_id=row["dashboard_config_id"],
        created_at=row["created_at"],
        filter_start=row["filter_start"],
        filter_end=row["filter_end"],
        status=row["status"],
        error=row["error"],
    )


def _generate_report(report_id: int, dashboard_config_id: int) -> None:
    """Background worker: build the ZIP and update the report row.

    Runs in a threadpool via FastAPI's BackgroundTasks. All IO is blocking
    on purpose — SQLite + zipfile have no async equivalents and the
    threadpool already isolates us from the event loop.
    """
    store = reports_store_factory()
    report = store.get_report(report_id)
    if report is None:
        return

    filter_start = report["filter_start"]
    filter_end = report["filter_end"]

    tmp_path: Path | None = None
    try:
        store.mark_running(report_id)

        rows = store.query_rows(dashboard_config_id, filter_start, filter_end)

        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(CSV_HEADER)

        picture_paths: set[Path] = set()
        data_dir = get_data_dir()
        for row in rows:
            picture_url = row["picture_url"]
            picture_cell = ""
            if picture_url:
                src = data_dir / picture_url
                if src.exists():
                    picture_paths.add(src)
                    picture_cell = f"pictures/{src.name}"
                else:
                    logger.warning(
                        "Report %s: picture %s missing on disk, skipping",
                        report_id,
                        src,
                    )
            writer.writerow(
                [
                    row["session_id"],
                    row["session_start"],
                    row["session_end"],
                    row["event_timestamp"] or "",
                    row["test_case_name"] or "",
                    "True" if row["passed"] else "False",
                    _format_defects_cell(row["violated_limits"]),
                    picture_cell,
                ]
            )

        store.reports_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir = store.reports_dir / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"{uuid.uuid4().hex}.zip"

        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("report.csv", csv_buffer.getvalue())
            for src in picture_paths:
                zf.write(src, arcname=f"pictures/{src.name}")

        final_path = store.reports_dir / f"{report_id}.zip"
        tmp_path.replace(final_path)
        tmp_path = None

        store.mark_completed(report_id, str(final_path))
    except Exception as exc:
        logger.exception("Report %s generation failed", report_id)
        try:
            store.mark_failed(report_id, str(exc))
        except Exception:
            logger.exception("Failed to mark report %s as failed", report_id)
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                logger.exception("Failed to clean up temp report %s", tmp_path)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_report(
    dashboard_id: DashboardId,
    background_tasks: BackgroundTasks,
    store: ReportsStoreDep,
    body: Annotated[CreateReportRequest | None, Body()] = None,
) -> DashboardReportSummary:
    filter_start = body.start if body else None
    filter_end = body.end if body else None

    now = datetime.now(timezone.utc)
    if filter_start is not None and _to_utc(filter_start) > now:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start cannot be in the future",
        )
    if filter_end is not None and _to_utc(filter_end) > now:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end cannot be in the future",
        )

    if (
        filter_start is not None
        and filter_end is not None
        and _to_utc(filter_start) > _to_utc(filter_end)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start must be before or equal to end",
        )

    if not store.dashboard_has_sessions_in_range(
        dashboard_id, filter_start, filter_end
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No data found for the selected range",
        )

    report_id = store.create_report(dashboard_id, filter_start, filter_end)

    background_tasks.add_task(_generate_report, report_id, dashboard_id)

    row = store.get_report(report_id)
    return _summary_from_row(row)


@router.get("")
def list_reports(
    dashboard_id: DashboardId,
    store: ReportsStoreDep,
) -> list[DashboardReportSummary]:
    return [_summary_from_row(row) for row in store.list_reports(dashboard_id)]


@router.get("/{report_id}")
def download_report(
    dashboard_id: DashboardId,
    report_id: int,
    store: ReportsStoreDep,
):
    row = store.get_report(report_id)
    if row is None or row["dashboard_config_id"] != dashboard_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )

    if row["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"status": row["status"], "error": row["error"]},
        )

    file_path = Path(row["file_path"]) if row["file_path"] else None
    if file_path is None or not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file missing on disk",
        )

    return FileResponse(
        path=file_path,
        media_type="application/zip",
        filename=f"dashboard-{dashboard_id}-report-{report_id}.zip",
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    dashboard_id: DashboardId,
    report_id: int,
    store: ReportsStoreDep,
):
    row = store.get_report(report_id)
    if row is None or row["dashboard_config_id"] != dashboard_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )

    if row["status"] in ("pending", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete report while status is '{row['status']}'",
        )

    if row["file_path"]:
        file_path = Path(row["file_path"])
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass

    store.delete_report(report_id)
