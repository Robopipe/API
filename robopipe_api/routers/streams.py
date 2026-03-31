import os
import tempfile

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

from robopipe_api.dashboard.dashboard_handler import (
    handle_detections,
    reset_line_crossing,
    _threshold_tracker,
)
from robopipe_api.dashboard.events_store import events_store_factory
from robopipe_api.dashboard.config_store import config_store_factory

from ..camera.sensor.sensor_config import SensorConfigProperties
from ..camera.sensor.sensor_control import SensorControl
from ..models.sensor_control import SensorControlUpdate
from ..models.stream_info import StreamInfo
from ..models.dashboard.detection_event import DetectionEvent
from ..utils.detections_parser import parse_detections
from .common import (
    CameraDep,
    EventsStoreDep,
    SensorDep,
    StreamName,
    NNConfigDep,
    DashboardConfigsListDep,
    VideoRelayDep,
    VideoTrackDep,
    WebRTCManagerDep,
    WSRelayDep,
    SyncTaskDep,
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


class JpegResponse(Response):
    media_type = "image/jpeg"


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
    response_class=JpegResponse,
    responses={
        200: {
            "content": {
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}}
            },
            "description": "Image bytes in JPEG format",
        }
    },
)
async def capture_still_image(sensor: SensorDep) -> JpegResponse:
    img = await anyio.to_thread.run_sync(sensor.capture_still)

    return JpegResponse(img.getData().tobytes())


@stream_router.get("/nn", tags=["nn"])
def get_neural_network(sensor: SensorDep):
    return sensor.nn_config


def _load_model_blob_from_bytes(
    model_bytes: bytes, filename: str
) -> "dai.OpenVINO.Blob | dai.NNArchive":
    """Load a model blob from raw bytes, handling both .blob and .tar.xz/.tar.gz formats."""
    if filename.endswith(".tar.xz") or filename.endswith(".tar.gz"):
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=filename[filename.rfind(".tar") :]
        ) as tmp:
            tmp.write(model_bytes)
            tmp_path = tmp.name
        try:
            return dai.NNArchive(tmp_path)
        finally:
            os.unlink(tmp_path)
    else:
        return dai.OpenVINO.Blob(list(model_bytes))


def _load_model_blob_from_path(
    model_path: str,
) -> "dai.OpenVINO.Blob | dai.NNArchive":
    """Load a model blob from a file path on disk."""
    if model_path.endswith(".tar.xz") or model_path.endswith(".tar.gz"):
        return dai.NNArchive(model_path)
    else:
        with open(model_path, "rb") as f:
            return dai.OpenVINO.Blob(list(f.read()))


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
    blob = _load_model_blob_from_bytes(model_bytes, filename)

    sensor.nn_config = config
    camera.deploy_nn(stream_name, blob, config)


@stream_router.delete("/nn", status_code=status.HTTP_202_ACCEPTED, tags=["nn"])
async def delete_neural_network(camera: CameraDep, stream_name: StreamName):
    camera.delete_nn(stream_name)


@stream_router.websocket("/nn")
async def get_sensor_detections(
    ws: WebSocket,
    camera: CameraDep,
    mxid: Mxid,
    stream_name: StreamName,
    relay: WSRelayDep,
):
    await ws.accept()

    def producer():
        sensor = camera.sensors.get(stream_name)
        if sensor is None:
            raise RuntimeError(f"Sensor {stream_name} no longer available")
        detections = sensor.get_nn_detections()
        seq = detections.getSequenceNum()
        parsed_detections = parse_detections(detections)
        result = handle_detections(
            sensor.dashboard_config, parsed_detections, sensor.dashboard_run_session_id
        )
        result["seq"] = seq
        return result

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
def serve_dashboard(
    request: Request, mxid: Mxid, stream_name: StreamName, sensor: SensorDep
):
    if sensor.dashboard_config is None:
        return Response("No dashboard configured for this stream", status_code=404)

    dashboard_index = (
        Path(__file__).parent.parent / "static" / "dashboard" / "index.html"
    )
    soup = BeautifulSoup(dashboard_index.read_text(), "html.parser")
    head = soup.head
    if head:
        store = config_store_factory()
        has_multiple = len(store.list_configs(mxid, stream_name)) > 1
        dashboard_config = {
            "configId": sensor.dashboard_config.id,
            "apiBase": str(request.url).rstrip("/dashboard"),
            "mxid": mxid,
            "streamName": stream_name,
            "labels": [label.model_dump() for label in sensor.dashboard_config.labels],
            "testCases": [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "severity": tc.severity,
                    "thresholds": [t.model_dump() for t in tc.thresholds],
                }
                for tc in sensor.dashboard_config.testCases
            ],
            "lineDirection": sensor.dashboard_config.lineDirection,
            "linePosition": sensor.dashboard_config.linePosition,
            "lineFlow": sensor.dashboard_config.lineFlow,
            "remoteBackendUrl": sensor.dashboard_config.remoteBackendUrl,
            "running": sensor.dashboard_run_session_id is not None,
            "hasMultipleConfigs": has_multiple,
        }
        script_tag = soup.new_tag("script")
        script_tag.string = f"""
            window.DASHBOARD_CONFIG = {json.dumps(dashboard_config)};
        """
        head.append(script_tag)

    return HTMLResponse(content=str(soup))


@stream_router.post("/dashboard")
async def set_dashboard_config(
    camera: CameraDep,
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
    configs: DashboardConfigsListDep,
    models: list[UploadFile],
):
    if len(configs) != len(models):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Number of configs ({len(configs)}) must match number of models ({len(models)})",
        )

    store = config_store_factory()
    store.clear_configs(mxid, stream_name)

    # Read all model files and store all configs
    for (dashboard_config, nn_config), model in zip(configs, models):
        model_bytes = await model.read()
        filename = model.filename or ""
        store.store_config(
            mxid, stream_name, dashboard_config, nn_config, model_bytes, filename
        )

    # Deploy the first config immediately
    first_config, first_nn_config = configs[0]
    first_stored = store.get_config(mxid, stream_name, first_config.id)
    blob = _load_model_blob_from_path(first_stored.model_path)

    sensor.nn_config = first_nn_config
    camera.deploy_nn(stream_name, blob, first_nn_config)
    sensor = camera.sensors.get(stream_name)  # Refresh after deploy
    sensor.dashboard_config = first_config

    return {
        "dashboard_url": f"/cameras/{mxid}/streams/{stream_name}/dashboard",
        "configs_count": len(configs),
    }


@stream_router.delete("/dashboard")
def delete_dashboard_config(sensor: SensorDep, mxid: Mxid, stream_name: StreamName):
    sensor.dashboard_config = None
    config_store_factory().clear_configs(mxid, stream_name)


@stream_router.get("/dashboard/configs")
def list_dashboard_configs(
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
):
    store = config_store_factory()
    configs = store.list_configs(mxid, stream_name)
    return {
        "active_config_id": sensor.active_config_id,
        "configs": [
            {"config_id": c.config_id, "config_name": c.config_name} for c in configs
        ],
    }


@stream_router.post("/dashboard/configs/{config_id}/activate")
def switch_dashboard_config(
    camera: CameraDep,
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
    config_id: int,
    events_store: EventsStoreDep,
):
    store = config_store_factory()
    stored = store.get_config(mxid, stream_name, config_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    # Stop dashboard and reset evaluation state
    if sensor.dashboard_run_session_id is not None:
        events_store.end_session(sensor.dashboard_run_session_id)
        sensor.dashboard_run_session_id = None
    if sensor.dashboard_config is not None:
        reset_line_crossing(sensor.dashboard_config.id)
        _threshold_tracker.reset(sensor.dashboard_config.id)

    # Load model from disk and deploy
    blob = _load_model_blob_from_path(stored.model_path)
    sensor.nn_config = stored.nn_config
    camera.deploy_nn(stream_name, blob, stored.nn_config)

    # Refresh sensor reference after pipeline restart
    sensor = camera.sensors.get(stream_name)
    sensor.dashboard_config = stored.dashboard_config

    return {"switched_to": config_id, "config_name": stored.config_name}


@stream_router.post("/dashboard/start")
def start_dashboard(sensor: SensorDep, events_store: EventsStoreDep):
    if sensor.dashboard_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No dashboard configured for this stream",
        )
    reset_line_crossing(sensor.dashboard_config.id)
    sensor.dashboard_run_session_id = events_store.start_session(
        sensor.dashboard_config.id
    )
    return {"running": True}


@stream_router.post("/dashboard/stop")
def stop_dashboard(sensor: SensorDep, events_store: EventsStoreDep):
    if sensor.dashboard_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No dashboard configured for this stream",
        )
    events_store.end_session(sensor.dashboard_run_session_id)
    sensor.dashboard_run_session_id = None
    return {"running": False}


@stream_router.get("/dashboard/metrics")
def get_dashboard_metrics(sensor: SensorDep, events_store: EventsStoreDep):
    if sensor.dashboard_config is None or sensor.dashboard_run_session_id is None:
        return {}

    data = {}
    data["threshold_status"] = _threshold_tracker.get_status(
        sensor.dashboard_config.id, sensor.dashboard_config.testCases
    )
    data["counters"] = events_store.get_counters(sensor.dashboard_run_session_id)

    return data


@stream_router.post("/dashboard/events", status_code=status.HTTP_202_ACCEPTED)
async def cache_detection_events(
    events: list[DetectionEvent],
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
    sync_task: SyncTaskDep,
):
    if (
        sensor.dashboard_config is None
        or sensor.dashboard_config.remoteBackendUrl is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No remote backend URL configured for this dashboard",
        )

    if sensor.dashboard_run_session_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dashboard is not running",
        )

    await anyio.to_thread.run_sync(
        lambda: events_store_factory().save_events(
            [e.model_dump() for e in events],
            mxid,
            stream_name,
            sensor.dashboard_config.remoteBackendUrl,
        )
    )
    sync_task.notify_new_events()


router.include_router(stream_router)
