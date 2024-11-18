import tornado.websocket

from ..stream import StreamService


class StreamHandler(tornado.websocket.WebSocketHandler):
    def initialize(self, stream_service: StreamService):
        self.stream_service = stream_service

    def check_origin(self, origin):
        return True

    def open(self, mxid: str, sensor_name: str):
        self.stream_key = (mxid, sensor_name)

        try:
            self.stream_service.subscribe((mxid, sensor_name), self)
        except:
            self.close()

    def on_close(self):
        self.stream_service.unsubscribe(self.stream_key, self)
