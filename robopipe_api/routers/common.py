from fastapi import Depends, Path

from typing import Annotated

from ..camera.camera import Camera
from ..camera.camera_manager import CameraManager
from ..camera.sensor import Sensor
from ..stream import StreamService

CameraManagerDep = Annotated[CameraManager, Depends(CameraManager)]
Mxid = Annotated[str, Path(regex=r"[A-Z0-9]+")]


def get_camera(camera_manager: CameraManagerDep, mxid: Mxid):
    return camera_manager[mxid]


CameraDep = Annotated[Camera, Depends(get_camera)]
SensorName = Annotated[str, Path(regex=r"CAM_[A-H]")]


def get_sensor(camera: CameraDep, sensor_name: SensorName):
    return camera.sensors[sensor_name]


SensorDep = Annotated[Sensor, Depends(get_sensor)]

StreamServiceDep = Annotated[StreamService, Depends(StreamService)]
