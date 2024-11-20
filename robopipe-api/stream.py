import anyio
import threading

from .log import logger
from .camera.camera_manager import CameraManager
from .error import SensorNotFoundException
from .video_encoder import VideoEncoder
from .utils.singleton import Singleton
from .websocket import WebSocket


StreamKey = tuple[str, str]
StreamSubscriber = dict[StreamKey, list[WebSocket]]


@Singleton
class StreamService:
    def __init__(self):
        self.camera_manager = CameraManager()
        self.subscribers: StreamSubscriber = {}
        self.encoders: dict[StreamKey, VideoEncoder] = {}
        # self.workers

    def __del__(self):
        self.stop()

    def stop(self):
        self.subscribers.clear()

    async def subscribe(self, key: StreamKey, handler: WebSocket):
        mxid, sensor_name = key
        camera = self.camera_manager[mxid]

        if sensor_name not in camera.sensors.keys():
            raise SensorNotFoundException()

        if key not in self.subscribers:
            self.subscribers[key] = []
            self.encoders[key] = VideoEncoder(camera.sensors[key[1]])

        self.subscribers[key].append(handler)
        await handler.send(self.encoders[key].init_fragment)

        if len(self.subscribers[key]) == 1:
            self.open_stream(key)

    def unsubscribe(self, key: StreamKey, handler: WebSocket):
        if key in self.subscribers:
            self.subscribers[key].remove(handler)

            if not self.subscribers[key]:
                del self.subscribers[key]
                del self.encoders[key]

    async def stream(self, key: StreamKey):
        subscribers = self.subscribers.get(key)
        video_encoder = self.encoders[key]

        async def broadcast(frame):
            async with anyio.create_task_group() as tg:
                for subscriber in subscribers:
                    tg.start_soon(subscriber.send, frame)

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
