import av
import depthai as dai
from PIL import Image
import numpy as np

from typing import Callable

from ..utils.image import dai_image_to_pil_image
from .pipeline import PipelineQueueType
from .sensor_config import CameraConfig, CameraConfigProperties

# from .sensor_control import SensorControl


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
        self._camera_config = CameraConfig(self.sensor_node)
        # self._control = SensorControl(self.sensor_node.initialControl.getData())

    @property
    def camera_config(self) -> CameraConfigProperties:
        return self._camera_config.properties

    @camera_config.setter
    def camera_config(self, value: CameraConfigProperties):
        self._camera_config.properties = value
        self.restart_pipeline()

    def capture_still(self):
        control_queue = self.input_queues[PipelineQueueType.CONTROL]

        ctrl = dai.CameraControl()
        ctrl.setCaptureStill(True)
        control_queue.send(ctrl)

        try:
            img_frame = self.output_queues[PipelineQueueType.STILL].get()
        except:
            return

        return dai_image_to_pil_image(img_frame)

    def get_video_frame(self):
        try:
            video_frame = self.output_queues[PipelineQueueType.VIDEO].getAll()[0]
        except:
            return

        return av.VideoFrame.from_ndarray(video_frame.getFrame(), "nv12").to_rgb()

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
