import asyncio
import logging
import os
import shutil
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import anyio.to_thread

from ..paths import get_data_dir

logger = logging.getLogger(__name__)


@dataclass
class _Candidate:
    mtime: float
    size: int
    path: Path
    kind: str  # "picture" or "report"


class CleanupTask:
    """Periodically deletes oldest event pictures and reports when free disk
    space drops below the configured low-water mark, stopping once it rises
    back above the high-water mark.
    """

    def __init__(
        self,
        data_dir: Path,
        db_path: Path,
        interval_s: float,
        min_free_pct: float,
        target_free_pct: float,
        batch_size: int,
    ) -> None:
        self._data_dir = data_dir
        self._db_path = db_path
        self._interval_s = interval_s
        self._min_free_pct = min_free_pct
        self._target_free_pct = max(target_free_pct, min_free_pct)
        self._batch_size = max(batch_size, 1)
        self._pictures_dir = data_dir / "event_pictures"
        self._reports_dir = data_dir / "reports"

    async def run(self) -> None:
        while True:
            try:
                await anyio.to_thread.run_sync(self._cleanup_once)
            except Exception:
                logger.exception("Cleanup pass failed")
            await asyncio.sleep(self._interval_s)

    def _free_pct(self) -> float | None:
        try:
            usage = shutil.disk_usage(self._data_dir)
        except OSError:
            return None
        if usage.total == 0:
            return None
        return usage.free / usage.total * 100.0

    def _collect_candidates(self) -> list[_Candidate]:
        candidates: list[_Candidate] = []

        if self._pictures_dir.is_dir():
            try:
                with os.scandir(self._pictures_dir) as it:
                    for entry in it:
                        if not entry.is_file():
                            continue
                        try:
                            st = entry.stat()
                        except OSError:
                            continue
                        candidates.append(
                            _Candidate(
                                mtime=st.st_mtime,
                                size=st.st_size,
                                path=Path(entry.path),
                                kind="picture",
                            )
                        )
            except OSError:
                logger.exception("Failed to scan %s", self._pictures_dir)

        if self._reports_dir.is_dir():
            try:
                with os.scandir(self._reports_dir) as it:
                    for entry in it:
                        # Skip the .tmp directory used for in-progress report
                        # generation; deleting anything there would corrupt an
                        # active write.
                        if not entry.is_file():
                            continue
                        try:
                            st = entry.stat()
                        except OSError:
                            continue
                        candidates.append(
                            _Candidate(
                                mtime=st.st_mtime,
                                size=st.st_size,
                                path=Path(entry.path),
                                kind="report",
                            )
                        )
            except OSError:
                logger.exception("Failed to scan %s", self._reports_dir)

        candidates.sort(key=lambda c: c.mtime)
        return candidates

    def _cleanup_once(self) -> None:
        free_pct = self._free_pct()
        if free_pct is None or free_pct >= self._min_free_pct:
            return

        candidates = self._collect_candidates()
        if not candidates:
            return

        deleted_pictures: list[str] = []
        deleted_report_ids: list[int] = []
        bytes_freed = 0

        idx = 0
        while idx < len(candidates):
            chunk = candidates[idx : idx + self._batch_size]
            idx += self._batch_size

            for cand in chunk:
                try:
                    cand.path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Failed to delete %s", cand.path, exc_info=True)
                    continue
                bytes_freed += cand.size
                if cand.kind == "picture":
                    deleted_pictures.append(f"event_pictures/{cand.path.name}")
                else:
                    stem = cand.path.stem
                    try:
                        deleted_report_ids.append(int(stem))
                    except ValueError:
                        # Filename doesn't match the {report_id}.zip pattern,
                        # so there's no matching DB row to clean up.
                        pass

            current = self._free_pct()
            if current is not None and current >= self._target_free_pct:
                break

        self._update_db(deleted_pictures, deleted_report_ids)

        final_pct = self._free_pct()
        logger.info(
            "Cleanup deleted %d pictures, %d reports, freed %.1f MB, free=%.2f%%",
            len(deleted_pictures),
            len(deleted_report_ids),
            bytes_freed / (1024 * 1024),
            final_pct if final_pct is not None else float("nan"),
        )

    def _update_db(
        self, deleted_pictures: list[str], deleted_report_ids: list[int]
    ) -> None:
        if not deleted_pictures and not deleted_report_ids:
            return
        if not self._db_path.exists():
            return

        try:
            with sqlite3.connect(self._db_path) as conn:
                if deleted_pictures:
                    try:
                        placeholders = ",".join("?" for _ in deleted_pictures)
                        conn.execute(
                            f"UPDATE dashboard_evaluation_event "
                            f"SET picture_url = NULL "
                            f"WHERE picture_url IN ({placeholders})",
                            deleted_pictures,
                        )
                    except sqlite3.Error:
                        logger.exception("Failed to null picture_url for deleted files")

                if deleted_report_ids:
                    try:
                        placeholders = ",".join("?" for _ in deleted_report_ids)
                        conn.execute(
                            f"DELETE FROM dashboard_report "
                            f"WHERE id IN ({placeholders})",
                            deleted_report_ids,
                        )
                    except sqlite3.Error:
                        logger.exception("Failed to delete dashboard_report rows")
        except sqlite3.Error:
            logger.exception("Failed to open DB for cleanup updates")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r, using default %s", name, raw, default)
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid int for %s=%r, using default %s", name, raw, default)
        return default


@lru_cache(maxsize=1)
def cleanup_task_factory() -> CleanupTask:
    data_dir = get_data_dir()
    return CleanupTask(
        data_dir=data_dir,
        db_path=data_dir / "robopipe.db",
        interval_s=_env_float("ROBOPIPE_CLEANUP_INTERVAL_SECONDS", 3600.0),
        min_free_pct=_env_float("ROBOPIPE_CLEANUP_MIN_FREE_PCT", 10.0),
        target_free_pct=_env_float("ROBOPIPE_CLEANUP_TARGET_FREE_PCT", 20.0),
        batch_size=_env_int("ROBOPIPE_CLEANUP_BATCH_SIZE", 100),
    )
