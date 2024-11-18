import depthai as dai

from .camera import Camera
from .pipeline import StreamingPipeline
from ..error import CameraNotFoundException


class CameraManager:
    cameras: dict[str, Camera] = {}

    def __init__(self):
        self.reload_cameras()

    def __getitem__(self, key: str):
        camera = self.get(key)

        if camera is None:
            raise CameraNotFoundException()

        return camera

    def get(self, key: str) -> Camera | None:
        return self.cameras.get(key)

    def reload_cameras(self):
        mxids = list(map(lambda x: x.getMxId(), dai.Device.getAllConnectedDevices()))

        for mxid in mxids:
            if mxid not in self.cameras:
                self.cameras[mxid] = Camera(mxid)

        for mxid in self.cameras.keys():
            if mxid not in mxids:
                del self.cameras[mxid]

    def boot_cameras(self):
        for mxid in self.cameras.keys():
            self.boot_camera(mxid)

    def boot_camera(self, mxid: str):
        camera = self.cameras[mxid]
        camera.open(
            StreamingPipeline([sensor for sensor in camera.all_sensors.values()])
        )

    def shutdown_camera(self, mxid: str):
        self.cameras[mxid].close()
