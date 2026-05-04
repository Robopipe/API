import asyncio
import fractions
import time

from aiortc import VideoStreamTrack, MediaStreamError
from aiortc.contrib.media import MediaRelay
import anyio.to_thread
from av import VideoFrame

from .camera.camera import Camera
from .log import logger

VIDEO_CLOCK_RATE = 90000
VIDEO_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)


class VideoTrack(VideoStreamTrack):
    def __init__(self, camera: Camera, sensor_name: str):
        super().__init__()
        self.camera = camera
        self.sensor_name = sensor_name
        self._start: float | None = None

    async def recv(self) -> VideoFrame:
        sensor = self.camera.sensors.get(self.sensor_name)
        if sensor is None:
            # Sensor briefly absent during reload_sensors() — wait one tick and retry.
            await asyncio.sleep(0.01)
            sensor = self.camera.sensors.get(self.sensor_name)
            if sensor is None:
                self.stop()
                _drop_track(self.camera.mxid, self.sensor_name)
                raise MediaStreamError()

        try:
            frame = await anyio.to_thread.run_sync(
                sensor.get_video_frame, abandon_on_cancel=True
            )
        except Exception as e:
            logger.error(f"Error in get_video_frame: {e}")
            self.stop()
            _drop_track(self.camera.mxid, self.sensor_name)
            raise MediaStreamError()

        # PTS from wall clock so a slow recv shrinks the framerate instead of
        # silently lagging the stream. aiortc's default next_timestamp() advances
        # PTS at a fixed nominal 30 FPS regardless of how long recv() actually
        # took, which compounds into unbounded drift between encoder PTS and
        # real time and eventually freezes the receiver.
        now = time.monotonic()
        if self._start is None:
            self._start = now
        frame.pts = int((now - self._start) * VIDEO_CLOCK_RATE)
        frame.time_base = VIDEO_TIME_BASE

        return frame


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
