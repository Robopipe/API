from fastapi import APIRouter, WebSocket
import anyio
from fastapi.responses import Response
import fastapi

from io import BytesIO

from ..camera.sensor_config import SensorConfigProperties
from ..camera.sensor_control import SensorControl
from ..utils.ws_adapter import WsAdapter
from .common import CameraDep, SensorDep, Mxid, SensorName, StreamServiceDep

router = APIRouter(prefix="/cameras/{mxid}/sensors")


@router.get("/")
def get_sensors(camera: CameraDep):
    return {
        sensor: {"active": sensor in camera.sensors}
        for sensor in camera.all_sensors.keys()
    }


@router.get("/{sensor_name}/config")
def get_sensor_config(sensor: SensorDep) -> SensorConfigProperties:
    return sensor.config


@router.post("/{sensor_name}/config")
def update_sensor_config(
    sensor: SensorDep, config: SensorConfigProperties
) -> SensorConfigProperties:
    sensor.config = config

    return sensor.config


@router.get("/{sensor_name}/control")
def get_sensor_control(sensor: SensorDep) -> SensorControl:
    return sensor.control


@router.post("/{sensor_name}/control")
def update_sensor_control(sensor: SensorDep, control: SensorControl) -> SensorControl:
    sensor.control = control

    return sensor.control


@router.get("/{sensor_name}/still")
def capture_still_image(sensor: SensorDep, format: str = "jpeg"):
    img_buffer = BytesIO()
    sensor.capture_still().save(img_buffer, format)

    return Response(img_buffer.getvalue(), media_type=f"image/{format}")


@router.websocket("/{sensor_name}/stream")
async def get_sensor_stream(
    ws: WebSocket, mxid: Mxid, sensor_name: SensorName, stream_service: StreamServiceDep
):
    tg = anyio.create_task_group()

    async def sleep():
        async with tg:
            tg.start_soon(anyio.sleep_forever)

    ws_adapter = WsAdapter(ws)
    await ws_adapter.accept()
    await stream_service.subscribe(
        (mxid, sensor_name), ws_adapter, lambda: tg.cancel_scope.cancel()
    )
    await sleep()
    stream_service.unsubscribe((mxid, sensor_name), ws_adapter)
