from fastapi import Depends, Path

from typing import Annotated

from ..camera.camera import Camera
from ..camera.camera_manager import CameraManager, camera_manager_factory
from ..camera.sensor import Sensor
from ..stream import StreamService, stream_service_factory

CameraManagerDep = Annotated[CameraManager, Depends(camera_manager_factory)]
Mxid = Annotated[str, Path(regex=r"[A-Z0-9]+")]


def get_camera(camera_manager: CameraManagerDep, mxid: Mxid):
    return camera_manager[mxid]


CameraDep = Annotated[Camera, Depends(get_camera)]
SensorName = Annotated[str, Path(regex=r"CAM_[A-H]")]


def get_sensor(camera: CameraDep, sensor_name: SensorName):
    return camera.sensors[sensor_name]


SensorDep = Annotated[Sensor, Depends(get_sensor)]


def get_stream_service(camera_manager: CameraManagerDep):
    return stream_service_factory(camera_manager)


StreamServiceDep = Annotated[StreamService, Depends(get_stream_service)]
