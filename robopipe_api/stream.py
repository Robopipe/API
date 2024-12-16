from functools import lru_cache
import anyio
import anyio.from_thread
import anyio.to_thread
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

    def __del__(self):
        self.stop()

    def stop(self):
        self.subscribers.clear()

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
            await anyio.to_thread.run_sync(self.stream, key)

    def unsubscribe(self, key: StreamKey, handler: WebSocket):
        if key in self.subscribers:
            subscriber_index = None

            for i in range(len(self.subscribers[key])):
                if self.subscribers[key][i][0] == handler:
                    subscriber_index = i
                    break

            if subscriber_index is not None:
                self.subscribers[key].pop(subscriber_index)

            if not self.subscribers[key]:
                del self.subscribers[key]
                del self.encoders[key]

    def stream(self, key: StreamKey):
        subscribers = self.subscribers.get(key)
        video_encoder = self.encoders[key]

        async def broadcast(frame):
            async def try_send(
                subscriber: WebSocket, frame, on_close: Callable[[], None] | None = None
            ):
                try:
                    await subscriber.send(frame)
                except:
                    if on_close is not None:
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

            anyio.from_thread.run(broadcast, frame)

            subscribers = self.subscribers.get(key)


@lru_cache(maxsize=1)
def stream_service_factory(camera_manager: CameraManager):
    return StreamService(camera_manager)
