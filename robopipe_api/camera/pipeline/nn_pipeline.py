import depthai as dai

from ..nn import CameraNNConfig
from .depth_pipeline import DepthPipeline
from .pipeline_queue_type import PipelineQueueType


class NNPipeline(DepthPipeline):
    def __init__(
        self, networks: list[CameraNNConfig], pipeline: dai.Pipeline | None = None
    ):
        self.neural_networks: dict[str, dai.node.NeuralNetwork] = {}
        super().__init__([], pipeline)

        for nn in networks:
            self.add_nn(nn)

    def extract_properties(self):
        super().extract_properties()

        for neural_network in self.pipeline.getAllNodes():
            if not isinstance(neural_network, dai.node.NeuralNetwork):
                continue

            for camera in self.cameras.values():
                is_mono = isinstance(camera, dai.node.MonoCamera)

                try:
                    if is_mono:
                        camera.out.unlink(neural_network.input)
                    else:
                        camera.preview.unlink(neural_network.input)
                except:
                    continue

                if is_mono:
                    camera.out.link(neural_network.input)
                else:
                    camera.preview.link(neural_network.input)

                self.neural_networks[camera.getBoardSocket().name] = neural_network
                break

    def __setup_mono_camera(
        self,
        camera: dai.node.MonoCamera,
        nn: CameraNNConfig,
        nn_node: dai.node.NeuralNetwork,
    ):
        sensor_name = camera.getBoardSocket().name
        script = self.scripts[sensor_name]

        script.outputs["preview"].link(nn_node.input)

    def __setup_camera(
        self,
        camera: dai.node.ColorCamera | dai.node.Camera,
        nn: CameraNNConfig,
        nn_node: dai.node.NeuralNetwork,
    ):
        sensor_name = camera.getBoardSocket().name
        camera.setPreviewSize(nn.input_shape[:2])
        camera.setInterleaved(False)

        still_queue = self.outputs.get(
            PipelineQueueType.STILL.get_queue_name(sensor_name)
        )

        if still_queue is not None:
            camera.preview.unlink(still_queue.input)
            camera.still.link(still_queue.input)
        camera.setNumFramesPool(2, 2, 3, 3, 2)

        camera.preview.link(nn_node.input)

    def __setup_stereo_camera(
        self, nn: CameraNNConfig, nn_node: dai.node.NeuralNetwork
    ):
        self.scripts[nn.sensor_name].outputs["preview"].link(nn_node.input)

    def add_nn(self, nn: CameraNNConfig):
        sensor_name = nn.sensor_name

        if sensor_name in self.neural_networks:
            self.remove_nn(sensor_name)

        nn_node = nn.create_node(self.pipeline)
        self.neural_networks[sensor_name] = nn_node
        cam_nn_out = self.create_x_link(
            sensor_name, PipelineQueueType.NN, False, False, 1
        )
        nn_node.out.link(cam_nn_out.input)

        if sensor_name.startswith("DEPTH"):
            left, right = sensor_name.split("_")[1:]
            self.add_stereo_pair(f"CAM_{left}", f"CAM_{right}")
            self.__setup_stereo_camera(nn, nn_node)
            return

        if sensor_name not in self.cameras:
            self.add_sensor(nn.sensor)

        cam = self.cameras[sensor_name]

        if isinstance(cam, dai.node.MonoCamera):
            self.__setup_mono_camera(cam, nn, nn_node)
        else:
            self.__setup_camera(cam, nn, nn_node)

    def remove_nn(self, sensor_name: str):
        if sensor_name not in self.neural_networks:
            return

        nn_node = self.neural_networks[sensor_name]
        cam = self.cameras[sensor_name]
        still_queue = self.outputs.get(
            PipelineQueueType.STILL.get_queue_name(sensor_name)
        )

        if not isinstance(cam, dai.node.MonoCamera) and still_queue is not None:
            cam.preview.unlink(nn_node.input)
            cam.still.unlink(still_queue.input)
            cam.preview.link(still_queue.input)
            cam.setPreviewSize(cam.getStillSize())
            cam.setNumFramesPool(2, 2, 3, 3, 0)

        self.pipeline.remove(nn_node)
        del self.neural_networks[sensor_name]
        self.del_queue(sensor_name, PipelineQueueType.NN)

    def remove_sensor(self, sensor):
        self.remove_nn(sensor)

        return super().remove_sensor(sensor)
