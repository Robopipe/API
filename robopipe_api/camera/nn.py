import depthai as dai

import pathlib


class CameraNNConfig:
    def __init__(
        self,
        sensor: dai.CameraFeatures,
        blob: dai.OpenVINO.Blob | pathlib.Path,
        num_inference_threads: int = 2,
    ):
        self.sensor = sensor
        self.blob = (
            blob if isinstance(blob, dai.OpenVINO.Blob) else dai.OpenVINO.Blob(blob)
        )
        self.input_shape = self.blob.networkInputs["input"].dims
        self.output_shape = self.blob.networkOutputs["output"].dims
        self.num_inference_threads = num_inference_threads

    def create_node(self, pipeline: dai.Pipeline) -> dai.node.NeuralNetwork:
        node = pipeline.createNeuralNetwork()

        return self.configure_node(node)

    def configure_node(self, node: dai.node.NeuralNetwork):
        if isinstance(self.blob, dai.OpenVINO.Blob):
            node.setBlob(self.blob)
        else:
            node.setBlobPath(self.blob)

        node.setNumInferenceThreads(self.num_inference_threads)

        return node
