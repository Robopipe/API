import av
import tornado.websocket
import tornado.ioloop
import tornado.gen

import asyncio
import io

from .log import logger
from .camera.camera_manager import CameraManager
from .error import SensorNotFoundException


StreamKey = tuple[str, str]
StreamSubscriber = dict[StreamKey, list[tornado.websocket.WebSocketHandler]]


class StreamService:
    def __init__(self, camera_manager: CameraManager, main_loop: tornado.ioloop.IOLoop):
        self.camera_manager = camera_manager
        self.main_loop = main_loop
        self.subscribers: StreamSubscriber = {}

    def subscribe(self, key: StreamKey, handler: tornado.websocket.WebSocketHandler):
        mxid, sensor_name = key
        camera = self.camera_manager[mxid]

        if sensor_name not in camera.sensors.keys():
            raise SensorNotFoundException()

        if key not in self.subscribers:
            self.subscribers[key] = []

        self.subscribers[key].append(handler)

        if len(self.subscribers[key]) == 1:
            self.open_stream(key)

    def unsubscribe(self, key: StreamKey, handler: tornado.websocket.WebSocketHandler):
        if key in self.subscribers:
            self.subscribers[key].remove(handler)

            if not self.subscribers[key]:
                del self.subscribers[key]

    async def stream(self, key: StreamKey):
        subscribers = self.subscribers.get(key)

        buffer = io.BytesIO()
        container = av.open(
            buffer,
            "w",
            "mp4",
            options={
                "movflags": "frag_keyframe+empty_moov+faststart+default_base_moof",
                "flush_packets": "1",
            },
        )
        video_stream = container.add_stream(
            "h264",
            30,
            options={
                "tune": "zerolatency",
                "preset": "ultrafast",
                "reset_timestamps": "1",
            },
        )

        video_stream.rate = 20
        video_stream.bit_rate = 5000000
        video_stream.gop_size = 1

        while subscribers:
            sensor_handle = self.camera_manager[key[0]].sensors[key[1]]
            frame = sensor_handle.get_video_frame()

            if frame is None:
                continue

            container.mux(video_stream.encode(frame))

            await subscribers[0].write_message(buffer.getvalue(), True)
            buffer.seek(0)
            buffer.truncate()
            subscribers = self.subscribers.get(key)

        container.close()

    def open_stream(self, key: StreamKey):
        def start_stream():
            logger.info(f"Starting stream for camera: {key[0]}, sensor: {key[1]}")
            current_loop = tornado.ioloop.IOLoop.current()
            asyncio.run(self.stream(key))
            current_loop.stop()
            logger.info(f"Stopping stream for camera: {key[0]}, sensor: {key[1]}")

        self.main_loop.run_in_executor(None, start_stream)
