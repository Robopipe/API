from fastapi import HTTPException, status

from ...camera.sensor.sensor_config import SensorConfigProperties
from ...camera.sensor.sensor_control import SensorControl
from ...models.batch_stream_update import BatchStreamUpdate
from ...models.sensor_control import SensorControlUpdate
from ...models.stream_info import StreamInfo
from ..common import CameraDep, SensorDep, StreamName
from . import router, stream_router


@router.get("/")
def list_all_streams(camera: CameraDep) -> list[StreamInfo]:
    get_sensor_info = lambda sensor: StreamInfo(
        name=sensor,
        active=(sensor in camera.sensors),
        replay=(sensor in camera._replay_video_paths),
    )
    sensors = list(map(get_sensor_info, camera.all_sensors.keys()))

    return sensors


@router.patch("/")
def batch_update_streams(
    camera: CameraDep, update: BatchStreamUpdate
) -> list[StreamInfo]:
    try:
        camera.batch_update_sensors(update.activate, update.deactivate)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    get_sensor_info = lambda sensor: StreamInfo(
        name=sensor,
        active=(sensor in camera.sensors),
        replay=(sensor in camera._replay_video_paths),
    )
    return list(map(get_sensor_info, camera.all_sensors.keys()))


@stream_router.post("/", status_code=status.HTTP_201_CREATED)
def activate_stream(camera: CameraDep, stream_name: StreamName):
    camera.activate_sensor(stream_name)


@stream_router.delete("/", status_code=status.HTTP_202_ACCEPTED)
def deactivate_stream(camera: CameraDep, stream_name: StreamName):
    camera.deactivate_sensor(stream_name)


@stream_router.get("/config")
def get_stream_config(sensor: SensorDep) -> SensorConfigProperties:
    return sensor.config


@stream_router.post("/config")
def update_stream_config(
    sensor: SensorDep, config: SensorConfigProperties
) -> SensorConfigProperties:
    sensor.config = config

    return sensor.config


@stream_router.get("/control")
def get_stream_control(sensor: SensorDep) -> SensorControl:
    return sensor.control


@stream_router.post("/control")
def update_stream_control(
    sensor: SensorDep, control: SensorControlUpdate
) -> SensorControl:
    updated_control = sensor.control.model_copy(
        update=control.model_dump(exclude_unset=True, exclude_none=True)
    )
    sensor.control = SensorControl.model_validate(updated_control)

    return sensor.control
