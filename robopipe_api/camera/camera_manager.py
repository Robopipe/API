import depthai as dai

import time
from functools import lru_cache

from ..error import CameraNotFoundException
from ..log import logger
from .camera import Camera
from .pipeline.nn_pipeline import NNPipeline


class CameraManager:
    RESTART_RELOAD_RETRIES = 5
    RESTART_RELOAD_TIMEOUT_BASE = 1.0

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
        del self.cameras[mxid]

    def restart_camera(self, mxid: str):
        if mxid not in self.cameras:
            raise CameraNotFoundException()

        try:
            self.shutdown_camera(mxid)
        except Exception as e:
            logger.warning(
                f"restart_camera({mxid}): shutdown raised, continuing: {e}"
            )
            self.cameras.pop(mxid, None)

        timeout = self.RESTART_RELOAD_TIMEOUT_BASE
        for _ in range(self.RESTART_RELOAD_RETRIES):
            self.reload_cameras()
            if mxid in self.cameras:
                break
            time.sleep(timeout)
            timeout *= 2
        else:
            raise CameraNotFoundException()

        self.boot_camera(mxid)


@lru_cache(maxsize=1)
def camera_manager_factory():
    return CameraManager()
