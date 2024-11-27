from enum import Enum
from typing import Self


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
