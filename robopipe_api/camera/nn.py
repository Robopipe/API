import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork

# Type alias for supported model formats
ModelType = dai.NNArchive


class CameraNNConfig:
    def __init__(
        self,
        sensor_name: str,
        sensor: dai.CameraFeatures,
        model: ModelType,
        num_inference_threads: int = 2,
        use_parser: bool = True,
    ):
        self.sensor_name = sensor_name
        self.sensor = sensor
        self.num_inference_threads = num_inference_threads
        self.use_parser = use_parser
        self.model = model

    def create_node(
        self,
        pipeline: dai.Pipeline,
        camera: dai.node.Camera,
    ) -> dai.node.NeuralNetwork | ParsingNeuralNetwork:
        if self.use_parser:
            node = pipeline.create(ParsingNeuralNetwork)
        else:
            node = pipeline.create(dai.node.NeuralNetwork)

        node.input.setBlocking(False)
        node.setNumInferenceThreads(self.num_inference_threads)
        node.build(camera, self.model)

        return node
