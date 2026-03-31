from enum import Enum

from .base_model import BaseModel


class NNType(Enum):
    Generic = "Generic"
    Detection = "Detection"
    SpatialDetection = "SpatialDetection"


class NNGenericConfig(BaseModel):
    use_parser: bool = True


class NNConfig(BaseModel):
    type: NNType
    model_id: int | None = None
    num_inference_threads: int = 2
    nn_config: NNGenericConfig | None = None
