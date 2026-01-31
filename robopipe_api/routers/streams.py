import av
import depthai as dai
from fastapi import (
    APIRouter,
    WebSocket,
    UploadFile,
    WebSocketDisconnect,
    status,
    Request,
)
import anyio
import numpy as np
from fastapi.responses import Response
from aiortc import (
    RTCSessionDescription,
    RTCPeerConnection,
    VideoStreamTrack,
    RTCRtpCodecCapability,
    RTCConfiguration,
)

from io import BytesIO

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


pcs = set()

from aiortc.codecs import get_encoder
from aiortc.codecs.h264 import H264Encoder

# Monkey-patch the H264 encoder to use low-latency settings
_original_init = H264Encoder.__init__


def hw_accelerated_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)

    # Try to use hardware encoder
    if hasattr(self, "codec") and self.codec:
        # Try different hardware encoders in order of preference
        hw_encoders = ["h264_nvenc", "h264_qsv", "h264_videotoolbox", "h264_vaapi"]

        for hw_codec in hw_encoders:
            try:
                # Check if hardware encoder is available
                test_codec = av.codec.Codec(hw_codec, "w")

                # Replace software encoder with hardware
                old_codec = self.codec
                self.codec = av.CodecContext.create(hw_codec, "w")
                self.codec.width = old_codec.width
                self.codec.height = old_codec.height
                self.codec.pix_fmt = "yuv420p"
                self.codec.time_base = old_codec.time_base
                self.codec.framerate = old_codec.framerate
                self.codec.bit_rate = old_codec.bit_rate

                # Hardware-specific low-latency options
                if "nvenc" in hw_codec:
                    self.codec.options = {
                        "preset": "llhp",  # Low-latency high performance
                        "tune": "ull",  # Ultra low latency
                        "zerolatency": "1",
                        "delay": "0",
                        "rc": "cbr",
                        "bf": "0",
                    }
                elif "qsv" in hw_codec:
                    self.codec.options = {
                        "preset": "veryfast",
                        "async_depth": "1",
                        "low_power": "1",
                    }
                elif "videotoolbox" in hw_codec:
                    self.codec.options = {
                        "realtime": "1",
                    }
                else:
                    self.codec.options = {
                        "preset": "ultrafast",
                        "tune": "zerolatency",
                        "bf": "0",
                    }

                print(f"Using hardware encoder: {hw_codec}")
                break

            except:
                continue
        else:
            # Fallback to software with aggressive settings
            self.codec.options = {
                "preset": "ultrafast",
                "tune": "zerolatency",
                "bf": "0",
                "refs": "1",
                "sc_threshold": "0",
                "rc-lookahead": "0",
            }
            print("Using software encoder (h264)")


H264Encoder.__init__ = hw_accelerated_init


@stream_router.post("/video-rtc")
async def negotiate_stream_offer(request: Request, sensor: SensorDep):
    import fractions

    class VideoTrack(VideoStreamTrack):
        def __init__(self, sensor: SensorDep):
            super().__init__()
            self.sensor = sensor
            self.counter = 0

        async def recv(self):
            pts, time_base = await self.next_timestamp()
            self.counter += 1

            video_frame = self.sensor.get_video_frame()
            video_frame.pts = pts  # CHANGED: Use actual PTS from next_timestamp()
            video_frame.time_base = time_base  # CHANGED: Use actual time_base

            return video_frame

    params = await request.json()
    pc = RTCPeerConnection()
    pcs.add(pc)

    offer = RTCSessionDescription(
        sdp=params["sdp"],
        type=params["type"],
    )

    await pc.setRemoteDescription(offer)

    video_transceiver = None
    for t in pc.getTransceivers():
        if t.kind == "video":
            video_transceiver = t
            break

    if video_transceiver is None:
        raise RuntimeError("Offer does not contain a video m-line")

    video_transceiver.direction = "sendonly"

    # OPTIMIZED CODEC SETTINGS FOR MINIMUM LATENCY
    video_transceiver.setCodecPreferences(
        [
            RTCRtpCodecCapability(
                mimeType="video/H264",
                clockRate=90000,
                channels=None,
                parameters={
                    "profile-level-id": "42e01f",  # Baseline profile (good)
                    "packetization-mode": "1",
                    "level-asymmetry-allowed": "1",
                },
            )
        ]
    )

    # CRITICAL: Configure sender parameters for low latency
    video_transceiver.sender.replaceTrack(VideoTrack(sensor))

    # Modify SDP for ultra-low latency before creating answer
    answer = await pc.createAnswer()

    # OPTIMIZATION: Inject low-latency parameters into SDP
    modified_sdp = modify_sdp_for_low_latency(answer.sdp)
    answer = RTCSessionDescription(sdp=modified_sdp, type=answer.type)

    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    }


def modify_sdp_for_low_latency(sdp: str) -> str:
    """Inject ultra-low latency parameters into SDP"""
    lines = sdp.split("\r\n")
    new_lines = []

    for line in lines:
        new_lines.append(line)

        # Add low-latency H.264 encoding parameters
        if line.startswith("a=fmtp:") and "H264" in line:
            # Extract the payload type
            parts = line.split(" ", 1)
            if len(parts) == 2:
                payload_type = parts[0].split(":")[1]
                params = parts[1]

                # Add critical low-latency parameters
                low_latency_params = [
                    "x-google-start-bitrate=2000",  # Start at reasonable bitrate
                    "x-google-min-bitrate=500",
                    "x-google-max-bitrate=4000",
                ]

                # Combine existing and new parameters
                new_lines[-1] = (
                    f"a=fmtp:{payload_type} {params};{';'.join(low_latency_params)}"
                )

    return "\r\n".join(new_lines)


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


@stream_router.get("/nn", tags=["nn"])
def get_neural_network(sensor: SensorDep):
    return sensor.nn_config


@stream_router.post("/nn", status_code=status.HTTP_201_CREATED, tags=["nn"])
async def deploy_neural_network(
    camera: CameraDep, stream_name: StreamName, model: UploadFile, config: NNConfigDep
):
    model_bytes = await model.read()
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
