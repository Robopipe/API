import av
import depthai as dai
import numpy as np
from PIL import Image

from abc import ABC, abstractmethod
from typing import Callable

from ...utils.image import img_frame_to_pil_image
from ..pipeline.pipeline_queue_type import PipelineQueueType
from .sensor_config import SensorConfigProperties
from .sensor_control import SensorControl


class SensorBase(ABC):
    def __init__(
        self,
        input_queues: dict[PipelineQueueType, dai.DataInputQueue],
        output_queues: dict[PipelineQueueType, dai.DataOutputQueue],
        restart_pipeline: Callable[[], None],
    ):
        self.input_queues = input_queues
        self.output_queues = output_queues
        self.restart_pipeline = restart_pipeline

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

    def __extract_img_properties(self, img: dai.ImgFrame):
        pass

    def capture_still(self):
        try:
            if PipelineQueueType.NN not in self.output_queues:
                self.output_queues[PipelineQueueType.STILL].getAll()
            else:
                control_queue = self.input_queues[PipelineQueueType.CONTROL]
                ctrl = dai.CameraControl()
                ctrl.setCaptureStill(True)
                control_queue.send(ctrl)

            img_frame: dai.ImgFrame = self.output_queues[
                PipelineQueueType.STILL
            ].getAll()[-1]

            self.__extract_img_properties(img_frame)
        except:
            return

        return img_frame_to_pil_image(img_frame)

    def get_video_frame(self):
        video_frame: dai.ImgFrame = self.output_queues[
            PipelineQueueType.VIDEO
        ].getAll()[-1]
        frame_type = video_frame.getType()

        self.__extract_img_properties(video_frame)

        if frame_type == dai.RawImgFrame.Type.NV12:
            return av.VideoFrame.from_ndarray(video_frame.getFrame(), "nv12").to_rgb()
        elif frame_type == dai.RawImgFrame.Type.BGR888i:
            return av.VideoFrame.from_ndarray(video_frame.getFrame()[..., ::-1], "rbg")
        elif frame_type == dai.RawImgFrame.Type.RAW8:
            return av.VideoFrame.from_ndarray(video_frame.getFrame(), "gray")

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

    def get_nn_detections(self) -> dai.NNData | dai.ImgDetections:
        detections = self.output_queues[PipelineQueueType.NN].get()

        return detections
