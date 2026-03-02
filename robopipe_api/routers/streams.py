import depthai as dai
from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    UploadFile,
    status,
    Request,
)
from aiortc import RTCSessionDescription, RTCPeerConnection
import anyio
import anyio.to_thread
from fastapi.responses import Response, HTMLResponse
from pathlib import Path
from bs4 import BeautifulSoup
import json

from robopipe_api.dashboard.dashboard_handler import handle_detections

from ..camera.sensor.sensor_config import SensorConfigProperties
from ..camera.sensor.sensor_control import SensorControl
from ..models.sensor_control import SensorControlUpdate
from ..models.stream_info import StreamInfo
from ..models.dashboard.dashboard_config import DashboardConfig
from ..utils.detections_parser import parse_detections
from .common import (
    CameraDep,
    SensorDep,
    StreamName,
    NNConfigDep,
    VideoRelayDep,
    VideoRelayDep,
    VideoTrackDep,
    WebRTCManagerDep,
    WSRelayDep,
    Mxid,
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
    response_description="Image bytes in JPEG format",
    response_model=bytes,
    response_class=type[Response(media_type="image/jpeg")],
)
async def capture_still_image(sensor: SensorDep) -> Response:
    img = await anyio.to_thread.run_sync(sensor.capture_still)

    return Response(img.getData().tobytes(), media_type="image/jpeg")


@stream_router.get("/nn", tags=["nn"])
def get_neural_network(sensor: SensorDep):
    return sensor.nn_config


@stream_router.post("/nn", status_code=status.HTTP_201_CREATED, tags=["nn"])
async def deploy_neural_network(
    camera: CameraDep,
    stream_name: StreamName,
    model: UploadFile,
    config: NNConfigDep,
    sensor: SensorDep,
):
    model_bytes = await model.read()
    filename = model.filename or ""

    # Support both .blob and .tar.xz (NNArchive) formats
    if filename.endswith(".tar.xz") or filename.endswith(".tar.gz"):
        # NNArchive requires a file path, so save temporarily
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=filename[filename.rfind(".tar") :]
        ) as tmp:
            tmp.write(model_bytes)
            tmp_path = tmp.name
        try:
            blob = dai.NNArchive(tmp_path)
        finally:
            os.unlink(tmp_path)
    else:
        # Assume .blob format
        blob = dai.OpenVINO.Blob(list(model_bytes))

    sensor.nn_config = config
    camera.deploy_nn(stream_name, blob, config)


@stream_router.delete("/nn", status_code=status.HTTP_202_ACCEPTED, tags=["nn"])
async def delete_neural_network(camera: CameraDep, stream_name: StreamName):
    camera.delete_nn(stream_name)


@stream_router.websocket("/nn")
async def get_sensor_detections(
    ws: WebSocket,
    sensor: SensorDep,
    mxid: Mxid,
    stream_name: StreamName,
    relay: WSRelayDep,
):
    await ws.accept()

    def producer():
        detections = sensor.get_nn_detections()
        parsed_detections = parse_detections(detections)
        return handle_detections(sensor.dashboard_config, parsed_detections)

    await relay.subscribe(key=(mxid, stream_name, "nn"), ws=ws, producer=producer)


@stream_router.post("/video")
async def stream_video_offer(
    req: Request,
    video_track: VideoTrackDep,
    video_relay: VideoRelayDep,
    webrtc_manager: WebRTCManagerDep,
):
    params = await req.json()
    rtc_offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    pc = RTCPeerConnection()
    webrtc_manager.add_pc(pc)
    pc.addTrack(video_relay.subscribe(video_track))
    await pc.setRemoteDescription(rtc_offer)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        if pc.iceConnectionState in ("failed", "disconnected", "closed"):
            await webrtc_manager.remove_pc(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ("failed", "disconnected", "closed"):
            await webrtc_manager.remove_pc(pc)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


@stream_router.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard(request: Request, sensor: SensorDep):
    if sensor.dashboard_config is None:
        return Response("No dashboard configured for this stream", status_code=404)

    dashboard_index = (
        Path(__file__).parent.parent / "static" / "dashboard" / "index.html"
    )
    soup = BeautifulSoup(dashboard_index.read_text(), "html.parser")
    head = soup.head
    if head:
        dashboard_config = {
            "apiBase": str(request.url).rstrip("/dashboard"),
            "labels": [label.model_dump() for label in sensor.dashboard_config.labels],
            "dashboardItems": [
                {
                    "id": item.id,
                    "name": item.name,
                    "severity": item.severity,
                }
                for item in sensor.dashboard_config.items
            ],
        }
        script_tag = soup.new_tag("script")
        script_tag.string = f"""
            window.DASHBOARD_CONFIG = {json.dumps(dashboard_config)};
        """
        head.append(script_tag)

    return HTMLResponse(content=str(soup))


@stream_router.post("/dashboard")
def set_dashboard_config(
    config: DashboardConfig, mxid: Mxid, stream_name: StreamName, sensor: SensorDep
):
    if sensor.nn_config is None:
        raise HTTPException(
            status_code=400,
            detail="Dashboard can only be set for streams with deployed neural networks",
        )

    sensor.dashboard_config = config

    return {"dashboard_url": f"/cameras/{mxid}/streams/{stream_name}/dashboard"}


@stream_router.delete("/dashboard")
def delete_dashboard_config(sensor: SensorDep):
    sensor.dashboard_config = None


router.include_router(stream_router)
