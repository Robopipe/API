import tornado.web

from ..camera.camera_manager import CameraManager
from ..error import (
    SensorNotFoundException,
    CameraNotFoundException,
    CameraShutDownException,
)


class BaseHandler(tornado.web.RequestHandler):
    def write_error(self, status_code, **kwargs):
        _, exception, trace = kwargs["exc_info"]

        if isinstance(
            exception, (CameraNotFoundException, SensorNotFoundException, KeyError)
        ):
            self.set_status(404)
            self.finish()
            return
        elif isinstance(exception, (CameraShutDownException)):
            self.set_status(423)
            self.finish()
            return

        self.finish()


class CameraBaseHandler(BaseHandler):
    def initialize(self, camera_manager: CameraManager):
        self.camera_manager = camera_manager
