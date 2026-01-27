import depthai as dai
import numpy as np
from PIL import Image

from abc import ABC, abstractmethod
from typing import Callable

from ...models.nn_config import NNConfig
from ...utils.image import img_frame_to_pil_image, img_frame_to_video_frame
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
            # control_queue = self.input_queues[PipelineQueueType.CONTROL]
            # ctrl = dai.CameraControl()
            # ctrl.setCaptureStill(True)
            # control_queue.send(ctrl)
            still_queue = self.output_queues[PipelineQueueType.STILL]
            img_frame = still_queue.getAll()[-1]
            print(img_frame)
            # img_frame: dai.ImgFrame = self.output_queues[
            #     PipelineQueueType.STILL
            # ].getAll()[-1]

            # self.__extract_img_properties(img_frame)
        except Exception as e:
            print(f"Error capturing still image: {e}")
            return

        return img_frame_to_pil_image(img_frame)

    def get_video_frame(self):
        video_frame: dai.ImgFrame = self.output_queues[PipelineQueueType.VIDEO].get()

        # while video_frame is None:
        #     print("Waiting for video frame...")
        #     video_frame = self.output_queues[PipelineQueueType.VIDEO].front()

        # self.__extract_img_properties(video_frame)

        return img_frame_to_video_frame(video_frame).to_rgb()

    def get_nn_frame(self):
        try:
            detections = self.output_queues[PipelineQueueType.NN].get()
            passthrough = self.output_queues[PipelineQueueType.NN_PASSTHROUGH].get()
        except Exception as e:
            return

        passthrough_frame = Image.fromarray(
            np.transpose(passthrough.getFrame().astype("uint8"), (1, 2, 0)), "RGB"
        )

        return (passthrough_frame, detections)

    def get_nn_detections(
        self,
    ) -> dai.NNData | dai.ImgDetections | dai.SpatialImgDetections:
        detections = self.output_queues[PipelineQueueType.NN].get()

        return detections
