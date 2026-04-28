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
    # Cap segmentation mask resolution before JSON-serializing to the client.
    # Frontend upscales smoothly with bilinear filtering, so 256 looks fine
    # even on 1080p displays. Set to None to disable (send native resolution).
    mask_max_dim: int | None = 256
    # Optional cap on WS detection emit rate. handle_detections() still runs
    # every frame (so dashboard counters/thresholds stay correct); only the
    # network send is throttled. Frames carrying newly-fired violation events
    # are always sent regardless of the throttle. None = no throttle.
    throttle_hz: float | None = None
