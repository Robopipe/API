import anyio.to_thread

from functools import lru_cache
import anyio
import threading
from typing import Callable

from .camera.camera_manager import CameraManager
from .error import SensorNotFoundException
from .video_encoder import VideoEncoder
from .websocket import WebSocket


StreamKey = tuple[str, str]
StreamSubscriber = dict[StreamKey, list[tuple[WebSocket, Callable[[], None]]]]


class StreamService:
    def __init__(self, camera_manager: CameraManager):
        self.camera_manager = camera_manager
        self.subscribers: StreamSubscriber = {}
        self.encoders: dict[StreamKey, VideoEncoder] = {}
        self.workers: dict[StreamKey, threading.Thread] = {}

    def __del__(self):
        self.stop()

    def stop(self):
        self.subscribers.clear()

        for worker in self.workers.values():
            worker.join()

    async def subscribe(
        self,
        key: StreamKey,
        handler: WebSocket,
        on_close: Callable[[], None] | None = None,
    ):
        mxid, sensor_name = key
        camera = self.camera_manager[mxid]

        if sensor_name not in camera.sensors.keys():
            raise SensorNotFoundException()

        if key not in self.subscribers:
            self.subscribers[key] = []
            self.encoders[key] = VideoEncoder(camera.sensors[key[1]])

        self.subscribers[key].append((handler, on_close))
        await handler.send(self.encoders[key].init_fragment)

        if len(self.subscribers[key]) == 1:
            self.open_stream(key)

    def unsubscribe(self, key: StreamKey, handler: WebSocket):
        if key in self.subscribers:
            for i in range(len(self.subscribers[key])):
                if self.subscribers[key][i][0] == handler:
                    break

            self.subscribers[key].pop(i)

            if not self.subscribers[key]:
                del self.subscribers[key]
                del self.encoders[key]
                self.workers[key].join()
                del self.workers[key]

    async def stream(self, key: StreamKey):
        subscribers = self.subscribers.get(key)
        video_encoder = self.encoders[key]

        async def broadcast(frame):
            async def try_send(
                subscriber: WebSocket, frame, on_close: Callable[[], None] | None = None
            ):
                try:
                    await subscriber.send(frame)
                except:
                    if on_close:
                        on_close()

            async with anyio.create_task_group() as tg:
                for subscriber, on_close in subscribers:
                    tg.start_soon(try_send, subscriber, frame, on_close)

        while subscribers:
            try:
                frame = next(video_encoder)
            except StopIteration:
                video_encoder = self.encoders[key] = VideoEncoder(
                    self.camera_manager[key[0]].sensors[key[1]]
                )
                continue

            await broadcast(frame)

            subscribers = self.subscribers.get(key)

    def open_stream(self, key: StreamKey):
        def start_stream():
            anyio.run(self.stream, key)

        worker = threading.Thread(target=start_stream)
        worker.start()
        self.workers[key] = worker


@lru_cache(maxsize=1)
def stream_service_factory(camera_manager: CameraManager):
    return StreamService(camera_manager)
