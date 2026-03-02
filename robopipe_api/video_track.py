from aiortc import VideoStreamTrack, MediaStreamError
from aiortc.contrib.media import MediaRelay
import anyio.to_thread
from av import VideoFrame

from functools import lru_cache

from .camera.sensor.sensor_base import SensorBase
from .log import logger


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

        frame.pts, frame.time_base = await self.next_timestamp()

        return frame


@lru_cache(maxsize=1)
def video_track_factory(sensor: SensorBase) -> VideoTrack:
    return VideoTrack(sensor)


@lru_cache(maxsize=1)
def media_relay_factory(sensor: SensorBase) -> MediaRelay:
    return MediaRelay()
