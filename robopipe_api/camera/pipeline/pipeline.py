import depthai as dai

from typing import Self

from .pipeline_queue_type import PipelineQueueType


class Pipeline:
    def __init__(
        self,
        device: dai.Device,
        pipeline: Self | None = None,
    ):
        self.input_queues: dict[str, dict[PipelineQueueType, str]] = {}
        self.output_queues: dict[str, dict[PipelineQueueType, str]] = {}
        self.inputs: dict[str, dai.InputQueue] = {}
        self.outputs: dict[str, dai.MessageQueue] = {}
        self.cameras: dict[str, dai.node.Camera] = {}
        self.pipeline = dai.Pipeline(device)
        self.pipeline.setXLinkChunkSize(0)

        if pipeline is not None:
            self.recreate(pipeline)

    def recreate(self, pipeline: Self):
        pass

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
