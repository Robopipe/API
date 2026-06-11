import datetime
import threading
from collections import OrderedDict

import depthai as dai
from depthai_nodes import Classifications, ImgDetectionsExtended
import numpy as np
from PIL import Image

from abc import ABC, abstractmethod
from typing import Callable
import av


from ...models.dashboard.dashboard_config import DashboardConfig
from ...models.detection.bbox_detection import BBoxDetection, BBoxDetections
from ...models.nn_config import NNConfig
from ...models.sahi_config import SAHIConfig
from ...utils.detections_parser import parse_detections
from ...utils.image import img_frame_to_video_frame
from ...utils.timestamp_burnin import burn_timestamp
from ...ws_relay import ProducerTerminated
from ..exceptions import VideoStreamEnded
from ..pipeline.pipeline_queue_type import PipelineQueueType
from ..sahi import Tile, remap_tile_detections, nms_merge
from ...models.still_config import StillConfig
from .sensor_config import SensorConfigProperties
from .sensor_control import SensorControl


class SensorBase(ABC):
    def __init__(
        self,
        input_queues: dict[PipelineQueueType, dai.InputQueue],
        output_queues: dict[PipelineQueueType, dai.MessageQueue],
        restart_pipeline: Callable[[], None],
    ):
        self.input_queues = input_queues
        self.output_queues = output_queues
        self.restart_pipeline = restart_pipeline
        self._nn_config = None
        self._dashboard_config = None
        self._dashboard_run_session_id: int | None = None
        self._active_config_id = None
        self.last_frame: av.VideoFrame | None = None
        self._video_seq: int = -1
        self._video_seq_cond = threading.Condition()
        self._frame_buffer: OrderedDict[int, av.VideoFrame] = OrderedDict()
        self._frame_buffer_lock = threading.Lock()
        self._frame_buffer_max = 60

        # SAHI state
        self._sahi_tile_queue: dai.MessageQueue | None = None
        self._sahi_manip_cfg: dai.InputQueue | None = None
        self._sahi_tiles: list[Tile] = []
        self._sahi_config: SAHIConfig | None = None
        self._sahi_model_input_size: tuple[int, int] = (0, 0)
        self._sahi_tile_index: int = 0
        self._sahi_tile_cache: list[list[BBoxDetection]] = []

    @property
    @abstractmethod
    def config(self) -> StillConfig: ...

    @config.setter
    @abstractmethod
    def config(self, value: StillConfig) -> None: ...

    @property
    @abstractmethod
    def control(self) -> SensorControl: ...

    @control.setter
    @abstractmethod
    def control(self, value: SensorControl) -> SensorControl: ...

    @property
    @abstractmethod
    def features(self) -> dai.CameraFeatures: ...

    @property
    def nn_config(self) -> NNConfig | None:
        return self._nn_config

    @nn_config.setter
    def nn_config(self, value: NNConfig | None) -> NNConfig | None:
        self._nn_config = value
        return self._nn_config

    @property
    def dashboard_config(self) -> DashboardConfig | None:
        return self._dashboard_config

    @dashboard_config.setter
    def dashboard_config(self, value: DashboardConfig | None):
        self._dashboard_config = value
        self._dashboard_run_session_id = None
        self._active_config_id = value.id if value else None

    @property
    def active_config_id(self) -> int | None:
        return self._active_config_id

    @property
    def dashboard_run_session_id(self) -> int | None:
        return self._dashboard_run_session_id

    @dashboard_run_session_id.setter
    def dashboard_run_session_id(self, value: int | None):
        self._dashboard_run_session_id = value

    def on_frame(self, img: dai.ImgFrame) -> None:
        pass

    def refresh_control_from_frame(self) -> None:
        pass

    def capture_still(self) -> bytes:
        still_queue = self.output_queues[PipelineQueueType.STILL]
        return still_queue.getAll()[-1].getData().tobytes()

    def get_video_frame(self) -> av.VideoFrame:
        video_queue = self.output_queues[PipelineQueueType.VIDEO]
        try:
            img_frame: dai.ImgFrame | None = video_queue.tryGet()
        except Exception as e:
            # The dai.Device backing this queue was closed (pipeline restart or
            # replay video reached EOF). Raise VideoStreamEnded so consumers
            # tear down rather than loop on the cached `last_frame`.
            raise VideoStreamEnded("video queue closed") from e

        if img_frame:
            self.on_frame(img_frame)
            ts_us = int(img_frame.getTimestampDevice().total_seconds() * 1_000_000)
            video_frame = img_frame_to_video_frame(img_frame)
            if self.nn_config is not None:
                video_frame = burn_timestamp(video_frame, ts_us)
            self.last_frame = video_frame
            self._buffer_frame(ts_us, self.last_frame)
        elif self.last_frame is None:
            try:
                img_frame = video_queue.get(
                    timeout=datetime.timedelta(milliseconds=1500)
                )
            except Exception as e:
                raise VideoStreamEnded("video queue closed") from e
            if img_frame is None:
                raise VideoStreamEnded("video queue empty")
            self.on_frame(img_frame)
            ts_us = int(img_frame.getTimestampDevice().total_seconds() * 1_000_000)
            video_frame = img_frame_to_video_frame(img_frame)
            if self.nn_config is not None:
                video_frame = burn_timestamp(video_frame, ts_us)
            self.last_frame = video_frame
            self._buffer_frame(ts_us, self.last_frame)
        else:
            ret = self.last_frame
            self.last_frame = None
            return ret

        return self.last_frame

    def _publish_video_seq(self, seq: int) -> None:
        """Notify any waiters that a video frame with this seq has been
        dispatched to the encoder. Used by `get_nn_detections` to hold the
        detection broadcast until the matching frame is on its way out, so
        client-side ts matching doesn't drift."""
        with self._video_seq_cond:
            if seq > self._video_seq:
                self._video_seq = seq
                self._video_seq_cond.notify_all()

    def _buffer_frame(self, ts_us: int, frame: av.VideoFrame) -> None:
        with self._frame_buffer_lock:
            self._frame_buffer[ts_us] = frame
            while len(self._frame_buffer) > self._frame_buffer_max:
                self._frame_buffer.popitem(last=False)

    def get_frame_by_ts(self, ts_us: int) -> av.VideoFrame | None:
        """Return the buffered frame whose ts_us matches exactly, else last_frame."""
        with self._frame_buffer_lock:
            frame = self._frame_buffer.get(ts_us)
        return frame if frame is not None else self.last_frame

    def _try_pull_passthrough(self, ts_us_hint: int) -> None:
        """Drain the VIDEO queue, buffering each frame, until the frame matching
        ``ts_us_hint`` is found or the queue is empty.

        Called by the NN WS producer right after reading a detection so the
        commit-picture renderer can get the exact passthrough frame via
        ``get_frame_by_ts``. Does NOT call ``on_frame`` — that side-effect is
        reserved for the encoder's ``get_video_frame`` path.
        """
        video_queue = self.output_queues.get(PipelineQueueType.VIDEO)
        if video_queue is None:
            return
        for _ in range(8):  # VIDEO queue maxSize=4; 8 is a generous safety cap
            try:
                img_frame = video_queue.tryGet()
            except Exception:
                return
            if img_frame is None:
                return
            ts_us = int(img_frame.getTimestampDevice().total_seconds() * 1_000_000)
            frame = burn_timestamp(img_frame_to_video_frame(img_frame), ts_us)
            self.last_frame = frame
            self._buffer_frame(ts_us, frame)
            if ts_us == ts_us_hint:
                return

    def get_nn_frame(self):
        try:
            nn_queue = self.output_queues.get(PipelineQueueType.NN)
            passthrough_queue = self.output_queues.get(PipelineQueueType.NN_PASSTHROUGH)

            if nn_queue is None or passthrough_queue is None:
                return None

            detections = nn_queue.get()
            passthrough = passthrough_queue.get()
        except Exception as e:
            return None

        # Avoid unnecessary copy if already uint8
        frame_data = passthrough.getFrame()
        if frame_data.dtype != np.uint8:
            frame_data = frame_data.astype(np.uint8)

        passthrough_frame = Image.fromarray(np.transpose(frame_data, (1, 2, 0)), "RGB")

        return (passthrough_frame, detections)

    @property
    def sahi_enabled(self) -> bool:
        return (
            self._sahi_config is not None
            and self._sahi_tile_queue is not None
            and len(self._sahi_tiles) > 0
        )

    def get_nn_detections(
        self,
    ) -> dai.ImgDetections | Classifications | ImgDetectionsExtended:
        # Soft fail when the NN pipeline has been removed (e.g. DELETE /nn
        # while a detections WS is still connected). Raising ProducerTerminated
        # instead of KeyError lets ws_relay's _produce loop exit cleanly
        # rather than log-spamming at 10Hz.
        nn_queue = self.output_queues.get(PipelineQueueType.NN)
        if nn_queue is None:
            raise ProducerTerminated()

        try:
            detections: dai.ImgDetections | Classifications | None = nn_queue.tryGet()
            if detections is None:
                detections = nn_queue.get(timeout=datetime.timedelta(seconds=2))
        except Exception as e:
            raise ProducerTerminated() from e

        if detections is None:
            raise TimeoutError("NN queue get() timed out")

        # Wait until the video track has dispatched the frame that
        # corresponds to this detection, so both leave the server at
        # approximately the same time. Without this, the WebRTC encoder
        # and the WS detection producer can land on different NN cycles
        # — their ts values diverge and the client matcher breaks.
        # The 0.5 s timeout keeps detection-only consumers (no video)
        # from blocking forever.
        det_seq = detections.getSequenceNum()
        # with self._video_seq_cond:
        #     self._video_seq_cond.wait_for(
        #         lambda: self._video_seq >= det_seq,
        #         timeout=0.5,
        #     )

        return detections

    def get_merged_sahi_detections(self) -> tuple[BBoxDetections, int, dict]:
        # Full-frame detections (blocking — tiles should be ready after this)
        full_frame_raw = self.get_nn_detections()
        seq = full_frame_raw.getSequenceNum()
        full_frame_parsed = parse_detections(full_frame_raw)
        full_frame_count = len(full_frame_parsed.detections)
        all_dets = list(full_frame_parsed.detections)

        # Grab the tile detection for the current tile (non-blocking)
        try:
            tile_raw = self._sahi_tile_queue.tryGet()
        except Exception as e:
            raise ProducerTerminated() from e
        tile_got_result = tile_raw is not None
        if tile_raw is not None:
            tile = self._sahi_tiles[self._sahi_tile_index]
            tile_parsed = parse_detections(tile_raw)
            remapped = remap_tile_detections(
                BBoxDetections(detections=list(tile_parsed.detections)),
                tile,
            )
            self._sahi_tile_cache[self._sahi_tile_index] = remapped

        # Advance to next tile and reconfigure ImageManip crop
        self._sahi_tile_index = (self._sahi_tile_index + 1) % len(self._sahi_tiles)
        next_tile = self._sahi_tiles[self._sahi_tile_index]
        cfg = dai.ImageManipConfig()
        crop_rect = dai.Rect(
            dai.Point2f(next_tile.x1, next_tile.y1),
            dai.Point2f(next_tile.x2, next_tile.y2),
        )
        cfg.addCrop(crop_rect, True)
        cfg.setOutputSize(
            self._sahi_model_input_size[0],
            self._sahi_model_input_size[1],
        )
        cfg.setFrameType(dai.ImgFrame.Type.BGR888i)
        self._sahi_manip_cfg.send(cfg)

        # Merge full-frame + all cached tile detections
        tile_det_count = 0
        for cached in self._sahi_tile_cache:
            all_dets.extend(cached)
            tile_det_count += len(cached)

        merged = nms_merge(all_dets, self._sahi_config.nms_iou_threshold)
        sahi_info = {
            "full_frame_dets": full_frame_count,
            "tile_dets_cached": tile_det_count,
            "merged_dets": len(merged),
            "tile_nn_produced": tile_got_result,
            "current_tile": self._sahi_tile_index,
            "total_tiles": len(self._sahi_tiles),
        }
        return BBoxDetections(detections=merged), seq, sahi_info
