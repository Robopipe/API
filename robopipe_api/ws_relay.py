import asyncio
import json
import logging
from functools import lru_cache
from typing import Any, Callable, Hashable

import anyio.to_thread
from fastapi import WebSocket

logger = logging.getLogger(__name__)

ChannelKey = Hashable


class ProducerTerminated(Exception):
    """
    Raised by a producer to signal the relay should stop invoking it.

    Distinct from a plain Exception (which the relay logs and retries after
    a sleep). Use this when the underlying resource is gone and retries
    will never succeed — e.g. the NN pipeline was deleted out from under
    the stream.
    """


class ProducerSkipMessage(Exception):
    """
    Raised by a producer to skip broadcasting this iteration.

    The relay keeps the producer loop alive and immediately calls the
    producer again. Use this for rate-limiting where the producer still
    needs to run side effects (state updates) every tick but only wants
    to broadcast some of them.
    """


class _Channel:
    """Internal state for a single relay channel."""

    def __init__(self):
        self.queues: set[asyncio.Queue[str]] = set()
        self.producer_task: asyncio.Task | None = None


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
        Subscribe *ws* to *key* and block until the connection closes.

        The caller must ``await ws.accept()`` **before** calling this.
        """
        channel = self._channels.get(key)
        if channel is None:
            channel = _Channel()
            self._channels[key] = channel

        # Each subscriber gets a 1-slot queue.  The producer replaces
        # stale data so the subscriber always gets the latest message.
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        channel.queues.add(q)

        if channel.producer_task is None or channel.producer_task.done():
            channel.producer_task = asyncio.create_task(self._produce(key, producer))

        # Two concurrent loops: one sends data, one detects disconnect.
        # Local variables keep strong references — no GC risk.
        send_task = asyncio.create_task(self._send_loop(ws, q))
        recv_task = asyncio.create_task(self._recv_loop(ws))

        try:
            # When *either* task finishes (disconnect or send error),
            # cancel the other and clean up.
            _done, pending = await asyncio.wait(
                [send_task, recv_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
        finally:
            channel.queues.discard(q)
            if not channel.queues:
                if channel.producer_task is not None:
                    channel.producer_task.cancel()
                self._channels.pop(key, None)
            try:
                await ws.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _produce(self, key: ChannelKey, producer: Callable[[], Any]):
        """Fetch data from *producer* in a thread and push to every queue."""
        try:
            while True:
                channel = self._channels.get(key)
                if channel is None or not channel.queues:
                    return

                try:
                    data = await anyio.to_thread.run_sync(
                        producer, abandon_on_cancel=True
                    )
                except ProducerTerminated:
                    logger.info(
                        "Producer terminated for channel %s (resource gone)", key
                    )
                    return
                except ProducerSkipMessage:
                    continue
                except Exception:
                    logger.exception("Producer error on channel %s", key)
                    await asyncio.sleep(0.1)
                    continue

                text = json.dumps(data, separators=(",", ":"))

                for q in list(channel.queues):
                    # Drop old data so the subscriber always gets the
                    # latest message rather than falling behind.
                    if q.full():
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    try:
                        q.put_nowait(text)
                    except asyncio.QueueFull:
                        pass
        except asyncio.CancelledError:
            pass

    @staticmethod
    async def _send_loop(ws: WebSocket, q: asyncio.Queue[str]):
        """Read from *q* and forward to the WebSocket."""
        while True:
            text = await q.get()
            await ws.send_text(text)

    @staticmethod
    async def _recv_loop(ws: WebSocket):
        """Block until the client disconnects."""
        try:
            while True:
                await ws.receive_text()
        except Exception:
            pass


@lru_cache(maxsize=1)
def ws_relay_factory() -> WebSocketRelay:
    return WebSocketRelay()
