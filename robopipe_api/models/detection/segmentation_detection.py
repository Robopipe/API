from typing import Any

from pydantic import PrivateAttr

from ..base_model import BaseModel
from .bbox_detection import BBoxDetection


class SegmentationDetection(BBoxDetection):
    pass


class SegmentationDetections(BaseModel):
    detections: list[SegmentationDetection]
    # Raw downsampled index mask (numpy int array, value = detection index,
    # -1 = background). Kept off the wire; the dashboard handler needs it to
    # re-encode masks_png after confidence filtering reorders/drops
    # detections, so mask values keep pointing at the right entries.
    _index_mask: Any = PrivateAttr(default=None)
    # Compact PNG-encoded mask: single-channel uint8 where pixel value 0
    # means background and value N means detections[N - 1]. Upstream DepthAI
    # masks use 255 for background (dai.SegmentationMask class maps and
    # dai.ImgDetections embedded instance maps); the parser remaps them into
    # this 0-based convention before encoding. PNG's spatial filter +
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
