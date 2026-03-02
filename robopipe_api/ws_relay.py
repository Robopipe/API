import asyncio
import logging
from functools import lru_cache
from typing import Any, Callable, Hashable

import anyio.to_thread
from fastapi import WebSocket

logger = logging.getLogger(__name__)

ChannelKey = Hashable


class _Channel:
    """Internal state for a single relay channel."""

    def __init__(self):
        self.subscribers: set[WebSocket] = set()
        self.task: asyncio.Task | None = None


class WebSocketRelay:
    """
    Generic WebSocket relay that broadcasts messages from a single producer
    to all subscribers on the same channel.

    When the first subscriber joins a channel, a producer task is started.
    When the last subscriber leaves, the producer task is cancelled.

    Usage::

        relay = WebSocketRelay()

        @app.websocket("/ws")
        async def ws_endpoint(ws: WebSocket):
            await ws.accept()
            await relay.subscribe(
                key=("my-channel",),
                ws=ws,
                producer=lambda: blocking_get_next_message(),
            )
    """

    def __init__(self):
        self._channels: dict[ChannelKey, _Channel] = {}

    async def subscribe(
        self,
        key: ChannelKey,
        ws: WebSocket,
        producer: Callable[[], Any],
    ):
        """
        Subscribe a WebSocket to a channel and block until the connection closes.

        The caller must ``await ws.accept()`` **before** calling this method.

        Args:
            key: Hashable channel identifier (e.g. ``(mxid, stream_name)``).
            ws: An already-accepted FastAPI ``WebSocket``.
            producer: A **sync** callable that returns a JSON-serialisable
                      message.  It is executed in a worker thread and may
                      block (e.g. waiting on a hardware queue).  The
                      returned value is broadcast to every subscriber on
                      the channel via ``ws.send_json``.
        """
        channel = self._channels.get(key)

        if channel is None:
            channel = _Channel()
            self._channels[key] = channel

        channel.subscribers.add(ws)

        # Start the producer loop when the first subscriber arrives.
        if channel.task is None or channel.task.done():
            channel.task = asyncio.create_task(self._produce(key, producer))

        try:
            # Block until the client disconnects.
            # We don't expect inbound messages, but receive_text() will
            # raise on disconnect / close.
            while True:
                await ws.receive_text()
        except Exception:
            pass
        finally:
            self._remove_subscriber(key, ws)
            try:
                await ws.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _remove_subscriber(self, key: ChannelKey, ws: WebSocket):
        channel = self._channels.get(key)
        if channel is None:
            return

        channel.subscribers.discard(ws)

        if not channel.subscribers:
            if channel.task is not None:
                channel.task.cancel()
            del self._channels[key]

    async def _produce(self, key: ChannelKey, producer: Callable[[], Any]):
        """Fetch data from *producer* in a thread and broadcast to subscribers."""
        try:
            while True:
                channel = self._channels.get(key)
                if channel is None or not channel.subscribers:
                    break

                try:
                    data = await anyio.to_thread.run_sync(producer)
                except Exception:
                    logger.exception("Producer error on channel %s", key)
                    continue

                # Snapshot the subscriber set so mutations during iteration
                # don't cause issues.
                disconnected: list[WebSocket] = []
                for ws in list(channel.subscribers):
                    try:
                        await ws.send_json(data)
                    except Exception:
                        disconnected.append(ws)

                for ws in disconnected:
                    self._remove_subscriber(key, ws)
        except asyncio.CancelledError:
            pass


@lru_cache(maxsize=1)
def ws_relay_factory() -> WebSocketRelay:
    return WebSocketRelay()
