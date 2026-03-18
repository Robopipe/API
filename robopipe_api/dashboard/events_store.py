import os
import sqlite3
from functools import lru_cache
from pathlib import Path


class EventsStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (
            Path(os.getenv("ROBOPIPE_DATA_DIR", str(Path.home() / ".robopipe")))
            / "events.db"
        )

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS detection_events (
                    id TEXT PRIMARY KEY,
                    test_case_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    mxid TEXT NOT NULL,
                    stream_name TEXT NOT NULL,
                    remote_url TEXT NOT NULL,
                    sent INTEGER NOT NULL DEFAULT 0
                )
            """)

    def save_events(
        self,
        events: list[dict],
        mxid: str,
        stream_name: str,
        remote_url: str,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO detection_events"
                " (id, test_case_id, type, timestamp, mxid, stream_name, remote_url)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (e["id"], e["test_case_id"], e["type"], e["timestamp"], mxid, stream_name, remote_url)
                    for e in events
                ],
            )

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
