import depthai as dai

from .pipeline_queue_type import PipelineQueueType


class Pipeline:
    def __init__(self, pipeline: dai.Pipeline | None = None):
        self.pipeline = pipeline or dai.Pipeline()
        self.input_queues: dict[str, dict[PipelineQueueType, str]] = {}
        self.output_queues: dict[str, dict[PipelineQueueType, str]] = {}
        self.cameras: dict[
            str, dai.node.ColorCamera | dai.node.MonoCamera | dai.node.Camera
        ] = {}
        self.inputs: dict[str, dai.node.XLinkIn] = {}
        self.outputs: dict[str, dai.node.XLinkOut] = {}

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
            elif isinstance(node, dai.node.XLinkIn):
                self.__add_queue_from_name(node.getStreamName(), True)
                self.inputs[node.getStreamName()] = node
            elif isinstance(node, dai.node.XLinkOut):
                self.__add_queue_from_name(node.getStreamName(), False)
                self.outputs[node.getStreamName()] = node

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

        if input:
            x_link.setMaxDataSize(1)
            self.inputs[x_link_queue] = x_link
        else:
            x_link.input.setBlocking(blocking)
            x_link.input.setQueueSize(queue_size)
            self.outputs[x_link_queue] = x_link

        self.__add_queue_from_name(x_link_queue, input)

        return x_link

    def del_queue(self, sensor_name: str, queue_type: PipelineQueueType):
        queue_name = queue_type.get_queue_name(sensor_name)

        if queue_name in self.inputs:
            nodes = self.inputs
            queues = self.input_queues
        elif queue_name in self.outputs:
            nodes = self.outputs
            queues = self.output_queues
        else:
            return

        self.pipeline.remove(nodes[queue_name])
        del nodes[queue_name]
        del queues[sensor_name][queue_type]

    def del_all_queues(self, sensor_name: str):
        for queue_type in PipelineQueueType:
            try:
                self.del_queue(sensor_name, queue_type)
            except:
                pass

        del self.input_queues[sensor_name]
        del self.output_queues[sensor_name]


class EmptyPipeline(Pipeline):
    pass
