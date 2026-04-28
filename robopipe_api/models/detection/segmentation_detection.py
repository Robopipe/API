from ..base_model import BaseModel
from .bbox_detection import BBoxDetection


class SegmentationDetection(BBoxDetection):
    pass


class SegmentationDetections(BaseModel):
    detections: list[SegmentationDetection]
    # Compact PNG-encoded mask: single-channel uint8 where pixel value 0
    # means background and value N means detections[N - 1] (i.e. label
    # index + 1, so -1 background fits in uint8). PNG's spatial filter +
    # deflate compresses dense masks ~30× vs the legacy nested int array.
    # Sent as a base64 string inside the JSON envelope so the existing WS
    # relay schema is unchanged.
    masks_png: str | None = None
    # Mask resolution, sent so the client can size its canvas without having
    # to decode the PNG header first.
    mask_width: int | None = None
    mask_height: int | None = None
    # Legacy nested-int representation. Retained for backward compatibility
    # with older clients; new server output sets it to None.
    masks: list[list[int]] | None = None
