import depthai as dai
from fastapi import (
    APIRouter,
    WebSocket,
    UploadFile,
    WebSocketDisconnect,
    status,
)
import anyio
from fastapi.responses import Response, StreamingResponse

from io import BytesIO
from typing import AsyncGenerator

from ..camera.sensor.sensor_config import SensorConfigProperties
from ..camera.sensor.sensor_control import SensorControl
from ..models.sensor_control import SensorControlUpdate
from ..models.stream_info import StreamInfo
from ..utils.detections_parser import parse_detections
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
def list_all_streams(camera: CameraDep) -> list[StreamInfo]:
    get_sensor_info = lambda sensor: StreamInfo(
        name=sensor, active=(sensor in camera.sensors)
    )
    sensors = list(map(get_sensor_info, camera.all_sensors.keys()))

    return sensors


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
    response_class=type[Response(media_type="image/*")],
)
def capture_still_image(sensor: SensorDep, format: str | None = "jpeg") -> Response:
    img_buffer = BytesIO()
    sensor.capture_still().save(img_buffer, format)

    return Response(img_buffer.getvalue(), media_type=f"image/{format}")


async def generate_mjpeg_frames(sensor, fps: int = 15) -> AsyncGenerator[bytes, None]:
    """Generate MJPEG frames as multipart content."""
    frame_interval = 1.0 / fps
    boundary = b"--frame\r\n"

    while True:
        try:
            # Get video frame and convert to JPEG
            video_frame = await anyio.to_thread.run_sync(sensor.get_video_frame)
            pil_image = video_frame.to_image()

            img_buffer = BytesIO()
            pil_image.save(img_buffer, "JPEG", quality=80)
            frame_data = img_buffer.getvalue()

            yield (
                boundary +
                b"Content-Type: image/jpeg\r\n" +
                f"Content-Length: {len(frame_data)}\r\n\r\n".encode() +
                frame_data +
                b"\r\n"
            )

            await anyio.sleep(frame_interval)
        except Exception as e:
            print(f"MJPEG stream error: {e}")
            break


@stream_router.get(
    "/mjpeg",
    response_class=StreamingResponse,
    responses={200: {"content": {"multipart/x-mixed-replace": {}}}},
)
async def stream_mjpeg(sensor: SensorDep, fps: int = 15):
    """Stream video as MJPEG. Works in any browser via img tag."""
    return StreamingResponse(
        generate_mjpeg_frames(sensor, fps),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@stream_router.get("/nn", tags=["nn"])
def get_neural_network(sensor: SensorDep):
    return sensor.nn_config


@stream_router.post("/nn", status_code=status.HTTP_201_CREATED, tags=["nn"])
async def deploy_neural_network(
    camera: CameraDep, stream_name: StreamName, model: UploadFile, config: NNConfigDep
):
    model_bytes = await model.read()
    filename = model.filename or ""

    # Support both .blob and .tar.xz (NNArchive) formats
    if filename.endswith(".tar.xz") or filename.endswith(".tar.gz"):
        # NNArchive requires a file path, so save temporarily
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False, suffix=filename[filename.rfind(".tar"):]) as tmp:
            tmp.write(model_bytes)
            tmp_path = tmp.name
        try:
            blob = dai.NNArchive(tmp_path)
        finally:
            os.unlink(tmp_path)
    else:
        # Assume .blob format
        blob = dai.OpenVINO.Blob(list(model_bytes))

    camera.deploy_nn(stream_name, blob, config)


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
                parsed_detections = detections.getFirstLayerFp16()
            else:
                parsed_detections = parse_detections(detections)

            await ws.send_json({"detections": parsed_detections})
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
