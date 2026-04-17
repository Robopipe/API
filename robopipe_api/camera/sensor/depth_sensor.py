import depthai as dai

from typing import Callable

from .sensor import Sensor
from .sensor_config import SensorConfig, SensorConfigProperties


class DepthSensor(Sensor):
    def __init__(
        self,
        sensor_features: dai.CameraFeatures,
        sensor_nodes: tuple[dai.node.Camera, dai.node.Camera],
        input_queues: dict,
        output_queues: dict,
        restart_pipeline: Callable[[], None],
    ):
        super().__init__(
            sensor_features,
            sensor_nodes[0],
            input_queues,
            output_queues,
            restart_pipeline,
        )

        self.left, self.right = sensor_nodes
        self._config = (SensorConfig(self.left), SensorConfig(self.right))

    @property
    def config(self) -> SensorConfigProperties:
        return self._config[0].properties

    @config.setter
    def config(self, value: SensorConfigProperties) -> SensorConfigProperties:
        self._config = (value, value)
        self.restart_pipeline()

        return value
