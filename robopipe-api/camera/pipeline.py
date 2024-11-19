import depthai as dai

from enum import Enum
from typing import Self

from .nn import CameraNNConfig


class PipelineQueueType(Enum):
    CONFIG = "config"
    CONTROL = "control"
    STILL = "still"
    PREVIEW = "preview"
    VIDEO = "video"
    NN = "nn"
    NN_PASSTHROUGH = "nn_passthrough"

    def get_queue_name(self, sensor_name: str) -> str:
        return self.value + "@" + sensor_name

    @classmethod
    def parse_queue_name(cls, queue_name: str) -> tuple[Self, str]:
        queue_type, sensor_name = queue_name.split("@")

        return (cls(queue_type), sensor_name)


class Pipeline:
    def __init__(self, pipeline: dai.Pipeline | None = None):
        self.pipeline = pipeline or dai.Pipeline()
        self.input_queues: dict[str, dict[PipelineQueueType, str]] = {}
        self.output_queues: dict[str, dict[PipelineQueueType, str]] = {}
        self.cameras: dict[
            str, dai.node.ColorCamera | dai.node.MonoCamera | dai.node.Camera
        ] = {}
        self.extract_properties()

    def __add_queue(self, queue_type: PipelineQueueType, sensor_name: str, input: bool):
        queues = self.input_queues if input else self.output_queues

        if sensor_name not in queues:
            queues[sensor_name] = {}

        queues[sensor_name][queue_type] = queue_type.get_queue_name(sensor_name)

    def __add_queue_from_name(self, queue_name: str, input: bool):
        self.__add_queue(*PipelineQueueType.parse_queue_name(queue_name), input)

    def extract_properties(self):
        nodes = self.pipeline.getAllNodes()

        for node in nodes:
            if isinstance(
                node, (dai.node.ColorCamera, dai.node.MonoCamera, dai.node.Camera)
            ):
                self.cameras[node.getBoardSocket().name] = node
            elif isinstance(node, (dai.node.XLinkIn, dai.node.XLinkOut)):
                self.__add_queue_from_name(
                    node.getStreamName(), isinstance(node, dai.node.XLinkIn)
                )

    def create_x_link(
        self,
        sensor_name: str,
        queue_type: PipelineQueueType,
        input: bool,
        blocking: bool = True,
        queue_size: int = 30,
    ) -> dai.node.XLinkIn | dai.node.XLinkOut:
        x_link_queue = queue_type.get_queue_name(sensor_name)
        x_link = (
            self.pipeline.createXLinkIn() if input else self.pipeline.createXLinkOut()
        )
        x_link.setStreamName(x_link_queue)

        if not input:
            x_link.input.setBlocking(blocking)
            x_link.input.setQueueSize(queue_size)
        else:
            x_link.setMaxDataSize(1)

        self.__add_queue_from_name(x_link_queue, input)

        return x_link


class EmptyPipeline(Pipeline):
    pass


class StreamingPipeline(Pipeline):
    def __init__(
        self, sensors: list[dai.CameraFeatures], pipeline: dai.Pipeline | None = None
    ):
        super().__init__(pipeline)

        for sensor in sensors:
            self.add_sensor(sensor)

    def add_sensor(self, sensor: dai.CameraFeatures):
        sensor_name = sensor.socket.name

        cam_control = self.create_x_link(sensor_name, PipelineQueueType.CONTROL, True)
        cam_still = self.create_x_link(sensor_name, PipelineQueueType.STILL, False)
        cam_video = self.create_x_link(
            sensor_name, PipelineQueueType.VIDEO, False, False, 1
        )

        if dai.CameraSensorType.COLOR in sensor.supportedTypes:
            cam_config = self.create_x_link(sensor_name, PipelineQueueType.CONFIG, True)

            cam = self.pipeline.createColorCamera()
            cam.setNumFramesPool(2, 2, 3, 3, 2)
            cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)

            cam_config.out.link(cam.inputConfig)
            cam.still.link(cam_still.input)
            cam.video.link(cam_video.input)
        elif dai.CameraSensorType.MONO in sensor.supportedTypes:
            cam = self.pipeline.createMonoCamera()
            cam.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
            cam.setNumFramesPool(10)

            cam_still.input.setBlocking(False)
            cam_still.input.setQueueSize(1)
            script = self.pipeline.createScript()
            script.setScript(
                """
                    while True:
                        frame = node.io['in'].get()
                        node.io['video'].send(frame)
                        node.io['still'].send(frame)
                """
            )

            script.inputs["in"].setBlocking(False)
            script.inputs["in"].setQueueSize(1)
            cam.out.link(script.inputs["in"])
            script.outputs["still"].link(cam_still.input)
            script.outputs["video"].link(cam_video.input)
        else:
            return

        cam.setBoardSocket(sensor.socket)
        self.cameras[sensor_name] = cam

        cam_control.out.link(cam.inputControl)


class NNPipeline(Pipeline):
    def __init__(
        self, networks: list[CameraNNConfig], pipeline: dai.Pipeline | None = None
    ):
        super().__init__(pipeline)

        for nn in networks:
            self.add_nn(nn)

    def add_nn(self, nn: CameraNNConfig):
        sensor_name = nn.sensor.name

        if sensor_name not in self.cameras:
            cam = self.pipeline.createColorCamera()
            cam.setBoardSocket(nn.sensor)
            self.cameras[sensor_name] = cam
        else:
            cam = self.cameras[sensor_name]

        cam.setPreviewSize(nn.input_shape[:2])
        cam.setInterleaved(False)

        nn_node = nn.create_node(self.pipeline)

        cam_nn_out = self.create_x_link(sensor_name, PipelineQueueType.NN, False)
        cam_nn_passthrough = self.create_x_link(
            sensor_name, PipelineQueueType.NN_PASSTHROUGH, False
        )

        cam.preview.link(nn_node.input)
        nn_node.out.link(cam_nn_out.input)
        nn_node.passthrough.link(cam_nn_passthrough.input)
