import tornado.httpserver
import tornado.web
import tornado.ioloop
import tornado.routing
import signal

from .log import logger
from .camera.camera_manager import CameraManager
from .stream import StreamService
from .handler import *

from .app import app


def main():
    main_loop = tornado.ioloop.IOLoop.current()

    camera_manager = CameraManager()
    camera_manager.boot_cameras()

    stream_service = StreamService(camera_manager, main_loop)

    logger.info(f"Found {len(camera_manager.cameras)} camera(s)")
    app.add_data({"camera_manager": camera_manager, "stream_service": stream_service})
    app.build()

    server = tornado.httpserver.HTTPServer(app)
    server.listen(8080)

    def sig_handler(sig, frame):
        if sig in (signal.SIGTERM, signal.SIGINT):
            main_loop.add_callback_from_signal(shutdown)

    def shutdown():
        stream_service.stop()
        server.stop()
        main_loop.stop()

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    logger.info("Starting HTTP server on port 8080")

    main_loop.start()


if __name__ == "__main__":
    main()
