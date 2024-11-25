import depthai as dai
from fastapi import APIRouter, WebSocket, UploadFile, WebSocketDisconnect
import anyio
from fastapi.responses import Response

from io import BytesIO

from ..camera.nn import CameraNNConfig
from ..camera.sensor_config import SensorConfigProperties
from ..camera.sensor_control import SensorControl
from ..utils.ws_adapter import WsAdapter
from .common import CameraDep, SensorDep, Mxid, SensorName, StreamServiceDep

router = APIRouter(
    prefix="/cameras/{mxid}/sensors",
    tags=["sensors"],
    responses={404: {"description": "Camera not found"}},
)


@router.get("/")
def get_sensors(camera: CameraDep):
    return {
        sensor: {"active": sensor in camera.sensors}
        for sensor in camera.all_sensors.keys()
    }


sensor_router = APIRouter(
    prefix="/{sensor_name}",
    tags=["sensors"],
    responses={404: {"description": "Camera or sensor not found"}},
)


@sensor_router.get("/config")
def get_sensor_config(sensor: SensorDep) -> SensorConfigProperties:
    return sensor.config


@sensor_router.post("/config")
def update_sensor_config(
    sensor: SensorDep, config: SensorConfigProperties
) -> SensorConfigProperties:
    sensor.config = config

    return sensor.config


@sensor_router.get("/control")
def get_sensor_control(sensor: SensorDep) -> SensorControl:
    return sensor.control


@sensor_router.post("/control")
def update_sensor_control(sensor: SensorDep, control: SensorControl) -> SensorControl:
    sensor.control = control

    return sensor.control


@sensor_router.get(
    "/still",
    response_description="Image bytes in the selected format",
    response_model=bytes,
    response_class=Response(media_type="image/*"),
)
def capture_still_image(sensor: SensorDep, format: str | None = "jpeg") -> Response:
    img_buffer = BytesIO()
    sensor.capture_still().save(img_buffer, format)

    return Response(img_buffer.getvalue(), media_type=f"image/{format}")


@sensor_router.post("/nn")
async def deploy_nn(camera: CameraDep, sensor_name: SensorName, model: UploadFile):
    model_bytes = await model.read()
    blob = dai.OpenVINO.Blob(list(model_bytes))

    camera.deploy_nn(
        CameraNNConfig(dai.CameraBoardSocket.__members__[sensor_name], blob)
    )

    return {"status": "ok"}


@sensor_router.websocket("/nn")
async def get_sensor_detections(ws: WebSocket, sensor: SensorDep):
    await ws.accept()

    try:
        while True:
            detections = sensor.get_nn_detections()
            await ws.send_json({"detections": detections.getFirstLayerFp16()})
            await anyio.sleep(0.001)
    except WebSocketDisconnect:
        return


@sensor_router.websocket("/stream")
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


router.include_router(sensor_router)
