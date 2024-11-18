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
        return sensor_name + "@" + self.value

    @classmethod
    def parse_queue_name(cls, queue_name: str) -> tuple[str, Self]:
        sensor_name, queue_type = queue_name.split("@")

        return (sensor_name, cls(queue_type))


class Pipeline:
    def __init__(self, pipeline: dai.Pipeline = dai.Pipeline()):
        self.pipeline = pipeline
        self.input_queues: dict[str, dict[PipelineQueueType, str]] = {}
        self.output_queues: dict[str, dict[PipelineQueueType, str]] = {}
        self.cameras: dict[
            str, dai.node.ColorCamera | dai.node.MonoCamera | dai.node.Camera
        ] = {}
        self.extract_properties()

    def __add_queue(self, sensor_name: str, queue_type: PipelineQueueType, input: bool):
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
    def __init__(self, sensors: list[dai.CameraFeatures]):
        super().__init__()

        for sensor in sensors:
            self.add_sensor(sensor)

    def add_sensor(self, sensor: dai.CameraFeatures):
        sensor_name = sensor.socket.name

        if dai.CameraSensorType.COLOR not in sensor.supportedTypes:
            return

        cam = self.pipeline.createColorCamera()
        cam.setBoardSocket(sensor.socket)
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam.setFps(35)
        # cam.setNumFramesPool(2, 2, 3, 3, 2)
        self.cameras[sensor_name] = cam

        cam_config = self.create_x_link(sensor_name, PipelineQueueType.CONFIG, True)
        cam_control = self.create_x_link(sensor_name, PipelineQueueType.CONTROL, True)

        cam_still = self.create_x_link(sensor_name, PipelineQueueType.STILL, False)

        cam_preview = self.create_x_link(
            sensor_name, PipelineQueueType.PREVIEW, False, False, 1
        )

        cam_video = self.create_x_link(
            sensor_name, PipelineQueueType.VIDEO, False, False, 1
        )

        cam_config.out.link(cam.inputConfig)
        cam_control.out.link(cam.inputControl)
        cam.preview.link(cam_preview.input)
        cam.video.link(cam_video.input)
        cam.still.link(cam_still.input)


class NNPipeline(Pipeline):
    def __init__(self, networks: list[CameraNNConfig]):
        super().__init__()

        for nn in networks:
            self.add_nn(nn)

    def add_nn(self, nn: CameraNNConfig):
        sensor_name = nn.sensor.name
        self.input_queues[sensor_name] = {}
        self.output_queues[sensor_name] = {}

        cam = self.pipeline.createColorCamera()
        cam.setBoardSocket(nn.sensor)
        cam.setPreviewSize(nn.input_shape[:2])
        cam.setInterleaved(False)
        self.cameras[sensor_name] = cam
        nn_node = nn.create_node(self.pipeline)

        cam_nn_out_queue = PipelineQueueType.NN.getQueueName(sensor_name)
        cam_nn_out = self.pipeline.createXLinkOut()
        cam_nn_out.setStreamName(cam_nn_out_queue)
        self.output_queues[sensor_name][PipelineQueueType.NN] = cam_nn_out_queue

        cam_nn_passthrough_queue = PipelineQueueType.NN_PASSTHROUGH.getQueueName(
            sensor_name
        )
        cam_nn_passthrough = self.pipeline.createXLinkOut()
        cam_nn_passthrough.setStreamName(cam_nn_passthrough_queue)
        self.output_queues[sensor_name][
            PipelineQueueType.NN_PASSTHROUGH
        ] = cam_nn_passthrough_queue

        cam.preview.link(nn_node.input)
        nn_node.out.link(cam_nn_out.input)
        nn_node.passthrough.link(cam_nn_passthrough.input)
