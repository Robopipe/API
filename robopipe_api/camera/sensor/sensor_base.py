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
        self.last_frame: av.VideoFrame | None = None

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
        return self._dashboard_config

    def __extract_img_properties(self, img: dai.ImgFrame):
        pass

    def capture_still(self) -> dai.EncodedFrame:
        still_queue = self.output_queues[PipelineQueueType.STILL]
        return still_queue.getAll()[-1]

    def get_video_frame(self) -> av.VideoFrame:
        video_queue = self.output_queues[PipelineQueueType.VIDEO]
        frames = video_queue.tryGet()

        if frames:
            self.last_frame = img_frame_to_video_frame(frames)
        elif self.last_frame is None:
            self.last_frame = img_frame_to_video_frame(video_queue.get())

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
            return nn_queue.get()

        return detections
