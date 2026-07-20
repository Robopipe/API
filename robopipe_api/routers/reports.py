import csv
import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Path as PathParam,
    Query,
    status,
)
from fastapi.responses import FileResponse

from ..dashboard.picture_renderer import render_event_picture
from ..dashboard.reports_store import ReportsStore, _format_utc_z, reports_store_factory
from ..models.dashboard.report import (
    CreateReportRequest,
    DashboardReportSummary,
    EventDetail,
    EventListResponse,
    SessionSummary,
)
from ..paths import get_data_dir

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dashboard/{dashboard_id}",
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


def _parse_utc(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _summary_from_row(row: dict) -> DashboardReportSummary:
    return DashboardReportSummary(
        id=row["id"],
        dashboard_id=row["dashboard_config_id"],
        created_at=_parse_utc(row["created_at"]),
        filter_start=_parse_utc(row["filter_start"]),
        filter_end=_parse_utc(row["filter_end"]),
        session_id=row["filter_session_id"],
        event_ids=(
            json.loads(row["filter_event_ids"]) if row["filter_event_ids"] else None
        ),
        status=row["status"],
        error=row["error"],
    )


def _event_payload(row: dict) -> dict:
    """Map a store row onto the API model shape (picture_url → has_picture)."""
    payload = dict(row)
    payload["has_picture"] = payload.pop("picture_url") is not None
    return payload


def _add_event_picture(
    zf: zipfile.ZipFile,
    src: Path,
    event_id: int,
    detections: list[dict],
    src_bytes_cache: dict[Path, bytes],
    written_arcnames: set[str],
    report_id: int,
) -> str:
    """Write one event's picture into the ZIP and return its CSV cell.

    Events with detection rows get a per-event annotated render
    (pictures/event-{id}.jpg). Events without rows — legacy pictures with
    the boxes already burned in — pass through under their source name,
    deduplicated. A failed read or render degrades per event, never fails
    the whole report.
    """
    try:
        if src not in src_bytes_cache:
            src_bytes_cache[src] = src.read_bytes()
        jpeg_bytes = src_bytes_cache[src]
    except OSError:
        logger.exception("Report %s: reading picture %s failed", report_id, src)
        return ""

    if detections:
        try:
            arcname = f"pictures/event-{event_id}.jpg"
            zf.writestr(arcname, render_event_picture(jpeg_bytes, detections))
            return arcname
        except Exception:
            logger.exception(
                "Report %s: rendering picture for event %s failed, "
                "passing the clean picture through",
                report_id,
                event_id,
            )

    arcname = f"pictures/{src.name}"
    if arcname not in written_arcnames:
        written_arcnames.add(arcname)
        zf.writestr(arcname, jpeg_bytes)
    return arcname


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
    session_id = report["filter_session_id"]
    event_ids = (
        json.loads(report["filter_event_ids"]) if report["filter_event_ids"] else None
    )

    tmp_path: Path | None = None
    try:
        store.mark_running(report_id)

        rows = store.query_rows(
            dashboard_config_id, filter_start, filter_end, session_id, event_ids
        )
        detections_by_event = store.get_event_detections(
            [
                row["event_id"]
                for row in rows
                if row["event_id"] is not None and row["picture_url"]
            ]
        )

        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(CSV_HEADER)

        store.reports_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir = store.reports_dir / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"{uuid.uuid4().hex}.zip"

        data_dir = get_data_dir()
        # One clean commit-frame JPEG is shared by every event saved in the
        # same tick, so annotated pictures are rendered and named per event
        # while the source bytes are read once per file.
        src_bytes_cache: dict[Path, bytes] = {}
        written_arcnames: set[str] = set()
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for row in rows:
                picture_url = row["picture_url"]
                picture_cell = ""
                if picture_url:
                    src = data_dir / picture_url
                    if not src.exists():
                        logger.warning(
                            "Report %s: picture %s missing on disk, skipping",
                            report_id,
                            src,
                        )
                    else:
                        picture_cell = _add_event_picture(
                            zf,
                            src,
                            row["event_id"],
                            detections_by_event.get(row["event_id"], []),
                            src_bytes_cache,
                            written_arcnames,
                            report_id,
                        )
                writer.writerow(
                    [
                        row["session_id"],
                        _format_utc_z(row["session_start"]) or "",
                        _format_utc_z(row["session_end"]) or "",
                        _format_utc_z(row["event_timestamp"]) or "",
                        row["test_case_name"] or "",
                        "True" if (len(row["violated_limits"]) <= 0) else "False",
                        _format_defects_cell(row["violated_limits"]),
                        picture_cell,
                    ]
                )
            zf.writestr("report.csv", csv_buffer.getvalue())

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


@router.post("/report", status_code=status.HTTP_202_ACCEPTED)
def create_report(
    dashboard_id: DashboardId,
    background_tasks: BackgroundTasks,
    store: ReportsStoreDep,
    body: Annotated[CreateReportRequest | None, Body()] = None,
) -> DashboardReportSummary:
    filter_start = body.start if body else None
    filter_end = body.end if body else None
    session_id = body.session_id if body else None
    event_ids = body.event_ids if body else None

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

    if not store.dashboard_has_report_data(
        dashboard_id, filter_start, filter_end, session_id, event_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No data found for the selected range",
        )

    report_id = store.create_report(
        dashboard_id, filter_start, filter_end, session_id, event_ids
    )

    background_tasks.add_task(_generate_report, report_id, dashboard_id)

    row = store.get_report(report_id)
    return _summary_from_row(row)


@router.get("/report")
def list_reports(
    dashboard_id: DashboardId,
    store: ReportsStoreDep,
) -> list[DashboardReportSummary]:
    return [_summary_from_row(row) for row in store.list_reports(dashboard_id)]


@router.get("/report/{report_id}")
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


@router.delete("/report/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@router.get("/sessions")
def list_sessions(
    dashboard_id: DashboardId,
    store: ReportsStoreDep,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[SessionSummary]:
    """Run sessions of a dashboard, newest first. Includes the running
    session (end_time null); start/end filter on session start time."""
    return [
        SessionSummary(**row) for row in store.list_sessions(dashboard_id, start, end)
    ]


@router.get("/events")
def list_events(
    dashboard_id: DashboardId,
    store: ReportsStoreDep,
    session_id: Annotated[int | None, Query(ge=1)] = None,
    start: datetime | None = None,
    end: datetime | None = None,
    test_case_id: str | None = None,
    passed: bool | None = None,
    sort_by: Literal["timestamp", "session_start", "test_case_name", "passed"] = (
        "timestamp"
    ),
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventListResponse:
    """Evaluation events of a dashboard, paginated. start/end filter on the
    event timestamp; each item carries its violated limits."""
    total = store.count_events(
        dashboard_id, session_id, start, end, test_case_id, passed
    )
    rows = store.list_events(
        dashboard_id,
        session_id,
        start,
        end,
        test_case_id,
        passed,
        sort_by,
        order,
        limit,
        offset,
    )
    return EventListResponse(
        items=[_event_payload(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_id}")
def get_event(
    dashboard_id: DashboardId,
    event_id: int,
    store: ReportsStoreDep,
) -> EventDetail:
    """One evaluation event with its violated limits and the full
    commit-frame detection set. Pre-migration events have no detection rows;
    their picture carries the boxes burned in instead."""
    row = store.get_event(dashboard_id, event_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )
    return EventDetail(**_event_payload(row))


@router.get(
    "/events/{event_id}/picture",
    response_class=FileResponse,
    responses={
        200: {
            "content": {
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}}
            },
            "description": "Event picture in JPEG format, exactly as stored",
        }
    },
)
def get_event_picture(
    dashboard_id: DashboardId,
    event_id: int,
    store: ReportsStoreDep,
):
    row = store.get_event(dashboard_id, event_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )
    if row["picture_url"] is None:
        raise HTTPException(status_code=404, detail="Picture not found")

    file_path = get_data_dir() / row["picture_url"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Picture file not found")

    return FileResponse(path=file_path, media_type="image/jpeg")
