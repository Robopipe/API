import depthai as dai

from typing import Self

from ..nn import CameraNNConfig
from .depth_pipeline import DepthPipeline
from .pipeline_queue_type import PipelineQueueType


class NNPipeline(DepthPipeline):
    def __init__(
        self,
        device: dai.Device,
        pipeline: Self | None = None,
        networks: list[CameraNNConfig] = [],
        sensors: list[dai.CameraFeatures] = [],
    ):
        self.neural_networks: dict[str, dai.node.NeuralNetwork] = {}
        self.nn_configs: dict[str, CameraNNConfig] = {}

        sensors = list(
            filter(
                lambda s: s.socket.name not in map(lambda nn: nn.sensor_name, networks),
                sensors,
            )
        )
        super().__init__(device, pipeline, sensors)

        for nn in networks:
            self.add_nn(nn)

    def recreate(self, pipeline: Self):
        super().recreate(pipeline)

        for nn in pipeline.nn_configs.values():
            self.add_nn(nn)

    def get_video_queue(self, sensor_name: str):
        return self.outputs[
            self.output_queues[sensor_name].get(PipelineQueueType.VIDEO)
        ]

    def add_nn_config(self, nn_config: CameraNNConfig):
        self.remove_sensor(nn_config.sensor_name)
        self.nn_configs[nn_config.sensor_name] = nn_config

    def add_nn(self, nn: CameraNNConfig):
        sensor_name = nn.sensor_name
        self.remove_nn(sensor_name)
        self.remove_sensor(sensor_name)
        self.nn_configs[sensor_name] = nn

        if sensor_name not in self.cameras:
            cam = self.pipeline.create(dai.node.Camera)
            self.build_camera(cam, nn.sensor.socket)
            self.cameras[sensor_name] = cam

        cam = self.cameras[sensor_name]
        nn_node = nn.create_node(self.pipeline, self.cameras.get(sensor_name))
        self.neural_networks[sensor_name] = nn_node
        nn_out = nn_node.out.createOutputQueue(maxSize=1, blocking=False)
        self.add_queue(nn_out, PipelineQueueType.NN, sensor_name, False)
        nn_video = nn_node.passthrough.createOutputQueue(maxSize=4, blocking=False)
        self.add_queue(nn_video, PipelineQueueType.VIDEO, sensor_name, False)

    def add_stereo_pair(self, left, right):
        nn_to_remove: list[CameraNNConfig] = []
        nn_to_reconfigure: list[CameraNNConfig] = []

        for nn in self.nn_configs.values():
            if nn.sensor_name in (left, right):
                nn_to_remove.append(nn)
            else:
                nn_to_reconfigure.append(nn)

        nn_to_remove.extend(nn_to_reconfigure)

        for nn in nn_to_remove:
            self.remove_nn(nn)

        super().add_stereo_pair(left, right)

        for nn in nn_to_reconfigure:
            self.add_nn(nn)

    def remove_stereo_pair(self):
        nn_to_reconfigure: list[CameraNNConfig] = []

        for sensor_name, nn in self.nn_configs.items():
            if isinstance(
                self.neural_networks[sensor_name], dai.node.SpatialDetectionNetwork
            ):
                nn_to_reconfigure.append(nn)

        for nn in nn_to_reconfigure:
            self.remove_nn(nn.sensor_name)

        super().remove_stereo_pair()

        for nn in nn_to_reconfigure:
            self.add_nn(nn)

    def remove_nn(self, sensor_name: str):
        if sensor_name not in self.neural_networks:
            return

        self.del_all_queues(sensor_name)
        del self.neural_networks[sensor_name]
        del self.nn_configs[sensor_name]

    def remove_sensor(self, sensor):
        self.remove_nn(sensor)

        return super().remove_sensor(sensor)
