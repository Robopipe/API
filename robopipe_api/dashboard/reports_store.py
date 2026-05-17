import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from ..paths import get_data_dir


def _to_sqlite_timestamp(dt: datetime | str | None) -> str | None:
    """Format a datetime to match SQLite's CURRENT_TIMESTAMP layout.

    SQLite stores 'YYYY-MM-DD HH:MM:SS' in UTC. Timezone-aware values are
    converted to UTC; naive values are assumed to already be UTC. Strings
    are passed through so values that round-trip from the DB also work.
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class ReportsStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (get_data_dir() / "robopipe.db")
        self.reports_dir = get_data_dir() / "reports"

    def reset_stuck_reports(self) -> None:
        """Mark any pending/running rows as failed.

        Called on startup so a server crash mid-generation doesn't leave
        clients polling forever.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE dashboard_report
                SET status = 'failed', error = 'Interrupted by server restart'
                WHERE status IN ('pending', 'running')
                """
            )

    def dashboard_has_sessions(self, dashboard_config_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM dashboard_run_session WHERE dashboard_config_id = ? LIMIT 1",
                (dashboard_config_id,),
            ).fetchone()
            return row is not None

    def dashboard_has_sessions_in_range(
        self,
        dashboard_config_id: int,
        filter_start: datetime | None,
        filter_end: datetime | None,
    ) -> bool:
        start_str = _to_sqlite_timestamp(filter_start)
        end_str = _to_sqlite_timestamp(filter_end)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM dashboard_run_session s
                WHERE s.dashboard_config_id = ?
                    AND s.end_time IS NOT NULL
                    AND (? IS NULL OR s.start_time >= ?)
                    AND (? IS NULL OR s.start_time <= ?)
                LIMIT 1
                """,
                (
                    dashboard_config_id,
                    start_str,
                    start_str,
                    end_str,
                    end_str,
                ),
            ).fetchone()
            return row is not None

    def create_report(
        self,
        dashboard_config_id: int,
        filter_start: datetime | None,
        filter_end: datetime | None,
    ) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO dashboard_report
                    (dashboard_config_id, filter_start, filter_end, status)
                VALUES (?, ?, ?, 'pending')
                """,
                (
                    dashboard_config_id,
                    _to_sqlite_timestamp(filter_start),
                    _to_sqlite_timestamp(filter_end),
                ),
            )
            return cursor.lastrowid

    def mark_running(self, report_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE dashboard_report SET status = 'running' WHERE id = ?",
                (report_id,),
            )

    def mark_completed(self, report_id: int, file_path: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE dashboard_report SET status = 'completed', file_path = ? WHERE id = ?",
                (file_path, report_id),
            )

    def mark_failed(self, report_id: int, error: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE dashboard_report SET status = 'failed', error = ? WHERE id = ?",
                (error, report_id),
            )

    def get_report(self, report_id: int) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM dashboard_report WHERE id = ?",
                (report_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_reports(self, dashboard_config_id: int) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM dashboard_report
                WHERE dashboard_config_id = ?
                ORDER BY id DESC
                """,
                (dashboard_config_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_report(self, report_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM dashboard_report WHERE id = ?",
                (report_id,),
            )

    def query_rows(
        self,
        dashboard_config_id: int,
        filter_start: datetime | str | None,
        filter_end: datetime | str | None,
    ) -> list[dict]:
        """Build the row-per-event payload for the CSV.

        Returns one dict per evaluation event, plus one dict per session that
        has no events (with event_id/test_case_name/picture_url all None).
        Violated limits are fetched in a single batched query and attached
        to each event row in display order.
        """
        start_str = _to_sqlite_timestamp(filter_start)
        end_str = _to_sqlite_timestamp(filter_end)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            session_event_rows = conn.execute(
                """
                SELECT
                    s.id AS session_id,
                    s.start_time AS session_start,
                    s.end_time AS session_end,
                    e.id AS event_id,
                    e.test_case_name AS test_case_name,
                    e.picture_url AS picture_url
                FROM dashboard_run_session s
                LEFT JOIN dashboard_evaluation_event e
                    ON e.dashboard_run_session_id = s.id
                WHERE s.dashboard_config_id = ?
                    AND s.end_time IS NOT NULL
                    AND (? IS NULL OR s.start_time >= ?)
                    AND (? IS NULL OR s.start_time <= ?)
                ORDER BY s.start_time ASC, s.id ASC, e.id ASC
                """,
                (
                    dashboard_config_id,
                    start_str,
                    start_str,
                    end_str,
                    end_str,
                ),
            ).fetchall()

            event_ids = [row["event_id"] for row in session_event_rows if row["event_id"] is not None]
            violated_by_event: dict[int, list[dict]] = {}
            if event_ids:
                placeholders = ",".join("?" for _ in event_ids)
                limit_rows = conn.execute(
                    f"""
                    SELECT event_id, limit_name, display_id, parent_display_id
                    FROM dashboard_evaluation_event_violated_limit
                    WHERE event_id IN ({placeholders})
                    ORDER BY event_id ASC, id ASC
                    """,
                    event_ids,
                ).fetchall()
                for r in limit_rows:
                    violated_by_event.setdefault(r["event_id"], []).append(
                        {
                            "limit_name": r["limit_name"],
                            "display_id": r["display_id"],
                            "parent_display_id": r["parent_display_id"],
                        }
                    )

        result: list[dict] = []
        for row in session_event_rows:
            event_id = row["event_id"]
            result.append(
                {
                    "session_id": row["session_id"],
                    "session_start": row["session_start"],
                    "session_end": row["session_end"],
                    "event_id": event_id,
                    "test_case_name": row["test_case_name"],
                    "picture_url": row["picture_url"],
                    "violated_limits": violated_by_event.get(event_id, []) if event_id is not None else [],
                }
            )
        return result


@lru_cache(maxsize=1)
def reports_store_factory() -> ReportsStore:
    return ReportsStore()
