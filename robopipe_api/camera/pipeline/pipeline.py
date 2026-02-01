import depthai as dai
from typing import Any

from ...error import PipelineException
from .pipeline_queue_type import PipelineQueueType


class Pipeline:
    def __init__(
        self, pipeline: dai.Pipeline | None = None, device: dai.Device | None = None
    ):
        if pipeline is None and device is None:
            raise PipelineException(
                "Either a pipeline or device must be provided to initialize the Pipeline."
            )

        self.pipeline = pipeline or dai.Pipeline(device)
        self.input_queues: dict[str, dict[PipelineQueueType, str]] = {}
        self.output_queues: dict[str, dict[PipelineQueueType, str]] = {}
        self.cameras: dict[str, dai.node.Camera] = {}
        # In v3, queues are objects returned by createInputQueue/createOutputQueue
        # not node types, so we use Any for the type hint
        self.inputs: dict[str, Any] = {}
        self.outputs: dict[str, Any] = {}

        # Note: setXLinkChunkSize may not be needed in v3 (XLink is automatic)
        # Keeping for compatibility, can be removed if it causes issues
        try:
            self.pipeline.setXLinkChunkSize(0)
        except AttributeError:
            pass  # Method doesn't exist in v3
        self.extract_properties()

    def add_queue(
        self,
        queue,
        queue_type: PipelineQueueType,
        sensor_name: str,
        input: bool,
    ):
        queues = self.input_queues if input else self.output_queues

        if sensor_name not in queues:
            queues[sensor_name] = {}

        queues[sensor_name][queue_type] = queue_type.get_queue_name(sensor_name)

        if input:
            self.inputs[queues[sensor_name][queue_type]] = queue
        else:
            self.outputs[queues[sensor_name][queue_type]] = queue

    def __add_queue_from_name(self, queue_name: str, input: bool):
        self.__add_queue(*PipelineQueueType.parse_queue_name(queue_name), input)

    def get_input_queue(self, queue_name: str):
        return self.inputs[queue_name]

    def get_output_queue(self, queue_name: str):
        return self.outputs[queue_name]

    def extract_properties(self):
        nodes = self.pipeline.getAllNodes()

        for node in nodes:
            if isinstance(node, dai.node.Camera):
                self.cameras[node.getBoardSocket().name] = node
            # In v3, queues are not nodes - they're created via createOutputQueue()
            # and stored directly in self.inputs/self.outputs when add_queue is called

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

        if sensor_name in self.input_queues:
            del self.input_queues[sensor_name]
        if sensor_name in self.output_queues:
            del self.output_queues[sensor_name]


class EmptyPipeline(Pipeline):
    pass
