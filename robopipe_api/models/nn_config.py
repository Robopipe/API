from enum import Enum

from .base_model import BaseModel
from .sahi_config import SAHIConfig


class NNType(Enum):
    Generic = "Generic"
    Detection = "Detection"
    SpatialDetection = "SpatialDetection"


class NNGenericConfig(BaseModel):
    use_parser: bool = True
    sahi_config: SAHIConfig | None = None


class NNConfig(BaseModel):
    type: NNType
    model_id: int | None = None
    num_inference_threads: int = 2
    nn_config: NNGenericConfig | None = None
