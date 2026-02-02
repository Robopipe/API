import depthai as dai
import numpy as np
from PIL import Image

from abc import ABC, abstractmethod
from typing import Callable
import av

from ...models.nn_config import NNConfig
from ...utils.image import img_frame_to_pil_image, img_frame_to_video_frame
from ..pipeline.pipeline_queue_type import PipelineQueueType
from .sensor_config import SensorConfigProperties
from .sensor_control import SensorControl


class SensorBase(ABC):
    def __init__(
        self,
        input_queues: dict,
        output_queues: dict,
        restart_pipeline: Callable[[], None],
    ):
        self.input_queues = input_queues
        self.output_queues = output_queues
        self.restart_pipeline = restart_pipeline
        self._nn_config = None
        self.last_frame = None

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

    def __extract_img_properties(self, img: dai.ImgFrame):
        pass

    def capture_still(self):
        try:
            still_queue = self.output_queues[PipelineQueueType.STILL]
            # Get all frames and use only the latest, then clean up
            frames = still_queue.getAll()
            if not frames:
                return None
            img_frame = frames[-1]
            # Explicitly clean up the list to free memory
            del frames
        except Exception as e:
            print(f"Error capturing still image: {e}")
            return None

        return img_frame_to_pil_image(img_frame)

    def get_video_frame(self):
        video_queue = self.output_queues[PipelineQueueType.VIDEO]
        dai_frame = video_queue.tryGet()

        if dai_frame is not None:
            # Drain any additional queued frames to get the latest and prevent buildup
            while True:
                next_frame = video_queue.tryGet()
                if next_frame is None:
                    break
                dai_frame = next_frame

            # Clean up old frame before replacing
            if self.last_frame is not None:
                del self.last_frame
            self.last_frame = img_frame_to_video_frame(dai_frame)
        elif self.last_frame is None:
            # Blocking get only if we have no frame at all
            dai_frame = video_queue.get()
            self.last_frame = img_frame_to_video_frame(dai_frame)

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

        passthrough_frame = Image.fromarray(
            np.transpose(frame_data, (1, 2, 0)), "RGB"
        )

        return (passthrough_frame, detections)

    def get_nn_detections(
        self,
    ) -> dai.NNData | dai.ImgDetections | dai.SpatialImgDetections | None:
        nn_queue = self.output_queues.get(PipelineQueueType.NN)
        if nn_queue is None:
            return None

        # Try to get the latest detection, draining any queued ones
        detections = nn_queue.tryGet()
        if detections is not None:
            # Drain queue to get most recent and prevent buildup
            while True:
                next_det = nn_queue.tryGet()
                if next_det is None:
                    break
                detections = next_det
        else:
            # Blocking get if no detection available yet
            detections = nn_queue.get()

        return detections
