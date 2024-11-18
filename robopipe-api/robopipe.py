import tornado.httpserver
import tornado.web
import tornado.ioloop
import tornado.routing
import signal

from .log import logger
from .camera.camera_manager import CameraManager
from .stream import StreamService
from .handler.camera_handler import CamerasHandler, CameraHandler, CameraStatsHandler
from .handler.sensor_handler import (
    SensorsHandler,
    SensorCaptureHandler,
    SensorConfigHandler,
    SensorNNHandler,
)
from .handler.stream_handler import StreamHandler


def main():
    main_loop = tornado.ioloop.IOLoop.current()

    camera_manager = CameraManager()
    camera_manager.boot_cameras()

    stream_service = StreamService(camera_manager, main_loop)

    logger.info(f"Found {len(camera_manager.cameras)} camera(s)")

    app = tornado.web.Application(
        [
            (r"/cameras", CamerasHandler, dict(camera_manager=camera_manager)),
            (
                r"/cameras/([A-Z0-9]+)",
                CameraHandler,
                dict(camera_manager=camera_manager),
            ),
            (
                r"/cameras/([A-Z0-9]+)/stats",
                CameraStatsHandler,
                dict(camera_manager=camera_manager),
            ),
            (
                r"/cameras/([A-Z0-9]+)/sensors",
                SensorsHandler,
                dict(camera_manager=camera_manager),
            ),
            (
                r"/cameras/([A-Z0-9]+)/sensors/(CAM_[A-H])/config",
                SensorConfigHandler,
                dict(camera_manager=camera_manager),
            ),
            (
                r"/cameras/([A-Z0-9]+)/sensors/(CAM_[A-H])/still",
                SensorCaptureHandler,
                dict(camera_manager=camera_manager),
            ),
            (
                r"/cameras/([A-Z0-9]+)/sensors/(CAM_[A-H])/stream",
                StreamHandler,
                dict(stream_service=stream_service),
            ),
            (
                r"/cameras/([A-Z0-9]+)/sensors/(CAM_[A-H])/nn",
                SensorNNHandler,
                dict(camera_manager=camera_manager),
            ),
        ],
    )

    server = tornado.httpserver.HTTPServer(app)
    server.listen(8080)

    def sig_handler(sig, frame):
        if sig in (signal.SIGTERM, signal.SIGINT):
            main_loop.add_callback_from_signal(shutdown)

    def shutdown():
        server.stop()
        main_loop.stop()

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    logger.info("Starting HTTP server on port 8080")

    main_loop.start()


if __name__ == "__main__":
    main()
