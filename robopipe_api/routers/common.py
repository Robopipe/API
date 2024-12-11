from fastapi import Depends, Path, Request

from typing import Annotated

from ..camera.camera import Camera
from ..camera.camera_manager import CameraManager, camera_manager_factory
from ..camera.sensor import Sensor
from ..stream import StreamService, stream_service_factory
from ..controller.devices import DeviceList, Devices, Device
from ..controller.devices import *

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

DEVICE_TYPES = [
    DI,
    RO,
    DO,
    AI,
    AO,
    SENSOR,
    LED,
    WATCHDOG,
    MODBUS_SLAVE,
    OWPOWER,
    REGISTER,
    DATA_POINT,
    OWBUS,
    DEVICE_INFO,
]

DevicesDep = Annotated[DeviceList, Depends(lambda: Devices)]
DeviceType = Annotated[str, Path(regex=r"{}".format("|".join(DEVICE_TYPES)))]


def get_device(devices: DevicesDep, circuit: str, request: Request):
    device_type = request.url.path.split("/")[2]

    return devices.by_name(device_type, circuit)


DeviceDep = Annotated[Device, Depends(get_device)]
