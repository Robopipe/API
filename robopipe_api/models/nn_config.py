from pydantic import model_validator

from enum import Enum
from typing import Any

from .base_model import BaseModel


class NNType(Enum):
    Generic = "Generic"
    Detection = "Detection"
    SpatialDetection = "SpatialDetection"


class NNGenericConfig(BaseModel):
    use_parser: bool = True
    pass


class NNDetectionConfig(BaseModel):
    pass


class NNSpatialDetectionConfig(BaseModel):
    pass


class NNConfig(BaseModel):
    type: NNType
    num_inference_threads: int = 2
    nn_config: NNGenericConfig | NNDetectionConfig | NNSpatialDetectionConfig = None
