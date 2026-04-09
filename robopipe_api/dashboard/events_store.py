import os
import sqlite3
from functools import lru_cache
from pathlib import Path


class EventsStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (
            Path(os.getenv("ROBOPIPE_DATA_DIR", str(Path.home() / ".robopipe")))
            / "robopipe.db"
        )

    def __init_migrations_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

    def __run_pending_migrations(self, conn: sqlite3.Connection) -> None:
        migrations_dir = Path(__file__).parent / "migrations"
        applied = set(
            row[0] for row in conn.execute("SELECT name FROM _migrations").fetchall()
        )
        for migration in sorted(migrations_dir.glob("*.sql")):
            if migration.name in applied:
                continue
            with open(migration, "r") as f:
                conn.executescript(f.read())
            conn.execute("INSERT INTO _migrations (name) VALUES (?)", (migration.name,))
        conn.commit()

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            self.__init_migrations_table(conn)
            self.__run_pending_migrations(conn)

    def start_session(self, dashboard_config_id: int) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO dashboard_run_session (dashboard_config_id) VALUES (?)",
                (dashboard_config_id,),
            )
            return cursor.lastrowid

    def get_session_start_time(self, session_id: int) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT start_time FROM dashboard_run_session WHERE id = ?",
                (session_id,),
            ).fetchone()
            return row[0] if row else None

    def end_session(self, session_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE dashboard_run_session SET end_time = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )

    def inc_counter(
        self, session_id: int, label_id: int, label_name: str, value: int = 1
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO dashboard_counter (dashboard_run_session_id, label_id, label_name, value)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(dashboard_run_session_id, label_id) DO UPDATE SET value = value + ?
                """,
                (session_id, label_id, label_name, value, value),
            )

    def get_counters(self, session_id: int) -> dict[int, int]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT label_id, value FROM dashboard_counter WHERE dashboard_run_session_id = ?",
                (session_id,),
            ).fetchall()
            return {row[0]: row[1] for row in rows}

    def save_event(
        self,
        session_id: int,
        test_case_id: str,
        test_case_name: str,
        failed_limit_id: str | None,
        failed_limit_name: str | None,
    ) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO dashboard_evaluation_event
                    (dashboard_run_session_id, test_case_id, test_case_name,
                     failed_limit_id, failed_limit_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    test_case_id,
                    test_case_name,
                    failed_limit_id,
                    failed_limit_name,
                ),
            )
            return cursor.lastrowid

    def update_event_picture(self, event_ids: list[int], picture_url: str) -> None:
        if not event_ids:
            return
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ",".join("?" for _ in event_ids)
            conn.execute(
                f"UPDATE dashboard_evaluation_event SET picture_url = ? WHERE id IN ({placeholders})",
                [picture_url, *event_ids],
            )

    def get_event_picture_url(self, event_id: int) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT picture_url FROM dashboard_evaluation_event WHERE id = ?",
                (event_id,),
            ).fetchone()
            return row[0] if row else None

    def get_unsent_events(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM detection_events WHERE sent = 0 LIMIT 100"
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_events_sent(self, ids: list[str]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "UPDATE detection_events SET sent = 1 WHERE id = ?",
                [(id_,) for id_ in ids],
            )

    def has_unsent_events(self) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM detection_events WHERE sent = 0"
            ).fetchone()
            return row[0] > 0


@lru_cache(maxsize=1)
def events_store_factory() -> EventsStore:
    return EventsStore()
