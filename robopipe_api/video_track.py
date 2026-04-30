import fractions
import time

from aiortc import VideoStreamTrack, MediaStreamError
from aiortc.contrib.media import MediaRelay
import anyio.to_thread
from av import VideoFrame

from functools import lru_cache

from .camera.sensor.sensor_base import SensorBase
from .log import logger

VIDEO_CLOCK_RATE = 90000
VIDEO_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)


class VideoTrack(VideoStreamTrack):
    def __init__(self, sensor: SensorBase):
        super().__init__()
        self.sensor = sensor
        self._start: float | None = None

    async def recv(self) -> VideoFrame:
        try:
            frame = await anyio.to_thread.run_sync(
                self.sensor.get_video_frame, abandon_on_cancel=True
            )
        except Exception as e:
            logger.error(f"Error in get_video_frame: {e}")
            self.stop()
            video_track_factory.cache_clear()
            media_relay_factory.cache_clear()
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


@lru_cache(maxsize=1)
def video_track_factory(sensor: SensorBase) -> VideoTrack:
    return VideoTrack(sensor)


@lru_cache(maxsize=1)
def media_relay_factory(sensor: SensorBase) -> MediaRelay:
    return MediaRelay()
