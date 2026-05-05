import asyncio
import fractions
from collections import deque

import av
from aiortc import VideoStreamTrack, MediaStreamError
from aiortc.contrib.media import MediaRelay
import anyio.to_thread

from .camera.camera import Camera
from .log import logger

VIDEO_CLOCK_RATE = 90000
VIDEO_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)
DEFAULT_BIT_RATE = 2_000_000  # 2 Mbps — comfortable for 1080p WebRTC


class VideoTrack(VideoStreamTrack):
    """Single source track shared across all WebRTC subscribers via
    MediaRelay. Encodes raw frames *once* with a host libav x264 codec
    and yields ``av.Packet``. aiortc's RTCRtpSender detects the Packet
    (vs a Frame) and routes through ``H264Encoder.pack()`` — RTP
    packetization only, no per-PC re-encoding. So adding viewers stays
    cheap, and the timestamp burnin applied in ``get_video_frame`` is
    preserved through encode → decode."""

    def __init__(self, camera: Camera, sensor_name: str):
        super().__init__()
        self.camera = camera
        self.sensor_name = sensor_name
        self._codec: av.CodecContext | None = None
        self._packet_buffer: deque[av.Packet] = deque()
        self._next_pts: int = 0

    def _ensure_codec(self, frame: av.VideoFrame) -> av.CodecContext:
        if (
            self._codec is not None
            and self._codec.width == frame.width
            and self._codec.height == frame.height
        ):
            return self._codec

        # Frame size changed (or first frame) — (re)create the encoder.
        codec = av.CodecContext.create("libx264", "w")
        codec.width = frame.width
        codec.height = frame.height
        codec.pix_fmt = "yuv420p"
        codec.framerate = fractions.Fraction(30, 1)
        codec.time_base = VIDEO_TIME_BASE
        codec.bit_rate = DEFAULT_BIT_RATE
        codec.options = {
            "tune": "zerolatency",
            "preset": "ultrafast",
            "g": "30",  # one keyframe per ~second so new subscribers attach quickly
        }
        codec.profile = "Baseline"
        self._codec = codec
        return codec

    def _encode_one(self, frame: av.VideoFrame) -> list[av.Packet]:
        codec = self._ensure_codec(frame)
        # libx264 only encodes its configured pix_fmt (yuv420p). The source
        # is nv12 (streaming pipeline) or bgr24 (NN passthrough); reformat
        # explicitly — libav does NOT auto-convert at codec.encode() time
        # and frames silently get dropped on mismatch (blank stream).
        # nv12 → yuv420p is plane re-arrangement (Y plane unchanged), so
        # the timestamp burnin in the Y strip survives.
        if frame.format.name != "yuv420p":
            frame = frame.reformat(format="yuv420p")
        # libav demands monotonically increasing PTS in the codec's time_base
        # (90 kHz here). The source frame carries no usable PTS, so we pace
        # at 1/30 s in 90 kHz units.
        frame.pts = self._next_pts
        frame.time_base = VIDEO_TIME_BASE
        self._next_pts += VIDEO_CLOCK_RATE // 30
        packets = list(codec.encode(frame))
        for pkt in packets:
            # H264Encoder.pack() reads pkt.pts / pkt.time_base via
            # convert_timebase() — make sure they're set so the receiver
            # gets sensible RTP timestamps.
            if pkt.time_base is None:
                pkt.time_base = VIDEO_TIME_BASE
        return packets

    async def recv(self) -> av.Packet:
        # Mirror aiortc's own VideoStreamTrack.recv: bail out as soon as
        # the track has been stopped. Without this, MediaRelay's
        # __run_track loop keeps calling recv() on a "stopped" track
        # forever (it only stops on MediaStreamError), pinning a CPU
        # core polling the (now-dead) source sensor and leaving zombie
        # tasks behind every time the camera is swapped or invalidated.
        if self.readyState != "live":
            raise MediaStreamError()

        # If a previous frame produced more than one packet (SPS+PPS+IDR
        # on keyframes), drain them one-per-recv before pulling the next.
        if self._packet_buffer:
            return self._packet_buffer.popleft()

        sensor = self.camera.sensors.get(self.sensor_name)
        if sensor is None:
            await asyncio.sleep(0.01)
            sensor = self.camera.sensors.get(self.sensor_name)
            if sensor is None:
                self.stop()
                _drop_track(self.camera.mxid, self.sensor_name)
                raise MediaStreamError()

        # Pull frames + encode in a thread until we get at least one packet.
        # libx264 with tune=zerolatency emits a packet on every input frame,
        # so this normally runs once.
        def _pull_and_encode() -> list[av.Packet]:
            frame = sensor.get_video_frame()
            return self._encode_one(frame)

        try:
            while not self._packet_buffer:
                packets = await anyio.to_thread.run_sync(
                    _pull_and_encode, abandon_on_cancel=True
                )
                self._packet_buffer.extend(packets)
        except Exception as e:
            logger.error(f"Error in VideoTrack encode: {e}")
            self.stop()
            _drop_track(self.camera.mxid, self.sensor_name)
            raise MediaStreamError()

        return self._packet_buffer.popleft()


_TrackKey = tuple[str, str]
_video_tracks: dict[_TrackKey, VideoTrack] = {}
_media_relays: dict[_TrackKey, MediaRelay] = {}


def video_track_factory(camera: Camera, sensor_name: str) -> VideoTrack:
    key = (camera.mxid, sensor_name)
    track = _video_tracks.get(key)
    if track is None:
        track = VideoTrack(camera, sensor_name)
        _video_tracks[key] = track
    return track


def media_relay_factory(camera: Camera, sensor_name: str) -> MediaRelay:
    key = (camera.mxid, sensor_name)
    relay = _media_relays.get(key)
    if relay is None:
        relay = MediaRelay()
        _media_relays[key] = relay
    return relay


def _drop_track(mxid: str, sensor_name: str) -> None:
    key = (mxid, sensor_name)
    _video_tracks.pop(key, None)
    _media_relays.pop(key, None)
