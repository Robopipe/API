from __future__ import annotations

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork

from ..models.sahi_config import SAHIConfig
from .sahi import Tile, compute_tiles

# Type alias for supported model formats
ModelType = dai.NNArchive


class SAHINodes:
    """Result of building a SAHI pipeline: one full-frame NN plus a single
    tile NN whose ImageManip crop is reconfigured at runtime to cycle
    through tiles."""

    def __init__(
        self,
        full_frame_nn: dai.node.NeuralNetwork | ParsingNeuralNetwork,
        tile_nn: dai.node.NeuralNetwork | ParsingNeuralNetwork,
        tile_manip_cfg: dai.InputQueue,
        tiles: list[Tile],
        model_input_size: tuple[int, int],
    ):
        self.full_frame_nn = full_frame_nn
        self.tile_nn = tile_nn
        self.tile_manip_cfg = tile_manip_cfg
        self.tiles = tiles
        self.model_input_size = model_input_size


class CameraNNConfig:
    def __init__(
        self,
        sensor_name: str,
        sensor: dai.CameraFeatures,
        model: ModelType,
        num_inference_threads: int = 2,
        use_parser: bool = True,
        sahi_config: SAHIConfig | dict | None = None,
    ):
        self.sensor_name = sensor_name
        self.sensor = sensor
        self.num_inference_threads = num_inference_threads
        self.use_parser = use_parser
        self.model = model
        if isinstance(sahi_config, dict):
            sahi_config = SAHIConfig(**sahi_config)
        self.sahi_config = sahi_config

    def _create_nn_node(
        self,
        pipeline: dai.Pipeline,
        num_threads: int,
    ) -> dai.node.NeuralNetwork | ParsingNeuralNetwork:
        if self.use_parser:
            node = pipeline.create(ParsingNeuralNetwork)
        else:
            node = pipeline.create(dai.node.NeuralNetwork)

        node.input.setBlocking(False)
        node.setNumInferenceThreads(num_threads)
        return node

    def create_node(
        self,
        pipeline: dai.Pipeline,
        camera: dai.node.Camera,
    ) -> dai.node.NeuralNetwork | ParsingNeuralNetwork:
        node = self._create_nn_node(pipeline, self.num_inference_threads)
        node.build(camera, self.model)
        return node

    def create_sahi_nodes(
        self,
        pipeline: dai.Pipeline,
        camera: dai.node.Camera,
    ) -> SAHINodes:
        # Full-frame NN (unchanged)
        full_frame_nn = self.create_node(pipeline, camera)

        tiles = compute_tiles(self.sahi_config)
        model_input_size = self.model.getInputSize()

        # Shared camera output for tile crops
        cam_output = camera.requestOutput(model_input_size)

        # Single ImageManip — crop is reconfigured at runtime to cycle tiles
        manip = pipeline.create(dai.node.ImageManip)
        first_tile = tiles[0]
        crop_rect = dai.Rect(
            dai.Point2f(first_tile.x1, first_tile.y1),
            dai.Point2f(first_tile.x2, first_tile.y2),
        )
        manip.initialConfig.addCrop(crop_rect, True)
        manip.initialConfig.setOutputSize(model_input_size[0], model_input_size[1])
        manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
        manip.setMaxOutputFrameSize(model_input_size[0] * model_input_size[1] * 3)
        cam_output.link(manip.inputImage)

        # Host input queue for dynamic crop reconfiguration
        manip_cfg = manip.inputConfig.createInputQueue()

        # Single tile NN
        tile_nn = self._create_nn_node(pipeline, 1)
        tile_nn.build(manip.out, self.model)

        return SAHINodes(full_frame_nn, tile_nn, manip_cfg, tiles, model_input_size)
