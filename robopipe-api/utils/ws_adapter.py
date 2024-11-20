import fastapi

from typing import Any

from ..websocket import WebSocket


class WsAdapter(WebSocket):
    def __init__(self, ws: fastapi.WebSocket):
        self.ws = ws

    def accept(self):
        return self.ws.accept()

    def close(self):
        return self.close()

    def send(self, data: str | bytes | dict | Any):
        if isinstance(data, str):
            return self.ws.send_text(data)
        elif isinstance(data, bytes):
            return self.ws.send_bytes(data)
        elif isinstance(data, dict):
            return self.ws.send_json(data)
        else:
            return self.ws.send(data)

    def receive(self):
        return self.ws.receive()
