import depthai as dai
from fastapi import (
    APIRouter,
    WebSocket,
    UploadFile,
    WebSocketDisconnect,
    status,
    Request,
)
from aiortc import RTCSessionDescription, RTCPeerConnection
import anyio
import anyio.to_thread
from fastapi.responses import Response

from ..camera.sensor.sensor_config import SensorConfigProperties
from ..camera.sensor.sensor_control import SensorControl
from ..models.sensor_control import SensorControlUpdate
from ..models.stream_info import StreamInfo
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
    camera: CameraDep, stream_name: StreamName, model: UploadFile, config: NNConfigDep
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

            if detections is None:
                await ws.send_json({"error": "NN queue not available"})
                await anyio.sleep(1)
                continue

            if isinstance(detections, dai.NNData):
                # v3 API: use getTensor or getFirstTensor
                try:
                    if hasattr(detections, "getFirstTensor"):
                        tensor = detections.getFirstTensor()
                    elif hasattr(detections, "getTensor"):
                        layer_names = detections.getAllLayerNames()
                        if layer_names:
                            tensor = detections.getTensor(layer_names[0])
                        else:
                            tensor = None
                    else:
                        tensor = None

                    if tensor is not None:
                        # Check if this is a segmentation mask (2D output)
                        import cv2
                        import numpy as np

                        # Reshape to 2D if needed (assumes square output like 256x256)
                        flat = tensor.flatten()
                        size = int(np.sqrt(len(flat)))
                        if size * size == len(flat):
                            # It's a segmentation mask
                            mask = flat.reshape((size, size))
                            # Convert to uint8 binary mask
                            mask_uint8 = (mask > 0.5).astype(np.uint8) * 255

                            # Find contours
                            contours, _ = cv2.findContours(
                                mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                            )

                            # Extract contour points (simplify to reduce data)
                            parsed_detections = []
                            for contour in contours:
                                # Approximate contour to reduce points
                                epsilon = 0.01 * cv2.arcLength(contour, True)
                                approx = cv2.approxPolyDP(contour, epsilon, True)
                                points = approx.reshape(-1, 2).tolist()
                                if len(points) >= 3:  # Valid polygon
                                    parsed_detections.append(points)
                        else:
                            # Not a square mask, return raw
                            parsed_detections = flat.tolist()
                    else:
                        parsed_detections = []
                except Exception as e:
                    print(f"[NN] Error processing: {e}")
                    parsed_detections = []
            else:
                parsed_detections = parse_detections(detections)

            await ws.send_json({"detections": parsed_detections})
            await anyio.sleep(0.05)  # 50ms = ~20fps max
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


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


router.include_router(stream_router)
