from aiortc.contrib.media import MediaRelay
from fastapi import Depends, Path, Request, Form, HTTPException, status
from fastapi.encoders import jsonable_encoder

from pydantic import ValidationError

from typing import Annotated


from ..camera.camera import Camera
from ..camera.camera_manager import CameraManager, camera_manager_factory
from ..camera.sensor.sensor_base import SensorBase
from ..models.nn_config import (
    NNType,
    NNConfig,
    NNGenericConfig,
    NNDetectionConfig,
    NNSpatialDetectionConfig,
)
from ..stream import StreamService, stream_service_factory
from ..video_track import media_relay_factory, video_track_factory, VideoTrack
from ..controller.devices import DeviceList, Devices, Device
from ..controller.devices import *
from ..webrtc_manager import WebRTCManager, webrtc_manager_factory
from ..ws_relay import WebSocketRelay, ws_relay_factory

CameraManagerDep = Annotated[CameraManager, Depends(camera_manager_factory)]
Mxid = Annotated[str, Path(regex=r"[A-Z0-9]+")]


def get_camera(camera_manager: CameraManagerDep, mxid: Mxid):
    camera = camera_manager.get(mxid)
    if camera is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Camera with mxid {mxid} not found"
        )
    return camera


CameraDep = Annotated[Camera, Depends(get_camera)]
StreamName = Annotated[str, Path(regex=r"CAM_[A-H]|DEPTH_[A-H]_[A-H]")]


def get_sensor(camera: CameraDep, stream_name: StreamName):
    sensor = camera.sensors.get(stream_name)
    if sensor is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Stream {stream_name} not found for camera {camera.mxid}",
        )
    return sensor


SensorDep = Annotated[SensorBase, Depends(get_sensor)]


def get_stream_service(camera_manager: CameraManagerDep):
    return stream_service_factory(camera_manager)


StreamServiceDep = Annotated[StreamService, Depends(get_stream_service)]


def get_video_track(sensor: SensorDep):
    return video_track_factory(sensor)


VideoTrackDep = Annotated[VideoTrack, Depends(get_video_track)]


def get_video_relay(sensor: SensorDep):
    return media_relay_factory(sensor)


VideoRelayDep = Annotated[MediaRelay, Depends(get_video_relay)]

WebRTCManagerDep = Annotated[WebRTCManager, Depends(lambda: webrtc_manager_factory())]
WSRelayDep = Annotated[WebSocketRelay, Depends(lambda: ws_relay_factory())]

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


def nn_config_checker(config: Annotated[str, Form()]):
    NN_CONFIG_MAP = {
        NNType.Generic: NNGenericConfig,
        NNType.Detection: NNDetectionConfig,
        NNType.SpatialDetection: NNSpatialDetectionConfig,
    }

    try:
        config_model = NNConfig.model_validate_json(config)
        nn_config_cls = NN_CONFIG_MAP.get(config_model.type)

        if nn_config_cls is None:
            raise ValueError(f"Invalid NNType: {config_model.type}")

        if not isinstance(config_model.nn_config, nn_config_cls):
            raise ValueError(
                f"Invalid NNType: {config_model.type} and NNConfig: {config_model.nn_config}. Expected: {nn_config_cls}"
            )

        return config_model
    except ValidationError as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, jsonable_encoder(e.errors())
        ) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


NNConfigDep = Annotated[NNConfig, Depends(nn_config_checker)]
