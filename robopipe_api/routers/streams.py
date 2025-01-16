import depthai as dai
from fastapi import APIRouter, WebSocket, UploadFile, WebSocketDisconnect, status
import anyio
from fastapi.responses import Response

from io import BytesIO

from ..camera.nn import CameraNNConfig, CameraNNYoloConfig, CameraNNMobileNetConfig
from ..camera.sensor_config import SensorConfigProperties
from ..camera.sensor_control import SensorControl
from ..models.nn_config import NNType
from ..models.sensor_control import SensorControlUpdate
from ..utils.ws_adapter import WsAdapter
from .common import (
    CameraDep,
    SensorDep,
    Mxid,
    StreamName,
    StreamServiceDep,
    NNConfigDep,
)

router = APIRouter(
    prefix="/cameras/{mxid}/streams",
    tags=["streams"],
    responses={404: {"description": "Camera not found"}},
)


@router.get("/")
def list_all_streams(camera: CameraDep):
    return {
        sensor: {"active": sensor in camera.sensors}
        for sensor in camera.all_sensors.keys()
    }


stream_router = APIRouter(
    prefix="/{stream_name}",
    tags=["streams"],
    responses={404: {"description": "Camera or stream not found"}},
)


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


@stream_router.get(
    "/still",
    response_description="Image bytes in the selected format",
    response_model=bytes,
    response_class=Response(media_type="image/*"),
)
def capture_still_image(sensor: SensorDep, format: str | None = "jpeg") -> Response:
    img_buffer = BytesIO()
    sensor.capture_still().save(img_buffer, format)

    return Response(img_buffer.getvalue(), media_type=f"image/{format}")


@stream_router.post("/nn", status_code=status.HTTP_201_CREATED, tags=["nn"])
async def deploy_neural_network(
    camera: CameraDep, stream_name: StreamName, model: UploadFile, config: NNConfigDep
):
    sensor = camera.all_sensors[stream_name]
    model_bytes = await model.read()
    blob = dai.OpenVINO.Blob(list(model_bytes))

    if config.type == NNType.Generic:
        nn_config = CameraNNConfig(sensor, blob, config.num_inference_threads)
    elif config.type == NNType.YOLO:
        nn_config = CameraNNYoloConfig(
            sensor,
            blob,
            config.num_inference_threads,
            **config.nn_config.model_dump(),
        )
    elif config.type == NNType.MobileNet:
        nn_config = CameraNNMobileNetConfig(
            sensor,
            blob,
            config.num_inference_threads,
            **config.nn_config.model_dump(),
        )

    camera.deploy_nn(nn_config)


@stream_router.delete("/nn", status_code=status.HTTP_202_ACCEPTED, tags=["nn"])
async def delete_neural_network(camera: CameraDep, stream_name: StreamName):
    camera.delete_nn(stream_name)


@stream_router.websocket("/nn")
async def get_sensor_detections(ws: WebSocket, sensor: SensorDep):
    await ws.accept()

    try:
        while True:
            detections = sensor.get_nn_detections()

            if isinstance(detections, dai.NNData):
                await ws.send_json(detections.getFirstLayerFp16())
            else:
                parsed_detections = list(
                    map(
                        lambda x: {
                            "label": x.label,
                            "confidence": x.confidence,
                            "coords": [x.xmin, x.ymin, x.xmax, x.ymax],
                        },
                        detections.detections,
                    )
                )

                await ws.send_json(parsed_detections)

            await anyio.sleep(0.001)
    except WebSocketDisconnect:
        return


@stream_router.websocket("/video")
async def get_stream_video(
    ws: WebSocket, mxid: Mxid, stream_name: StreamName, stream_service: StreamServiceDep
):
    tg = anyio.create_task_group()

    async def sleep():
        async with tg:
            tg.start_soon(anyio.sleep_forever)

    def on_close():
        tg.cancel_scope.cancel()
        stream_service.unsubscribe((mxid, stream_name), ws_adapter)

    ws_adapter = WsAdapter(ws)
    await ws_adapter.accept()
    await stream_service.subscribe((mxid, stream_name), ws_adapter, on_close)
    await sleep()

    try:
        await ws_adapter.close()
    except:
        pass


router.include_router(stream_router)
