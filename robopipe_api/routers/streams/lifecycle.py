from fastapi import HTTPException, status

from ...camera.sensor.sensor_config import SensorConfigProperties
from ...camera.sensor.sensor_control import SensorControl
from ...models.batch_stream_update import BatchStreamUpdate
from ...models.sensor_control import SensorControlCapabilities, SensorControlUpdate
from ...models.stream_info import StreamInfo
from ..common import CameraDep, SensorDep, StreamName
from . import router, stream_router


@router.get("/")
def list_all_streams(camera: CameraDep) -> list[StreamInfo]:
    get_sensor_info = lambda sensor: StreamInfo(
        name=sensor,
        active=(sensor in camera.sensors),
        replay=(camera.get_replay_video(sensor) is not None),
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
        replay=(camera.get_replay_video(sensor) is not None),
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


@stream_router.get("/control/capabilities")
def get_stream_control_capabilities(
    sensor: SensorDep,
) -> SensorControlCapabilities:
    return SensorControlCapabilities.from_features(sensor.features)


@stream_router.post("/control")
def update_stream_control(
    sensor: SensorDep, control: SensorControlUpdate
) -> SensorControl:
    update_dict = control.model_dump(exclude_unset=True, exclude_none=True)
    capabilities = SensorControlCapabilities.from_features(sensor.features)
    unsupported = capabilities.unsupported_fields(update_dict)
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Fields not supported by this sensor: {', '.join(unsupported)}",
        )

    updated_control = sensor.control.model_copy(update=update_dict)
    sensor.control = SensorControl.model_validate(updated_control)

    return sensor.control


@stream_router.post("/control/reset")
def reset_stream_control(sensor: SensorDep) -> SensorControl:
    sensor.control = SensorControl.default_for(sensor.features)
    sensor.refresh_control_from_frame()
    return sensor.control
