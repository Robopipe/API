from pydantic import BaseModel, model_validator

from enum import Enum
from typing import Any


class NNType(Enum):
    Generic = "Generic"
    YOLO = "YOLO"
    MobileNet = "MobileNet"


class NNYoloConfig(BaseModel):
    anchor_masks: dict[str, list[int]] | None = None
    anchors: list[float] | None = None
    coordinate_size: int | None = None
    confidence_threshold: float | None = None
    iou_threshold: float | None = None
    num_classes: int | None = None

    @model_validator(mode="before")
    @classmethod
    def check_nn_type(cls, data: Any, info: Any) -> Any:
        if info.data.get("type") != NNType.YOLO:
            raise ValueError("nn type and nn config mismatch")

        return data


class NNMobileNetConfig(BaseModel):
    confidence_threshold: float | None = None

    @model_validator(mode="before")
    @classmethod
    def check_nn_type(cls, data: Any, info: Any) -> Any:
        if info.data.get("type") != NNType.MobileNet:
            raise ValueError("nn type and nn config mismatch")

        return data


class NNConfig(BaseModel):
    type: NNType
    num_inference_threads: int = 2
    nn_config: NNYoloConfig | NNMobileNetConfig | None = None
