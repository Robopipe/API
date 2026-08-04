from typing import Union

from ..base_model import BaseModel
from .bbox_detection import BBoxDetection, BBoxDetections
from .segmentation_detection import SegmentationDetection, SegmentationDetections

BaseNNDetections = Union[BBoxDetections, SegmentationDetections]


class NNDetections(BaseModel):
    detections: list[BBoxDetection] | list[SegmentationDetection]
    masks: list[list[int]] | None = None
