import tornado.websocket

from ..stream import StreamService


class StreamHandler(tornado.websocket.WebSocketHandler):
    def initialize(self, **kwargs):
        self.stream_service = kwargs["stream_service"]

    def check_origin(self, origin):
        return True

    async def open(self, mxid: str, sensor_name: str):
        self.stream_key = (mxid, sensor_name)
        await self.stream_service.subscribe((mxid, sensor_name), self)

    def on_close(self):
        self.stream_service.unsubscribe(self.stream_key, self)
