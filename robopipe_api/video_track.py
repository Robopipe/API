from aiortc import VideoStreamTrack
from aiortc.contrib.media import MediaRelay
import anyio.to_thread
from av import VideoFrame

from functools import lru_cache

from .camera.sensor.sensor_base import SensorBase


class VideoTrack(VideoStreamTrack):
    def __init__(self, sensor: SensorBase):
        super().__init__()
        self.sensor = sensor
        self._start: float | None = None

    async def recv(self) -> VideoFrame:
        frame = await anyio.to_thread.run_sync(
            self.sensor.get_video_frame, abandon_on_cancel=True
        )
        frame.pts, frame.time_base = await self.next_timestamp()

        return frame


@lru_cache(maxsize=1)
def video_track_factory(sensor: SensorBase) -> VideoTrack:
    return VideoTrack(sensor)


@lru_cache(maxsize=1)
def media_relay_factory(sensor: SensorBase) -> MediaRelay:
    return MediaRelay()
