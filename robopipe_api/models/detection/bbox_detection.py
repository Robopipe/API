from ..base_model import BaseModel


class BBoxDetection(BaseModel):
    label: int
    confidence: float
    coords: tuple[float, float, float, float]


class BBoxDetections(BaseModel):
    detections: list[BBoxDetection]
