from ..base_model import BaseModel
from .bbox_detection import BBoxDetection


class SegmentationDetection(BBoxDetection):
    pass


class SegmentationDetections(BaseModel):
    detections: list[SegmentationDetection]
    masks: list[list[int]]
