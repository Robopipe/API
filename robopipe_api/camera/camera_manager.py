import depthai as dai

from functools import lru_cache

from ..error import CameraNotFoundException
from .camera import Camera
from .device_info import DeviceState
from .pipeline.depth_pipeline import DepthPipeline


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
        devices = dai.Device.getAllConnectedDevices()

        for dev in devices:
            mxid = dev.getMxId()
            if mxid not in self.cameras:
                self.cameras[dev.mxid] = Camera(mxid, dev.name)

        for mxid in self.cameras.keys():
            if mxid not in mxids:
                del self.cameras[mxid]

    def boot_cameras(self):
        print("Booting cameras...")
        for mxid in self.cameras.keys():
            self.boot_camera(mxid)

    def boot_camera(self, mxid: str):
        camera = self.cameras[mxid]

        if camera.info.state != DeviceState.X_LINK_UNBOOTED:
            return

        camera.open(
            DepthPipeline(None, [sensor for sensor in camera.all_sensors.values()])
        )

    def shutdown_camera(self, mxid: str):
        self.cameras[mxid].close()


@lru_cache(maxsize=1)
def camera_manager_factory():
    return CameraManager()
