import depthai as dai

from ...log import logger
from ..nn import CameraNNConfig
from .depth_pipeline import DepthPipeline
from .pipeline_queue_type import PipelineQueueType


class NNPipeline(DepthPipeline):
    def __init__(
        self,
        networks: list[CameraNNConfig],
        pipeline: dai.Pipeline | None = None,
        device: dai.Device | None = None,
    ):
        logger.debug(f"[NNPipeline.__init__] Creating NNPipeline with {len(networks)} networks")
        self.neural_networks: dict[str, dai.node.NeuralNetwork] = {}
        self.nn_configs: dict[str, CameraNNConfig] = {}
        # Store NN input outputs for cleanup
        self.nn_outputs: dict = {}
        logger.debug(f"[NNPipeline.__init__] Calling super().__init__")
        super().__init__(None, [], pipeline, device)
        self._check_device("after super().__init__")
        logger.debug(f"[NNPipeline.__init__] Super init complete, adding networks")

        for i, nn in enumerate(networks):
            logger.debug(f"[NNPipeline.__init__] Adding network {i + 1}/{len(networks)}: {nn.sensor_name}")
            self._check_device(f"before adding network {i + 1}")
            self.add_nn(nn)
            self._check_device(f"after adding network {i + 1}")
        logger.debug(f"[NNPipeline.__init__] All networks added")

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

    def add_nn(self, nn: CameraNNConfig):
        sensor_name = nn.sensor_name
        logger.debug(f"[NNPipeline.add_nn] Adding NN for sensor: {sensor_name}")
        self.nn_configs[sensor_name] = nn
        self.remove_nn(sensor_name)

        # Handle DEPTH sensor specially
        if sensor_name.startswith("DEPTH"):
            logger.debug(f"[NNPipeline.add_nn] DEPTH sensor detected, setting up stereo")
            left, right = sensor_name.split("_")[1:]
            self.add_stereo_pair(f"CAM_{left}", f"CAM_{right}")

            # For depth-based NN, use disparity as input
            if self.stereo_node is not None:
                logger.debug(f"[NNPipeline.add_nn] Creating NN node with disparity input")
                nn_node = nn.create_node(
                    self.pipeline,
                    self.stereo_node.disparity,
                    with_depth=True,
                )

                if isinstance(nn_node, dai.node.SpatialDetectionNetwork):
                    logger.debug(f"[NNPipeline.add_nn] Setting up SpatialDetectionNetwork depth alignment")
                    self.stereo_node.setDepthAlign(nn.sensor.socket)
                    self.stereo_node.depth.link(nn_node.inputDepth)

                self.neural_networks[sensor_name] = nn_node
                logger.debug(f"[NNPipeline.add_nn] Creating NN output queue")
                nn_out = nn_node.out.createOutputQueue(maxSize=4, blocking=False)
                self.add_queue(nn_out, PipelineQueueType.NN, sensor_name, False)
                logger.debug(f"[NNPipeline.add_nn] DEPTH NN setup complete")
            return

        # Regular camera sensor
        logger.debug(f"[NNPipeline.add_nn] Regular camera sensor")
        self._check_device("before adding sensor")
        if sensor_name not in self.cameras:
            logger.debug(f"[NNPipeline.add_nn] Sensor not in cameras, adding sensor")
            self.add_sensor(nn.sensor)
        self._check_device("after adding sensor")
        logger.debug(f"[NNPipeline.add_nn] Sensor added, cameras={list(self.cameras.keys())}")

        cam = self.cameras[sensor_name]

        # Get camera output sized for NN input
        # input_shape is typically [batch, channels, height, width] e.g. [1, 3, 300, 300]
        # We need (height, width) which are the last two dimensions
        nn_input_size = tuple(nn.input_shape[-2:])
        logger.debug(f"[NNPipeline.add_nn] Requesting camera output with size={nn_input_size} (from input_shape={nn.input_shape})")
        self._check_device("before requestOutput")
        nn_camera_output = cam.requestOutput(
            size=nn_input_size,
            type=dai.ImgFrame.Type.BGR888p,
        )
        self._check_device("after requestOutput")
        logger.debug(f"[NNPipeline.add_nn] Camera output requested")
        self.nn_outputs[sensor_name] = nn_camera_output

        # Create NN node with camera output (v3 API)
        logger.debug(f"[NNPipeline.add_nn] Creating NN node (with_depth={self.stereo_pair is not None})")
        self._check_device("before create_node")
        nn_node = nn.create_node(
            self.pipeline,
            nn_camera_output,
            with_depth=(self.stereo_pair is not None),
        )
        self._check_device("after create_node")
        logger.debug(f"[NNPipeline.add_nn] NN node created: {type(nn_node).__name__}")

        if self.stereo_pair is not None and isinstance(
            nn_node, dai.node.SpatialDetectionNetwork
        ):
            logger.debug(f"[NNPipeline.add_nn] Linking depth to SpatialDetectionNetwork")
            self.stereo_node.setDepthAlign(nn.sensor.socket)
            self.stereo_node.depth.link(nn_node.inputDepth)

        self.neural_networks[sensor_name] = nn_node

        # Create output queue for NN results
        logger.debug(f"[NNPipeline.add_nn] Creating NN output queue")
        nn_out = nn_node.out.createOutputQueue(maxSize=4, blocking=False)
        self.add_queue(nn_out, PipelineQueueType.NN, sensor_name, False)
        logger.debug(f"[NNPipeline.add_nn] NN added successfully for {sensor_name}")

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
