import base64
import math

import cv2
import depthai as dai
import numpy as np
from depthai_nodes import Classifications, ImgDetectionsExtended, ImgDetectionExtended

from ..models.detection.bbox_detection import BBoxDetection, BBoxDetections
from ..models.detection.segmentation_detection import (
    SegmentationDetection,
    SegmentationDetections,
)


def parse_img_detections(detections: dai.ImgDetections) -> BBoxDetections:
    def parse_detection(detection: dai.ImgDetection) -> BBoxDetection:
        res = {
            "label": detection.label,
            "confidence": detection.confidence,
            "coords": [detection.xmin, detection.ymin, detection.xmax, detection.ymax],
        }

        return BBoxDetection(**res)

    return BBoxDetections(detections=list(map(parse_detection, detections.detections)))


def _downsample_mask(mask: np.ndarray, max_dim: int | None) -> np.ndarray:
    """Resize a label-index mask to fit within max_dim on its longest side.

    Uses INTER_NEAREST so integer detection indices and the -1 background
    sentinel are preserved exactly (no interpolation across labels). A no-op
    when max_dim is None or the mask is already smaller.
    """
    if max_dim is None:
        return mask
    h, w = mask.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return mask
    scale = max_dim / longest
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)


def _encode_mask_png(mask: np.ndarray) -> str | None:
    """Base64-encode a label-index mask as a single-channel PNG.

    The mask is shifted so the -1 background sentinel maps to 0 and label N
    maps to N+1, then stored as uint8. PNG's filter + deflate exploits the
    spatial coherence of segmentation masks (long runs of identical values),
    typically yielding ~30× smaller payloads than a JSON nested int array.

    Returns None on encode failure or if the mask has more than 254 labels
    (won't fit in uint8 after the +1 shift).
    """
    if mask.size == 0:
        return None
    if mask.max() > 253:
        # Out of range for the +1 shift; bail and let the caller fall back
        # to the legacy array representation.
        return None
    shifted = (mask.astype(np.int32) + 1).astype(np.uint8)
    success, png_bytes = cv2.imencode(".png", shifted)
    if not success:
        return None
    return base64.b64encode(png_bytes.tobytes()).decode("ascii")


def parse_img_detections_extended(
    img_detections_extended: ImgDetectionsExtended,
    mask_max_dim: int | None = None,
) -> SegmentationDetections:
    def parse_rect(rect: dai.RotatedRect) -> list[float]:
        cx, cy = rect.center.x, rect.center.y
        w, h = rect.size.width, rect.size.height
        angle_rad = math.radians(rect.angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # Half dimensions
        hw, hh = w / 2, h / 2

        # Four corners of the rotated rectangle
        corners_x = [
            cx + dx * cos_a - dy * sin_a
            for dx, dy in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        ]
        corners_y = [
            cy + dx * sin_a + dy * cos_a
            for dx, dy in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        ]

        xmin = min(corners_x)
        ymin = min(corners_y)
        xmax = max(corners_x)
        ymax = max(corners_y)

        return [xmin, ymin, xmax, ymax]

    def parse_detection(detection: ImgDetectionExtended):
        rotated_rect = detection.rotated_rect
        coords = parse_rect(rotated_rect)
        res = {
            "label": detection.label,
            "confidence": detection.confidence,
            "coords": coords,
        }

        return SegmentationDetection(**res)

    masks = _downsample_mask(img_detections_extended.masks, mask_max_dim)
    masks_png = _encode_mask_png(masks)
    h, w = masks.shape[:2]
    res: dict = {
        "detections": list(map(parse_detection, img_detections_extended.detections)),
        "mask_width": int(w),
        "mask_height": int(h),
    }
    if masks_png is not None:
        res["masks_png"] = masks_png
    else:
        # Fallback for masks with > 254 labels or PNG encode failure: emit
        # the legacy nested int array. Old clients keep working too.
        res["masks"] = masks.tolist()

    return SegmentationDetections(**res)


def parse_classifications(classifications: Classifications):
    # For now, we will just return the top classification as a bbox detection with full frame coords
    if len(classifications.classifications) == 0:
        return BBoxDetections(detections=[])

    classification = classifications.classifications[0]
    res = {
        "label": classification.label,
        "confidence": classification.confidence,
        "coords": [0, 0, 1, 1],
    }

    return BBoxDetections(detections=[BBoxDetection(**res)])


def parse_detections(
    detections: dai.ImgDetections | Classifications | ImgDetectionsExtended,
    mask_max_dim: int | None = None,
):
    if isinstance(detections, dai.ImgDetections):
        return parse_img_detections(detections)
    elif isinstance(detections, Classifications):
        return parse_classifications(detections)
    elif isinstance(detections, ImgDetectionsExtended):
        return parse_img_detections_extended(detections, mask_max_dim=mask_max_dim)
    else:
        raise ValueError("Unsupported detections type")
