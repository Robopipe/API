import depthai as dai

import pathlib


class CameraNNConfig:
    def __init__(
        self,
        sensor_name: str,
        sensor: dai.CameraFeatures,
        blob: dai.OpenVINO.Blob | pathlib.Path,
        num_inference_threads: int = 2,
    ):
        self.sensor_name = sensor_name
        self.sensor = sensor
        self.blob = (
            blob if isinstance(blob, dai.OpenVINO.Blob) else dai.OpenVINO.Blob(blob)
        )
        self.input_shape = list(self.blob.networkInputs.values())[0].dims
        self.output_shape = list(self.blob.networkOutputs.values())[0].dims
        self.num_inference_threads = num_inference_threads

    def create_node(self, pipeline: dai.Pipeline) -> dai.node.NeuralNetwork:
        node = pipeline.createNeuralNetwork()

        return self.configure_node(node)

    def configure_node(self, node: dai.node.NeuralNetwork):
        if isinstance(self.blob, dai.OpenVINO.Blob):
            node.setBlob(self.blob)
        else:
            node.setBlobPath(self.blob)

        node.input.setBlocking(False)
        node.setNumInferenceThreads(self.num_inference_threads)

        return node


class CameraNNYoloConfig(CameraNNConfig):
    def __init__(
        self,
        sensor_name: str,
        sensor: dai.CameraFeatures,
        blob: dai.OpenVINO.Blob | pathlib.Path,
        num_inference_threads: int = 2,
        anchor_masks: dict[str, list[int]] | None = None,
        anchors: list[float] | None = None,
        coordinate_size: int | None = None,
        confidence_threshold: float | None = None,
        iou_threshold: float | None = None,
        num_classes: int | None = None,
    ):
        super().__init__(sensor_name, sensor, blob, num_inference_threads)

        self.anchor_masks = anchor_masks
        self.anchors = anchors
        self.coordinate_size = coordinate_size
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.num_classes = num_classes

    def create_node(self, pipeline: dai.Pipeline):
        node = pipeline.createYoloDetectionNetwork()

        return self.configure_node(node)

    def configure_node(self, node: dai.node.YoloDetectionNetwork):
        if self.anchor_masks is not None:
            node.setAnchorMasks(self.anchor_masks)
        if self.anchors is not None:
            node.setAnchors(self.anchors)
        if self.coordinate_size is not None:
            node.setCoordinateSize(self.coordinate_size)
        if self.confidence_threshold is not None:
            node.setConfidenceThreshold(self.confidence_threshold)
        if self.iou_threshold is not None:
            node.setIouThreshold(self.iou_threshold)
        if self.num_classes is not None:
            node.setNumClasses(self.num_classes)

        return super().configure_node(node)


class CameraNNMobileNetConfig(CameraNNConfig):
    def __init__(
        self,
        sensor_name: str,
        sensor: dai.CameraFeatures,
        blob: dai.OpenVINO.Blob | pathlib.Path,
        num_inference_threads: int = 2,
        confidence_threshold: float | None = None,
    ):
        super().__init__(sensor_name, sensor, blob, num_inference_threads)

        self.confidence_threshold = confidence_threshold

    def create_node(self, pipeline: dai.Pipeline):
        node = pipeline.createMobileNetDetectionNetwork()

        return self.configure_node(node)

    def configure_node(self, node: dai.node.MobileNetDetectionNetwork):
        if self.confidence_threshold is not None:
            node.setConfidenceThreshold(self.confidence_threshold)

        return super().configure_node(node)
