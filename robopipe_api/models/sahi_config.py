from pydantic import Field

from .base_model import BaseModel


class SAHIConfig(BaseModel):
    slice_width: float = Field(0.5, gt=0.0, le=1.0)
    slice_height: float = Field(0.5, gt=0.0, le=1.0)
    overlap_ratio: float = Field(0.2, ge=0.0, lt=0.5)
    nms_iou_threshold: float = Field(0.5, gt=0.0, le=1.0)
