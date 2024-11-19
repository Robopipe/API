import tornado.web

import dataclasses

from ..mapper.device_info import from_device_info
from .base_handler import CameraBaseHandler


class CamerasHandler(CameraBaseHandler):
    def get(self):
        cameras = {
            camera.mxid: from_device_info(camera.info)
            for camera in self.camera_manager.cameras.values()
        }

        self.finish({"cameras": cameras})


class CameraHandler(CameraBaseHandler):
    def get(self, mxid: str):
        camera = self.camera_manager[mxid]

        self.finish(from_device_info(camera.info))

    def post(self, mxid: str):
        self.camera_manager.boot_camera(mxid)

        self.finish({"message": "Camera was booted successfully"})

    def delete(self, mxid: str):
        self.camera_manager.shutdown_camera(mxid)

        self.finish({"message": "Camera was shut down successfully"})


class CameraStatsHandler(CameraBaseHandler):
    def get(self, mxid: str):
        camera = self.camera_manager[mxid]

        self.finish(dataclasses.asdict(camera.stats))
