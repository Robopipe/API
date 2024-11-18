import av
import tornado.websocket
import tornado.ioloop
import tornado.gen

import asyncio

from .log import logger
from .camera.camera_manager import CameraManager
from .error import SensorNotFoundException
from .video_encoder import VideoEncoder


StreamKey = tuple[str, str]
StreamSubscriber = dict[StreamKey, list[tornado.websocket.WebSocketHandler]]


class StreamService:
    def __init__(self, camera_manager: CameraManager, main_loop: tornado.ioloop.IOLoop):
        self.camera_manager = camera_manager
        self.main_loop = main_loop
        self.subscribers: StreamSubscriber = {}
        self.encoders: dict[StreamKey, VideoEncoder] = {}

    def __del__(self):
        self.stop()

    def stop(self):
        self.subscribers.clear()

    async def subscribe(
        self, key: StreamKey, handler: tornado.websocket.WebSocketHandler
    ):
        mxid, sensor_name = key
        camera = self.camera_manager[mxid]

        if sensor_name not in camera.sensors.keys():
            raise SensorNotFoundException()

        if key not in self.subscribers:
            self.subscribers[key] = []
            self.encoders[key] = VideoEncoder(camera.sensors[key[1]])

        self.subscribers[key].append(handler)
        await handler.write_message(self.encoders[key].init_fragment, True)

        if len(self.subscribers[key]) == 1:
            self.open_stream(key)

    def unsubscribe(self, key: StreamKey, handler: tornado.websocket.WebSocketHandler):
        if key in self.subscribers:
            self.subscribers[key].remove(handler)

            if not self.subscribers[key]:
                del self.subscribers[key]
                del self.encoders[key]

    async def stream(self, key: StreamKey):
        subscribers = self.subscribers.get(key)
        video_encoder = self.encoders[key]

        while subscribers:
            try:
                frame = next(video_encoder)
            except StopIteration:
                video_encoder = self.encoders[key] = VideoEncoder(
                    self.camera_manager[key[0]].sensors[key[1]]
                )
                continue

            send_futures = [
                handler.write_message(frame, True) for handler in subscribers
            ]

            await tornado.gen.multi(send_futures)

            subscribers = self.subscribers.get(key)

    def open_stream(self, key: StreamKey):
        def start_stream():
            logger.info(f"Starting stream for camera: {key[0]}, sensor: {key[1]}")
            current_loop = tornado.ioloop.IOLoop.current()
            asyncio.run(self.stream(key))
            current_loop.stop()
            logger.info(f"Stopping stream for camera: {key[0]}, sensor: {key[1]}")

        return self.main_loop.run_in_executor(None, start_stream)
