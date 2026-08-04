import datetime

import depthai as dai

from typing import Callable

from ...log import logger
from ...models.still_config import StillConfig
from ..pipeline.pipeline_queue_type import PipelineQueueType
from .sensor_control import SensorControl
from .sensor_base import SensorBase


class Sensor(SensorBase):
    INITIAL_SYNC_TIMEOUT = datetime.timedelta(seconds=1)

    def __init__(
        self,
        sensor_features: dai.CameraFeatures,
        sensor_node: dai.node.Camera,
        input_queues: dict,
        output_queues: dict,
        restart_pipeline: Callable[[], None],
    ):
        super().__init__(input_queues, output_queues, restart_pipeline)

        self._sensor_features = sensor_features
        self.sensor_node = sensor_node
        self._still_config: StillConfig | None = None
        self._control = SensorControl.default_for(sensor_features)
        self.refresh_control_from_frame()

    def refresh_control_from_frame(self) -> None:
        video_queue = self.output_queues.get(PipelineQueueType.VIDEO)
        if video_queue is None:
            return
        try:
            img = video_queue.get(timeout=self.INITIAL_SYNC_TIMEOUT)
        except Exception as e:
            logger.debug(f"Control state refresh failed: {e}")
            return
        if img is not None:
            self.on_frame(img)

    @property
    def features(self) -> dai.CameraFeatures:
        return self._sensor_features

    @property
    def config(self) -> StillConfig:
        return self._still_config

    @config.setter
    def config(self, value: StillConfig) -> None:
        self._still_config = value

    @property
    def control(self) -> SensorControl:
        return self._control

    @control.setter
    def control(self, value: SensorControl):
        self._control = value
        control_queue = self.input_queues.get(PipelineQueueType.CONTROL)
        if control_queue is not None:
            control_queue.send(self._control.to_camera_control(self._sensor_features))

    def on_frame(self, img: dai.ImgFrame) -> None:
        self._control.update_from_frame(img)
