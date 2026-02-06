import depthai as dai
from fastapi import (
    APIRouter,
    WebSocket,
    UploadFile,
    WebSocketDisconnect,
    status,
    Request
)
import anyio
from fastapi.responses import Response, StreamingResponse

from io import BytesIO
from typing import AsyncGenerator

from robopipe_api.camera.sensor.sensor import Sensor

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


async def generate_mjpeg_frames(
    sensor,
    fps: int = 15,
    quality: int = 50,
    scale: float = 0.8,
) -> AsyncGenerator[bytes, None]:
    """Generate MJPEG frames as multipart content.

    Args:
        sensor: The camera sensor
        fps: Target frames per second
        quality: JPEG quality 1-100 (not used, frame_data is pre-encoded)
        scale: Resolution scale 0.1-1.0 (not used, frame_data is pre-encoded)
    """
    import numpy as np
    
    frame_interval = 1.0 / fps
    boundary = b"--frame\r\n"

    try:
        while True:
            try:
                # Get video frame (already JPEG encoded)
                video_frames = await anyio.to_thread.run_sync(sensor.get_video_frame)
                for video_frame in video_frames:
                    frame_data = video_frame.getData()
                    
                    # Convert ndarray to bytes if needed
                    if isinstance(frame_data, np.ndarray):
                        frame_data = frame_data.tobytes()

                    yield (
                        boundary +
                        b"Content-Type: image/jpeg\r\n" +
                        f"Content-Length: {len(frame_data)}\r\n\r\n".encode() +
                        frame_data +
                        b"\r\n"
                    )

                await anyio.sleep(frame_interval)
            except GeneratorExit:
                break
            except Exception as e:
                print(f"MJPEG stream error: {e}")
                break
    finally:
        # Generator cleanup
        pass

@stream_router.get(
    "/mjpeg",
    response_class=StreamingResponse,
    responses={200: {"content": {"multipart/x-mixed-replace": {}}}},
)
async def stream_mjpeg(
    sensor: SensorDep,
    fps: int = 15,
    quality: int = 50,
    scale: float = 0.8,
):
    """Stream video as MJPEG. Works in any browser via img tag.

    Query params:
        fps: Target frame rate (default 15)
        quality: JPEG quality 1-100 (default 50, lower = faster/smaller)
        scale: Resolution scale 0.1-1.0 (default 1.0, lower = faster/smaller)

    Example for low latency: /mjpeg?fps=30&quality=30&scale=0.5
    """
    # Clamp values to valid ranges
    quality = max(1, min(100, quality))
    scale = max(0.1, min(1.0, scale))

    return StreamingResponse(
        generate_mjpeg_frames(sensor, fps, quality, scale),
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

            if detections is None:
                await ws.send_json({"error": "NN queue not available"})
                await anyio.sleep(1)
                continue

            if isinstance(detections, dai.NNData):
                # v3 API: use getTensor or getFirstTensor
                try:
                    if hasattr(detections, 'getFirstTensor'):
                        tensor = detections.getFirstTensor()
                    elif hasattr(detections, 'getTensor'):
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
                            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

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


import numpy as np
import av
from fractions import Fraction
from aiortc import VideoStreamTrack, RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.codecs import h264
from aiortc.mediastreams import VIDEO_CLOCK_RATE, VIDEO_TIME_BASE

# Keep references to peer connections so they aren't garbage-collected
_peer_connections: set[RTCPeerConnection] = set()


class ColorCycleTrack(VideoStreamTrack):
    """
    Example VideoTrack that generates solid RGB colour frames.
    Cycles through Red → Green → Blue, shifting colour every second
    at the configured frame-rate.
    """

    kind = "video"

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30):
        super().__init__()
        self.width = width
        self.height = height
        self.fps = fps
        self._frame_count = 0

        # Pre-build three solid-colour frames (RGB uint8)
        self._colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (0, 255, 255),  # Cyan
            (255, 0, 255),  # Magenta
        ]

    async def recv(self) -> av.VideoFrame:
        pts, time_base = await self.next_timestamp()

        # Pick colour based on elapsed seconds
        color_idx = (self._frame_count // self.fps) % len(self._colors)
        r, g, b = self._colors[color_idx]
        self._frame_count += 1

        # Build an RGB24 numpy array and wrap it as an av.VideoFrame
        data = np.empty((self.height, self.width, 3), dtype=np.uint8)
        data[:, :, 0] = r
        data[:, :, 1] = g
        data[:, :, 2] = b

        frame = av.VideoFrame.from_ndarray(data, format="rgb24")
        frame.pts = pts
        frame.time_base = time_base
        return frame


class SensorVideoTrack(VideoStreamTrack):
    """
    VideoTrack that forwards hardware-encoded H.264 frames from the camera
    sensor directly as av.Packets.  Because the DepthAI pipeline already
    contains a VideoEncoder node outputting H.264 baseline NALs, we skip
    aiortc's software encoder entirely (the sender calls encoder.pack()
    instead of encoder.encode()), which is dramatically faster.

    Frame timing is driven by the camera hardware — we do NOT use
    next_timestamp()'s asyncio.sleep pacing.  Instead a background thread
    pushes each frame into an asyncio.Queue the moment it arrives from the
    HW encoder, and recv() awaits that queue.  This keeps the event-loop
    free and matches the camera's native frame rate exactly.
    """

    kind = "video"

    def __init__(self, sensor: Sensor):
        super().__init__()
        self.sensor = sensor
        self._frame_count = 0
        self._start: float | None = None

        import threading, asyncio
        # Single-slot queue: if recv() is slow, we keep only the newest frame.
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2)
        self._loop = asyncio.get_event_loop()
        self._running = True
        self._thread = threading.Thread(target=self._poll_frames, daemon=True)
        self._thread.start()

    def _poll_frames(self):
        """Continuously grab frames from the HW encoder queue and push them
        into the async queue that recv() awaits."""
        while self._running:
            try:
                frame = self.sensor.get_video_frame()
                data = bytes(frame.getData())
                # If queue is full, drop the oldest to make room for the newest
                if self._queue.full():
                    try:
                        self._queue.get_nowait()
                    except Exception:
                        pass
                self._loop.call_soon_threadsafe(self._queue.put_nowait, data)
            except Exception:
                import time
                time.sleep(0.005)

    def stop(self):
        self._running = False

    async def recv(self) -> av.Packet:
        if self.readyState != "live":
            raise Exception("Track ended")

        # Wait for the next frame from the HW encoder (no artificial pacing).
        data = await self._queue.get()

        # Compute PTS from wall-clock so RTP timestamps stay correct.
        import time as _time
        now = _time.time()
        if self._start is None:
            self._start = now
            self._timestamp = 0
        else:
            self._timestamp = int((now - self._start) * VIDEO_CLOCK_RATE)

        packet = av.Packet(data)
        packet.pts = self._timestamp
        packet.time_base = VIDEO_TIME_BASE
        packet.is_keyframe = self._frame_count == 0
        self._frame_count += 1

        return packet


@stream_router.post("/rtc")
async def negotiate_stream_offer(request: Request, sensor: SensorDep):
    import json

    offer = await request.json()

    # Filter the incoming offer SDP to only keep H.264, so aiortc
    # negotiates H.264 from the start (not VP8)
    forced_sdp = _force_h264_sdp(offer["sdp"])
    offer_desc = RTCSessionDescription(sdp=forced_sdp, type=offer["type"])

    pc = RTCPeerConnection()
    _peer_connections.add(pc)

    # ── Swap tracks here ─────────────────────────────────────────────
    # Use ColorCycleTrack() for a quick test (no camera needed):
    # track = ColorCycleTrack(width=640, height=480, fps=30)
    #
    # Use SensorVideoTrack(sensor) for real camera frames:
    track = SensorVideoTrack(sensor)
    # ─────────────────────────────────────────────────────────────────

    pc.addTrack(track)

    @pc.on("connectionstatechange")
    async def on_connection_state_change():
        if pc.connectionState in ("failed", "closed"):
            if hasattr(track, 'stop'):
                track.stop()
            await pc.close()
            _peer_connections.discard(pc)

    await pc.setRemoteDescription(offer_desc)

    # Force H.264 by filtering the SDP: remove all video codecs except H264
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Rewrite the answer SDP to keep only H.264 video codec
    filtered_sdp = _force_h264_sdp(pc.localDescription.sdp)

    return Response(
        json.dumps({"sdp": filtered_sdp, "type": pc.localDescription.type}),
        media_type="application/json"
    )


def _force_h264_sdp(sdp: str) -> str:
    """
    Rewrite an SDP answer to only advertise H.264 for video.
    Strips VP8 / VP9 / AV1 payload types from m=video lines
    and removes their associated rtpmap / fmtp / rtcp-fb lines.
    """
    import re

    lines = sdp.splitlines()
    result = []
    in_video = False
    h264_pts: set[str] = set()
    all_video_pts: set[str] = set()

    # First pass: find H.264 payload types
    for line in lines:
        if line.startswith("m=video"):
            in_video = True
        elif line.startswith("m="):
            in_video = False

        if in_video:
            # a=rtpmap:<pt> H264/90000
            m = re.match(r"a=rtpmap:(\d+)\s+H264/", line)
            if m:
                h264_pts.add(m.group(1))

    # Second pass: filter
    in_video = False
    for line in lines:
        if line.startswith("m=video"):
            in_video = True
            # Rewrite m=video line to only include H.264 payload types
            parts = line.split()
            # m=video <port> <proto> <pt1> <pt2> ...
            header = parts[:3]
            pts = parts[3:]
            # Keep only H.264 pts (if we found any; otherwise keep original)
            if h264_pts:
                filtered_pts = [pt for pt in pts if pt in h264_pts]
                if filtered_pts:
                    result.append(" ".join(header + filtered_pts))
                    continue
            result.append(line)
            continue
        elif line.startswith("m="):
            in_video = False

        if in_video:
            # Drop rtpmap / fmtp / rtcp-fb lines for non-H264 payload types
            m = re.match(r"a=(?:rtpmap|fmtp|rtcp-fb):(\d+)\s", line)
            if m and m.group(1) not in h264_pts:
                continue

        result.append(line)

    return "\n".join(result)


router.include_router(stream_router)
