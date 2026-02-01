import depthai as dai

from ..nn import CameraNNConfig
from .depth_pipeline import DepthPipeline
from .pipeline_queue_type import PipelineQueueType


class NNPipeline(DepthPipeline):
    def __init__(
        self, networks: list[CameraNNConfig], pipeline: dai.Pipeline | None = None
    ):
        self.neural_networks: dict[str, dai.node.NeuralNetwork] = {}
        self.nn_configs: dict[str, CameraNNConfig] = {}
        # Store NN input outputs for cleanup
        self.nn_outputs: dict = {}
        super().__init__(None, [], pipeline)

        for nn in networks:
            self.add_nn(nn)

    def extract_properties(self):
        super().extract_properties()

        for neural_network in self.pipeline.getAllNodes():
            if not isinstance(neural_network, dai.node.NeuralNetwork):
                continue

            for camera in self.cameras.values():
                # In v3, all cameras are dai.node.Camera
                # Try to find which camera is linked to this NN
                try:
                    self.neural_networks[camera.getBoardSocket().name] = neural_network
                    break
                except:
                    continue

    def get_video_queue(self, sensor_name: str):
        return self.outputs[
            self.output_queues[sensor_name].get(PipelineQueueType.VIDEO)
        ]

    def __setup_camera(
        self,
        camera: dai.node.Camera,
        nn: CameraNNConfig,
        nn_node: dai.node.NeuralNetwork,
    ):
        sensor_name = camera.getBoardSocket().name

        # Create an output sized for the NN input
        nn_input_size = nn.input_shape[:2]
        nn_output = camera.requestOutput(
            size=nn_input_size,
            type=dai.ImgFrame.Type.BGR888p,
        )
        nn_output.link(nn_node.input)
        self.nn_outputs[sensor_name] = nn_output

    def __setup_stereo_camera(
        self, nn: CameraNNConfig, nn_node: dai.node.NeuralNetwork
    ):
        # For depth-based NN, link disparity to NN
        # This requires the disparity to be converted to appropriate format
        if self.stereo_node is not None:
            self.stereo_node.disparity.link(nn_node.input)

    def add_nn(self, nn: CameraNNConfig):
        sensor_name = nn.sensor_name
        self.nn_configs[sensor_name] = nn
        self.remove_nn(sensor_name)

        nn_node = nn.create_node(self.pipeline, self.stereo_pair is not None)

        if self.stereo_pair is not None and isinstance(
            nn_node, dai.node.SpatialDetectionNetwork
        ):
            self.stereo_node.setDepthAlign(nn.sensor.socket)
            self.stereo_node.depth.link(nn_node.inputDepth)

        self.neural_networks[sensor_name] = nn_node

        # Create output queue for NN results
        nn_out = nn_node.out.createOutputQueue(maxSize=1, blocking=False)
        self.add_queue(nn_out, PipelineQueueType.NN, sensor_name, False)

        if sensor_name.startswith("DEPTH"):
            left, right = sensor_name.split("_")[1:]
            self.add_stereo_pair(f"CAM_{left}", f"CAM_{right}")
            self.__setup_stereo_camera(nn, nn_node)
            return

        if sensor_name not in self.cameras:
            self.add_sensor(nn.sensor)

        cam = self.cameras[sensor_name]
        self.__setup_camera(cam, nn, nn_node)

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

        nn_node = self.neural_networks[sensor_name]

        # Clean up NN output reference
        if sensor_name in self.nn_outputs:
            del self.nn_outputs[sensor_name]

        self.pipeline.remove(nn_node)
        del self.neural_networks[sensor_name]
        del self.nn_configs[sensor_name]
        self.del_queue(sensor_name, PipelineQueueType.NN)

    def remove_sensor(self, sensor):
        self.remove_nn(sensor)

        return super().remove_sensor(sensor)
