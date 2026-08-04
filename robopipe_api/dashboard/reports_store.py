import json
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from ..paths import get_data_dir

# Whitelist mapping of events-list sort keys to SQL columns. User input is
# resolved through this dict and never interpolated into the query.
EVENT_SORT_COLUMNS = {
    "timestamp": "e.timestamp",
    "session_start": "s.start_time",
    "test_case_name": "e.test_case_name",
    "passed": "e.passed",
}


def _format_utc_z(value: datetime | str | None) -> str | None:
    """Format a naive-UTC SQLite string or datetime as ISO 8601 with a Z suffix."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.replace(" ", "T") + "Z" if "T" not in value and not value.endswith("Z") else value
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
            conn.execute("""
                UPDATE dashboard_report
                SET status = 'failed', error = 'Interrupted by server restart'
                WHERE status IN ('pending', 'running')
                """)

    def dashboard_has_sessions(self, dashboard_config_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM dashboard_run_session WHERE dashboard_config_id = ? LIMIT 1",
                (dashboard_config_id,),
            ).fetchone()
            return row is not None

    def dashboard_has_report_data(
        self,
        dashboard_config_id: int,
        filter_start: datetime | None,
        filter_end: datetime | None,
        session_id: int | None = None,
        event_ids: list[int] | None = None,
    ) -> bool:
        """True when the report selection would produce at least one row.

        With event_ids the check requires a matching event; otherwise a
        matching completed session is enough (sessions without events still
        produce CSV rows).
        """
        start_str = _to_sqlite_timestamp(filter_start)
        end_str = _to_sqlite_timestamp(filter_end)
        with sqlite3.connect(self.db_path) as conn:
            if event_ids:
                placeholders = ",".join("?" for _ in event_ids)
                row = conn.execute(
                    f"""
                    SELECT 1
                    FROM dashboard_evaluation_event e
                    JOIN dashboard_run_session s ON s.id = e.dashboard_run_session_id
                    WHERE s.dashboard_config_id = ?
                        AND s.end_time IS NOT NULL
                        AND e.id IN ({placeholders})
                        AND (? IS NULL OR s.id = ?)
                        AND (? IS NULL OR s.start_time >= ?)
                        AND (? IS NULL OR s.start_time <= ?)
                    LIMIT 1
                    """,
                    (
                        dashboard_config_id,
                        *event_ids,
                        session_id,
                        session_id,
                        start_str,
                        start_str,
                        end_str,
                        end_str,
                    ),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM dashboard_run_session s
                    WHERE s.dashboard_config_id = ?
                        AND s.end_time IS NOT NULL
                        AND (? IS NULL OR s.id = ?)
                        AND (? IS NULL OR s.start_time >= ?)
                        AND (? IS NULL OR s.start_time <= ?)
                    LIMIT 1
                    """,
                    (
                        dashboard_config_id,
                        session_id,
                        session_id,
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
        session_id: int | None = None,
        event_ids: list[int] | None = None,
    ) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO dashboard_report
                    (dashboard_config_id, filter_start, filter_end,
                     filter_session_id, filter_event_ids, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
                """,
                (
                    dashboard_config_id,
                    _to_sqlite_timestamp(filter_start),
                    _to_sqlite_timestamp(filter_end),
                    session_id,
                    json.dumps(event_ids) if event_ids else None,
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

    @staticmethod
    def _fetch_violated_limits(
        conn: sqlite3.Connection, event_ids: list[int]
    ) -> dict[int, list[dict]]:
        """Batch-fetch violated limits for a set of events, in display order."""
        violated_by_event: dict[int, list[dict]] = {}
        if not event_ids:
            return violated_by_event
        placeholders = ",".join("?" for _ in event_ids)
        limit_rows = conn.execute(
            f"""
            SELECT event_id, limit_id, limit_name, display_id, parent_display_id
            FROM dashboard_evaluation_event_violated_limit
            WHERE event_id IN ({placeholders})
            ORDER BY event_id ASC, id ASC
            """,
            event_ids,
        ).fetchall()
        for r in limit_rows:
            violated_by_event.setdefault(r["event_id"], []).append(
                {
                    "limit_id": r["limit_id"],
                    "limit_name": r["limit_name"],
                    "display_id": r["display_id"],
                    "parent_display_id": r["parent_display_id"],
                }
            )
        return violated_by_event

    def query_rows(
        self,
        dashboard_config_id: int,
        filter_start: datetime | str | None,
        filter_end: datetime | str | None,
        session_id: int | None = None,
        event_ids: list[int] | None = None,
    ) -> list[dict]:
        """Build the row-per-event payload for the CSV.

        Returns one dict per evaluation event, plus one dict per session that
        has no events (with event_id/test_case_name/picture_url all None).
        With event_ids the join is inner-only: sessions without a selected
        event produce no rows. Violated limits are fetched in a single
        batched query and attached to each event row in display order.
        """
        start_str = _to_sqlite_timestamp(filter_start)
        end_str = _to_sqlite_timestamp(filter_end)

        # Placeholders bind in SQL-text order: the ON-clause event ids come
        # before every WHERE parameter.
        join = "LEFT JOIN"
        event_clause = ""
        params: list = []
        if event_ids:
            join = "JOIN"
            placeholders = ",".join("?" for _ in event_ids)
            event_clause = f"AND e.id IN ({placeholders})"
            params.extend(event_ids)
        params.extend(
            [
                dashboard_config_id,
                session_id,
                session_id,
                start_str,
                start_str,
                end_str,
                end_str,
            ]
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            session_event_rows = conn.execute(
                f"""
                SELECT
                    s.id AS session_id,
                    s.start_time AS session_start,
                    s.end_time AS session_end,
                    s.model_name AS model_name,
                    e.id AS event_id,
                    e.test_case_name AS test_case_name,
                    e.timestamp AS event_timestamp,
                    e.picture_url AS picture_url
                FROM dashboard_run_session s
                {join} dashboard_evaluation_event e
                    ON e.dashboard_run_session_id = s.id
                    {event_clause}
                WHERE s.dashboard_config_id = ?
                    AND s.end_time IS NOT NULL
                    AND (? IS NULL OR s.id = ?)
                    AND (? IS NULL OR s.start_time >= ?)
                    AND (? IS NULL OR s.start_time <= ?)
                ORDER BY s.start_time ASC, s.id ASC, e.id ASC
                """,
                params,
            ).fetchall()

            found_event_ids = [
                row["event_id"]
                for row in session_event_rows
                if row["event_id"] is not None
            ]
            violated_by_event = self._fetch_violated_limits(conn, found_event_ids)

        result: list[dict] = []
        for row in session_event_rows:
            event_id = row["event_id"]
            result.append(
                {
                    "session_id": row["session_id"],
                    "session_start": row["session_start"],
                    "session_end": row["session_end"],
                    "model_name": row["model_name"],
                    "event_id": event_id,
                    "event_timestamp": row["event_timestamp"],
                    "test_case_name": row["test_case_name"],
                    "picture_url": row["picture_url"],
                    "violated_limits": (
                        violated_by_event.get(event_id, [])
                        if event_id is not None
                        else []
                    ),
                }
            )
        return result

    def list_sessions(
        self,
        dashboard_config_id: int,
        filter_start: datetime | None = None,
        filter_end: datetime | None = None,
    ) -> list[dict]:
        """Sessions with event aggregates, newest first.

        Running sessions (end_time NULL) are included so the reports UI can
        browse the run in progress.
        """
        start_str = _to_sqlite_timestamp(filter_start)
        end_str = _to_sqlite_timestamp(filter_end)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    s.id,
                    s.start_time,
                    s.end_time,
                    s.end_reason,
                    COUNT(e.id) AS event_count,
                    COALESCE(SUM(CASE WHEN e.passed = 0 THEN 1 ELSE 0 END), 0)
                        AS failed_count
                FROM dashboard_run_session s
                LEFT JOIN dashboard_evaluation_event e
                    ON e.dashboard_run_session_id = s.id
                WHERE s.dashboard_config_id = ?
                    AND (? IS NULL OR s.start_time >= ?)
                    AND (? IS NULL OR s.start_time <= ?)
                GROUP BY s.id
                ORDER BY s.start_time DESC, s.id DESC
                """,
                (
                    dashboard_config_id,
                    start_str,
                    start_str,
                    end_str,
                    end_str,
                ),
            ).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def _events_filter(
        dashboard_config_id: int,
        session_ids: list[int] | None,
        model_ids: list[int] | None,
        filter_start: datetime | None,
        filter_end: datetime | None,
        test_case_ids: list[str] | None,
        limit_ids: list[str] | None,
        passed: bool | None,
    ) -> tuple[str, list]:
        start_str = _to_sqlite_timestamp(filter_start)
        end_str = _to_sqlite_timestamp(filter_end)
        clauses = ["s.dashboard_config_id = ?"]
        params: list = [dashboard_config_id]
        if session_ids:
            placeholders = ", ".join("?" * len(session_ids))
            clauses.append(f"e.dashboard_run_session_id IN ({placeholders})")
            params.extend(session_ids)
        if model_ids:
            placeholders = ", ".join("?" * len(model_ids))
            clauses.append(f"s.model_id IN ({placeholders})")
            params.extend(model_ids)
        if start_str is not None:
            clauses.append("e.timestamp >= ?")
            params.append(start_str)
        if end_str is not None:
            clauses.append("e.timestamp <= ?")
            params.append(end_str)
        if test_case_ids:
            placeholders = ", ".join("?" * len(test_case_ids))
            clauses.append(f"e.test_case_id IN ({placeholders})")
            params.extend(test_case_ids)
        if limit_ids:
            placeholders = ", ".join("?" * len(limit_ids))
            clauses.append(
                "EXISTS ("
                "SELECT 1 FROM dashboard_evaluation_event_violated_limit vl "
                f"WHERE vl.event_id = e.id AND vl.limit_id IN ({placeholders})"
                ")"
            )
            params.extend(limit_ids)
        if passed is not None:
            clauses.append("e.passed = ?")
            params.append(1 if passed else 0)
        return " AND ".join(clauses), params

    def count_events(
        self,
        dashboard_config_id: int,
        session_ids: list[int] | None = None,
        model_ids: list[int] | None = None,
        filter_start: datetime | None = None,
        filter_end: datetime | None = None,
        test_case_ids: list[str] | None = None,
        limit_ids: list[str] | None = None,
        passed: bool | None = None,
    ) -> int:
        where, params = self._events_filter(
            dashboard_config_id,
            session_ids,
            model_ids,
            filter_start,
            filter_end,
            test_case_ids,
            limit_ids,
            passed,
        )
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM dashboard_evaluation_event e
                JOIN dashboard_run_session s ON s.id = e.dashboard_run_session_id
                WHERE {where}
                """,
                params,
            ).fetchone()
            return row[0]

    def list_events(
        self,
        dashboard_config_id: int,
        session_ids: list[int] | None = None,
        model_ids: list[int] | None = None,
        filter_start: datetime | None = None,
        filter_end: datetime | None = None,
        test_case_ids: list[str] | None = None,
        limit_ids: list[str] | None = None,
        passed: bool | None = None,
        sort_by: str = "timestamp",
        order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """One page of evaluation events with their violated limits attached."""
        where, params = self._events_filter(
            dashboard_config_id,
            session_ids,
            model_ids,
            filter_start,
            filter_end,
            test_case_ids,
            limit_ids,
            passed,
        )
        sort_column = EVENT_SORT_COLUMNS[sort_by]
        direction = "DESC" if order == "desc" else "ASC"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT
                    e.id,
                    e.dashboard_run_session_id AS session_id,
                    s.start_time AS session_start,
                    s.end_time AS session_end,
                    s.model_id,
                    s.model_name,
                    e.timestamp,
                    e.test_case_id,
                    e.test_case_name,
                    e.passed,
                    e.picture_url
                FROM dashboard_evaluation_event e
                JOIN dashboard_run_session s ON s.id = e.dashboard_run_session_id
                WHERE {where}
                ORDER BY {sort_column} {direction}, e.id {direction}
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
            events = [dict(row) for row in rows]
            violated_by_event = self._fetch_violated_limits(
                conn, [e["id"] for e in events]
            )
        for event in events:
            event["violated_limits"] = violated_by_event.get(event["id"], [])
        return events

    @staticmethod
    def _fetch_detections(
        conn: sqlite3.Connection, event_ids: list[int]
    ) -> dict[int, list[dict]]:
        """Event-related (role-marked) detections per event.

        Events saved before the related-only restriction also stored plain
        commit-frame detections with role NULL; those rows stay in the table
        but are filtered out here so old and new events return the same
        payload shape.
        """
        detections_by_event: dict[int, list[dict]] = {}
        if not event_ids:
            return detections_by_event
        placeholders = ",".join("?" for _ in event_ids)
        rows = conn.execute(
            f"""
            SELECT event_id, label_id, label_name, confidence,
                   x_min, y_min, x_max, y_max,
                   display_id, parent_display_id, role
            FROM dashboard_evaluation_event_detection
            WHERE event_id IN ({placeholders})
                AND role IS NOT NULL
            ORDER BY event_id ASC, id ASC
            """,
            event_ids,
        ).fetchall()
        for r in rows:
            d = dict(r)
            detections_by_event.setdefault(d.pop("event_id"), []).append(d)
        return detections_by_event

    def get_event(self, dashboard_config_id: int, event_id: int) -> dict | None:
        """Full event detail: session columns, violated limits, detections.

        None when the event does not exist or belongs to another dashboard.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                    e.id,
                    e.dashboard_run_session_id AS session_id,
                    s.start_time AS session_start,
                    s.end_time AS session_end,
                    s.model_id,
                    s.model_name,
                    e.timestamp,
                    e.test_case_id,
                    e.test_case_name,
                    e.passed,
                    e.picture_url
                FROM dashboard_evaluation_event e
                JOIN dashboard_run_session s ON s.id = e.dashboard_run_session_id
                WHERE e.id = ? AND s.dashboard_config_id = ?
                """,
                (event_id, dashboard_config_id),
            ).fetchone()
            if row is None:
                return None
            event = dict(row)
            event["violated_limits"] = self._fetch_violated_limits(
                conn, [event_id]
            ).get(event_id, [])
            event["detections"] = self._fetch_detections(conn, [event_id]).get(
                event_id, []
            )
            return event

    def get_event_detections(self, event_ids: list[int]) -> dict[int, list[dict]]:
        """Batch detections per event, for the export renderer."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return self._fetch_detections(conn, event_ids)


@lru_cache(maxsize=1)
def reports_store_factory() -> ReportsStore:
    return ReportsStore()
