import dataclasses

from ..app import app
from ..mapper.device_info import from_device_info
from .base_handler import CameraBaseHandler


@app.route(r"/cameras")
class CamerasHandler(CameraBaseHandler):
    def get(self):
        """Get a greeting endpoint.
        ---
        description: Get a greeting
        responses:
            200:
                description: A greeting to the client
                schema:
                    $ref: '#/definitions/Greeting'
        """
        cameras = {
            camera.mxid: from_device_info(camera.info)
            for camera in self.camera_manager.cameras.values()
        }

        self.finish({"cameras": cameras})


@app.route(r"/cameras/([A-Z0-9]+)")
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


@app.route(r"/cameras/([A-Z0-9]+)/stats")
class CameraStatsHandler(CameraBaseHandler):
    def get(self, mxid: str):
        camera = self.camera_manager[mxid]

        self.finish(dataclasses.asdict(camera.stats))
