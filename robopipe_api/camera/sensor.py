import av
import depthai as dai
from PIL import Image
import numpy as np

import math
from typing import Callable

from ..utils.image import img_frame_to_pil_image
from .pipeline.pipeline_queue_type import PipelineQueueType
from .sensor_config import SensorConfig, SensorConfigProperties
from .sensor_control import SensorControl


class Sensor:
    def __init__(
        self,
        sensor_node: dai.node.Camera | dai.node.ColorCamera | dai.node.MonoCamera,
        input_queues: dict[PipelineQueueType, dai.DataInputQueue],
        output_queues: dict[PipelineQueueType, dai.DataOutputQueue],
        restart_pipeline: Callable[[], None],
    ):
        self.sensor_node = sensor_node
        self.input_queues = input_queues
        self.output_queues = output_queues
        self.restart_pipeline = restart_pipeline
        self._config = SensorConfig(self.sensor_node)
        self._control = SensorControl.from_camera_control(
            self.sensor_node.initialControl
        )

    @property
    def config(self) -> SensorConfigProperties:
        return self._config.properties

    @config.setter
    def config(self, value: SensorConfigProperties):
        self._config.properties = value
        self.restart_pipeline()

    @property
    def control(self) -> SensorControl:
        return self._control

    @control.setter
    def control(self, value: SensorControl):
        self._control = value
        control_queue = self.input_queues[PipelineQueueType.CONTROL]
        control_queue.send(self._control.to_camera_control())

    def __extract_img_properties(self, img: dai.ImgFrame):
        self._control.sensitivity_iso = img.getSensitivity()
        self._control.exposure_time = math.floor(
            img.getExposureTime().total_seconds() * 1000
        )
        self._control.manual_whitebalance = img.getColorTemperature()

    def capture_still(self):
        try:
            if PipelineQueueType.NN not in self.output_queues:
                self.output_queues[PipelineQueueType.STILL].getAll()
            else:
                control_queue = self.input_queues[PipelineQueueType.CONTROL]
                ctrl = dai.CameraControl()
                ctrl.setCaptureStill(True)
                control_queue.send(ctrl)

            img_frame: dai.ImgFrame = self.output_queues[PipelineQueueType.STILL].get()
            self.__extract_img_properties(img_frame)
        except:
            return

        return img_frame_to_pil_image(img_frame)

    def get_video_frame(self):
        video_frame: dai.ImgFrame = self.output_queues[
            PipelineQueueType.VIDEO
        ].getAll()[-1]
        frame_type = video_frame.getType()

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
