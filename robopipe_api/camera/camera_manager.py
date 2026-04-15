import depthai as dai

from functools import lru_cache

from ..error import CameraNotFoundException
from .camera import Camera
from .pipeline.nn_pipeline import NNPipeline


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
        mxids = list(map(lambda x: x.deviceId, dai.DeviceBase.getAllConnectedDevices()))
        devices = dai.DeviceBase.getAllConnectedDevices()

        for dev in devices:
            mxid = dev.deviceId
            if mxid not in self.cameras:
                self.cameras[dev.deviceId] = Camera(mxid, dev.name)

        current_mxids = set(self.cameras.keys())
        for mxid in current_mxids:
            if mxid not in mxids:
                del self.cameras[mxid]

    def boot_cameras(self):
        for mxid in self.cameras.keys():
            self.boot_camera(mxid)

    def boot_camera(self, mxid: str):
        camera = self.cameras[mxid]
        boot_sensors = list(
            filter(
                lambda s: dai.CameraSensorType.COLOR in s.supportedTypes,
                camera.all_sensors.values(),
            )
        )
        pipeline = NNPipeline(device=camera.camera_handle)
        for sensor in boot_sensors:
            pipeline.add_sensor_config(sensor)
        camera.open(pipeline)

    def shutdown_camera(self, mxid: str):
        self.cameras[mxid].cleanup_replay_videos()
        self.cameras[mxid].close()


@lru_cache(maxsize=1)
def camera_manager_factory():
    return CameraManager()
