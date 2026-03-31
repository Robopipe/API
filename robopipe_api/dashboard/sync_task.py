import asyncio
from functools import lru_cache

import anyio.to_thread
import httpx

from .events_store import EventsStore, events_store_factory

_RETRY_DELAY_SECONDS = 60


class SyncTask:
    def __init__(self, store: EventsStore) -> None:
        self._store = store
        self._pending: asyncio.Event | None = None

    def notify_new_events(self) -> None:
        """Signal the sync task that new events are waiting."""
        if self._pending is not None:
            self._pending.set()

    async def run(self) -> None:
        self._pending = asyncio.Event()
        while True:
            await self._pending.wait()
            self._pending.clear()
            await self._attempt_sync()

    async def _attempt_sync(self) -> None:
        events = await anyio.to_thread.run_sync(self._store.get_unsent_events)
        if not events:
            return

        by_url: dict[str, list[dict]] = {}
        for e in events:
            by_url.setdefault(e["remote_url"], []).append(e)

        any_failed = False
        async with httpx.AsyncClient() as client:
            for url, url_events in by_url.items():
                payload = [
                    {
                        "id": e["id"],
                        "test_case_id": e["test_case_id"],
                        "type": e["type"],
                        "timestamp": e["timestamp"],
                        "mxid": e["mxid"],
                        "stream_name": e["stream_name"],
                    }
                    for e in url_events
                ]
                try:
                    resp = await client.post(url, json=payload, timeout=10.0)
                    if resp.is_success:
                        ids = [e["id"] for e in url_events]
                        await anyio.to_thread.run_sync(
                            lambda ids=ids: self._store.mark_events_sent(ids)
                        )
                    else:
                        any_failed = True
                except Exception:
                    any_failed = True

        if any_failed:
            await asyncio.sleep(_RETRY_DELAY_SECONDS)
            if self._pending is not None:
                self._pending.set()


@lru_cache(maxsize=1)
def sync_task_factory() -> SyncTask:
    return SyncTask(events_store_factory())
