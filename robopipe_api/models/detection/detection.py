from typing import Union

from ..base_model import BaseModel
from .bbox_detection import BBoxDetection, BBoxDetections
from .segmentation_detection import SegmentationDetection, SegmentationDetections
from .dashboard_detection import DashboardDetection

BaseNNDetections = Union[BBoxDetections, SegmentationDetections]


class NNDetections(BaseModel):
    detections: list[BBoxDetection] | list[SegmentationDetection]
    masks: list[list[int]] | None = None
    dashboard_detections: list[DashboardDetection] | None = None
