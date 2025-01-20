import depthai as dai

import math
from typing import Callable

from ..pipeline.pipeline_queue_type import PipelineQueueType
from .sensor_config import SensorConfig, SensorConfigProperties
from .sensor_control import SensorControl
from .sensor_base import SensorBase


class Sensor(SensorBase):
    def __init__(
        self,
        sensor_features: dai.CameraFeatures,
        sensor_node: dai.node.Camera | dai.node.ColorCamera | dai.node.MonoCamera,
        input_queues: dict[PipelineQueueType, dai.DataInputQueue],
        output_queues: dict[PipelineQueueType, dai.DataOutputQueue],
        restart_pipeline: Callable[[], None],
    ):
        super().__init__(input_queues, output_queues, restart_pipeline)

        self.sensor_node = sensor_node
        self._config = SensorConfig(self.sensor_node)
        self._control = SensorControl.from_camera_control(
            self.sensor_node.initialControl, sensor_features.hasAutofocusIC
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

        if self._control.focus is not None:
            self._control.focus.lens_position = img.getLensPositionRaw()
