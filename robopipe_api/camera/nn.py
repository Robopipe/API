import depthai as dai

import pathlib

from ..log import logger

# Type alias for supported model formats
ModelType = dai.OpenVINO.Blob | dai.NNArchive | pathlib.Path


class CameraNNConfig:
    def __init__(
        self,
        sensor_name: str,
        sensor: dai.CameraFeatures,
        blob: ModelType,
        num_inference_threads: int = 2,
    ):
        self.sensor_name = sensor_name
        self.sensor = sensor
        self.num_inference_threads = num_inference_threads

        # Handle different model formats
        logger.info(f"[CameraNNConfig] blob type: {type(blob)}")
        if isinstance(blob, dai.NNArchive):
            self.nn_archive = blob
            self.blob = None
            # Get input/output shapes from archive
            try:
                config = blob.getConfig()
                logger.info(f"[CameraNNConfig] NNArchive config.model: {config.model}")
                # inputs/outputs can be list or dict depending on version
                inputs = config.model.inputs
                outputs = config.model.outputs
                logger.info(f"[CameraNNConfig] inputs: {inputs}, outputs: {outputs}")
                if isinstance(inputs, dict):
                    first_input = list(inputs.values())[0]
                    logger.info(f"[CameraNNConfig] first_input: {first_input}, attrs: {dir(first_input)}")
                    self.input_shape = list(first_input.dims) if hasattr(first_input, 'dims') else [1, 3, 300, 300]
                elif isinstance(inputs, list) and len(inputs) > 0:
                    first_input = inputs[0]
                    logger.info(f"[CameraNNConfig] first_input (list): {first_input}, attrs: {dir(first_input)}")
                    # Try different attribute names for shape/dims
                    if hasattr(first_input, 'dims'):
                        self.input_shape = list(first_input.dims)
                    elif hasattr(first_input, 'shape'):
                        self.input_shape = list(first_input.shape)
                    elif hasattr(first_input, 'size'):
                        self.input_shape = list(first_input.size)
                    else:
                        logger.warning(f"[CameraNNConfig] No dims/shape/size attr found")
                        self.input_shape = [1, 3, 300, 300]
                else:
                    logger.warning(f"[CameraNNConfig] Could not extract input shape, using default")
                    self.input_shape = [1, 3, 300, 300]
                if isinstance(outputs, dict):
                    first_output = list(outputs.values())[0]
                    self.output_shape = list(first_output.dims) if hasattr(first_output, 'dims') else [1, 1, 100, 7]
                elif isinstance(outputs, list) and len(outputs) > 0:
                    self.output_shape = list(outputs[0].dims) if hasattr(outputs[0], 'dims') else [1, 1, 100, 7]
                else:
                    self.output_shape = [1, 1, 100, 7]
            except Exception as e:
                # Fallback to defaults if config parsing fails
                logger.error(f"[CameraNNConfig] Failed to parse NNArchive config: {e}")
                import traceback
                traceback.print_exc()
                self.input_shape = [1, 3, 300, 300]
                self.output_shape = [1, 1, 100, 7]
        else:
            self.nn_archive = None
            self.blob = (
                blob if isinstance(blob, dai.OpenVINO.Blob) else dai.OpenVINO.Blob(blob)
            )
            self.input_shape = list(self.blob.networkInputs.values())[0].dims
            self.output_shape = list(self.blob.networkOutputs.values())[0].dims

        logger.info(f"[CameraNNConfig] Final shapes - input: {self.input_shape}, output: {self.output_shape}")

    def create_node(
        self,
        pipeline: dai.Pipeline,
        camera_output,
        with_depth: bool = False,
    ) -> dai.node.NeuralNetwork:
        """Create and configure NN node with v3 API.

        Args:
            pipeline: The depthai pipeline
            camera_output: The camera output to link to NN input (from requestOutput)
            with_depth: Whether to use spatial detection (requires stereo depth)
        """
        logger.debug(f"[CameraNNConfig.create_node] Creating NeuralNetwork node")
        node = pipeline.create(dai.node.NeuralNetwork)
        logger.debug(f"[CameraNNConfig.create_node] NeuralNetwork node created")

        # V3 API: use build() with input and model for NNArchive
        if self.nn_archive is not None:
            logger.debug(f"[CameraNNConfig.create_node] Building with NNArchive")
            node.build(camera_output, self.nn_archive)
            logger.debug(f"[CameraNNConfig.create_node] NNArchive build complete")
        else:
            # For Blob, link manually and set blob
            logger.debug(f"[CameraNNConfig.create_node] Linking camera output to node input")
            camera_output.link(node.input)
            if isinstance(self.blob, dai.OpenVINO.Blob):
                logger.debug(f"[CameraNNConfig.create_node] Setting blob")
                node.setBlob(self.blob)
            else:
                logger.debug(f"[CameraNNConfig.create_node] Setting blob path")
                node.setBlobPath(self.blob)

        logger.debug(f"[CameraNNConfig.create_node] Configuring node (blocking=False, threads={self.num_inference_threads})")
        node.input.setBlocking(False)
        node.setNumInferenceThreads(self.num_inference_threads)

        logger.debug(f"[CameraNNConfig.create_node] Node creation complete")
        return node


class CameraNNYoloConfig(CameraNNConfig):
    def __init__(
        self,
        sensor_name: str,
        sensor: dai.CameraFeatures,
        blob: ModelType,
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

    def create_node(
        self,
        pipeline: dai.Pipeline,
        camera_output,
        with_depth: bool = False,
    ):
        logger.debug(f"[CameraNNYoloConfig.create_node] Creating YOLO node (with_depth={with_depth})")
        if with_depth:
            node = pipeline.create(dai.node.YoloSpatialDetectionNetwork)
        else:
            node = pipeline.create(dai.node.YoloDetectionNetwork)
        logger.debug(f"[CameraNNYoloConfig.create_node] Node created: {type(node).__name__}")

        return self.configure_node(node, camera_output)

    def configure_node(self, node, camera_output):
        logger.debug(f"[CameraNNYoloConfig.configure_node] Configuring YOLO node")
        # Link camera output to detection network input
        if self.nn_archive is not None:
            logger.debug(f"[CameraNNYoloConfig.configure_node] Building with NNArchive")
            node.build(camera_output, self.nn_archive)
        else:
            logger.debug(f"[CameraNNYoloConfig.configure_node] Linking camera output and setting blob")
            camera_output.link(node.input)
            if isinstance(self.blob, dai.OpenVINO.Blob):
                node.setBlob(self.blob)
            else:
                node.setBlobPath(self.blob)

        logger.debug(f"[CameraNNYoloConfig.configure_node] Setting YOLO-specific parameters")
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

        node.input.setBlocking(False)
        node.setNumInferenceThreads(self.num_inference_threads)
        logger.debug(f"[CameraNNYoloConfig.configure_node] YOLO node configuration complete")

        return node


class CameraNNMobileNetConfig(CameraNNConfig):
    def __init__(
        self,
        sensor_name: str,
        sensor: dai.CameraFeatures,
        blob: ModelType,
        num_inference_threads: int = 2,
        confidence_threshold: float | None = None,
    ):
        super().__init__(sensor_name, sensor, blob, num_inference_threads)

        self.confidence_threshold = confidence_threshold

    def create_node(
        self,
        pipeline: dai.Pipeline,
        camera_output,
        with_depth: bool = False,
    ):
        logger.debug(f"[CameraNNMobileNetConfig.create_node] Creating MobileNet node (with_depth={with_depth})")
        if with_depth:
            node = pipeline.create(dai.node.MobileNetSpatialDetectionNetwork)
        else:
            node = pipeline.create(dai.node.MobileNetDetectionNetwork)
        logger.debug(f"[CameraNNMobileNetConfig.create_node] Node created: {type(node).__name__}")

        return self.configure_node(node, camera_output)

    def configure_node(self, node, camera_output):
        logger.debug(f"[CameraNNMobileNetConfig.configure_node] Configuring MobileNet node")
        # Link camera output to detection network input
        if self.nn_archive is not None:
            logger.debug(f"[CameraNNMobileNetConfig.configure_node] Building with NNArchive")
            node.build(camera_output, self.nn_archive)
        else:
            logger.debug(f"[CameraNNMobileNetConfig.configure_node] Linking camera output and setting blob")
            camera_output.link(node.input)
            if isinstance(self.blob, dai.OpenVINO.Blob):
                node.setBlob(self.blob)
            else:
                node.setBlobPath(self.blob)

        if self.confidence_threshold is not None:
            logger.debug(f"[CameraNNMobileNetConfig.configure_node] Setting confidence_threshold={self.confidence_threshold}")
            node.setConfidenceThreshold(self.confidence_threshold)

        node.input.setBlocking(False)
        node.setNumInferenceThreads(self.num_inference_threads)
        logger.debug(f"[CameraNNMobileNetConfig.configure_node] MobileNet node configuration complete")

        return node
