import datetime
import threading

import depthai as dai
from depthai_nodes import Classifications, ImgDetectionsExtended
import numpy as np
from PIL import Image

from abc import ABC, abstractmethod
from typing import Callable
import av


from ...models.dashboard.dashboard_config import DashboardConfig
from ...models.nn_config import NNConfig
from ...utils.image import img_frame_to_video_frame
from ..pipeline.pipeline_queue_type import PipelineQueueType
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

    @property
    @abstractmethod
    def config(self) -> SensorConfigProperties: ...

    @config.setter
    @abstractmethod
    def config(self, value: SensorConfigProperties) -> SensorConfigProperties: ...

    @property
    @abstractmethod
    def control(self) -> SensorControl: ...

    @control.setter
    @abstractmethod
    def control(self, value: SensorControl) -> SensorControl: ...

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

    def __extract_img_properties(self, img: dai.ImgFrame):
        pass

    def capture_still(self) -> dai.EncodedFrame:
        still_queue = self.output_queues[PipelineQueueType.STILL]
        return still_queue.getAll()[-1]

    def get_video_frame(self) -> av.VideoFrame:
        video_queue = self.output_queues[PipelineQueueType.VIDEO]
        img_frame: dai.ImgFrame | None = video_queue.tryGet()

        if img_frame:
            self.last_frame = img_frame_to_video_frame(img_frame)
            # seq = img_frame.getSequenceNum()
            # with self._video_seq_cond:
            #     self._video_seq = seq
            #     self._video_seq_cond.notify_all()
        elif self.last_frame is None:
            img_frame = video_queue.get()
            self.last_frame = img_frame_to_video_frame(img_frame)
            # seq = img_frame.getSequenceNum()
            # with self._video_seq_cond:
            #     self._video_seq = seq
            #     self._video_seq_cond.notify_all()

        return self.last_frame

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

    def get_nn_detections(
        self,
    ) -> dai.ImgDetections | Classifications | ImgDetectionsExtended:
        nn_queue = self.output_queues[PipelineQueueType.NN]
        detections: dai.ImgDetections | Classifications | None = nn_queue.tryGet()

        if detections is None:
            detections = nn_queue.get(timeout=datetime.timedelta(seconds=2))
            if detections is None:
                raise TimeoutError("NN queue get() timed out")

        # Wait until the video track has dispatched the frame that
        # corresponds to this detection, so both leave the server
        # at approximately the same time.
        # det_seq = detections.getSequenceNum()
        # with self._video_seq_cond:
        #     self._video_seq_cond.wait_for(
        #         lambda: self._video_seq >= det_seq,
        #         timeout=0.5,
        #     )

        return detections
