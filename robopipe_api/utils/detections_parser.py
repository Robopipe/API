import base64
import math

import cv2
import depthai as dai
import numpy as np
from depthai_nodes import Classifications

from ..models.detection.bbox_detection import BBoxDetection, BBoxDetections
from ..models.detection.segmentation_detection import (
    SegmentationDetection,
    SegmentationDetections,
)


def _parse_rect(rect: dai.RotatedRect) -> list[float]:
    """Axis-aligned [xmin, ymin, xmax, ymax] hull of a normalized RotatedRect."""
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


def _downsample_mask(mask: np.ndarray, max_dim: int | None) -> np.ndarray:
    """Resize an index mask to fit within max_dim on its longest side.

    Uses INTER_NEAREST so integer index values and the background sentinel
    (-1 or 255 depending on the source convention) are preserved exactly
    (no interpolation across labels). A no-op when max_dim is None or the
    mask is already smaller.
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
    """Base64-encode a detection-index mask as a single-channel PNG.

    The mask is shifted so the -1 background sentinel maps to 0 and index N
    maps to N+1, then stored as uint8. PNG's filter + deflate exploits the
    spatial coherence of segmentation masks (long runs of identical values),
    typically yielding ~30× smaller payloads than a JSON nested int array.

    Returns None on encode failure or if the mask has more than 254 indices
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


def _mask_fields(mask: np.ndarray) -> dict:
    """Wire fields for a detection-index mask (-1 = background)."""
    masks_png = _encode_mask_png(mask)
    h, w = mask.shape[:2]
    fields: dict = {
        "mask_width": int(w),
        "mask_height": int(h),
        "masks_png": masks_png,
        "masks": None,
    }
    if masks_png is None:
        # Fallback for masks with > 254 labels or PNG encode failure: emit
        # the legacy nested int array. Old clients keep working too.
        fields["masks"] = mask.tolist()

    return fields


def _build_segmentation_detections(
    detections: list[SegmentationDetection],
    mask: np.ndarray,
) -> SegmentationDetections:
    """Package detections plus a detection-index mask (-1 = background)."""
    res = SegmentationDetections(detections=detections, **_mask_fields(mask))
    res._index_mask = mask
    return res


def reindex_segmentation_masks(
    detections: SegmentationDetections,
    kept: list[SegmentationDetection],
) -> dict | None:
    """Re-encode the wire mask fields so values reference `kept`.

    The mask encodes 1-based positions into the detections list; when the
    dashboard handler filters or reorders that list, the mask must be
    remapped or every pixel resolves to the wrong detection. `kept` must
    contain object-identical members of `detections.detections`. Pixels of
    dropped detections become background. Returns None when there is no
    mask to remap.
    """
    mask = detections._index_mask
    if mask is None:
        return None
    new_pos = {id(d): i for i, d in enumerate(kept)}
    # One extra slot at the end: the -1 background sentinel indexes it,
    # mapping background to background.
    lut = np.full(len(detections.detections) + 1, -1, dtype=np.int16)
    for i, detection in enumerate(detections.detections):
        lut[i] = new_pos.get(id(detection), -1)

    return _mask_fields(lut[mask])


def parse_img_detections(
    detections: dai.ImgDetections,
    mask_max_dim: int | None = None,
) -> BBoxDetections | SegmentationDetections:
    raw_mask = detections.getCvSegmentationMask()
    detection_cls = BBoxDetection if raw_mask is None else SegmentationDetection

    def parse_detection(detection: dai.ImgDetection):
        res = {
            "label": detection.label,
            "confidence": detection.confidence,
            "coords": [detection.xmin, detection.ymin, detection.xmax, detection.ymax],
        }

        return detection_cls(**res)

    parsed = list(map(parse_detection, detections.detections))
    if raw_mask is None:
        return BBoxDetections(detections=parsed)

    # Instance-segmentation models embed a mask plane whose values are the
    # index of the owning detection, with 255 as background; shift to the
    # internal -1-background convention before encoding.
    raw_mask = _downsample_mask(raw_mask, mask_max_dim)
    mask = raw_mask.astype(np.int16)
    mask[raw_mask == 255] = -1

    return _build_segmentation_detections(parsed, mask)


def parse_segmentation_mask(
    segmentation_mask: dai.SegmentationMask,
    mask_max_dim: int | None = None,
) -> SegmentationDetections:
    # hasValidMask() is True even on a default-constructed message; the
    # reliable emptiness signal is getCvMask() returning None.
    raw_mask = segmentation_mask.getCvMask()
    if raw_mask is None or raw_mask.size == 0:
        return SegmentationDetections(detections=[])

    detections: list[SegmentationDetection] = []
    # LUT from mask class index to the wire mask value: the first detection of
    # each class. The client resolves colors via "value N -> detections[N-1]"
    # and every region of a class shares its label, so pointing all of a
    # class's pixels at its first detection keeps the overlay correct without
    # relabeling per region. Index 255 (background) stays -1.
    class_to_detection = np.full(256, -1, dtype=np.int16)
    for class_idx in segmentation_mask.getUniqueIndices():
        # One box per connected region of the class, normalized coordinates.
        rects = segmentation_mask.getBoundingBoxes(class_idx)
        if not rects:
            continue
        class_to_detection[class_idx] = len(detections)
        for rect in rects:
            # A semantic mask carries no per-object confidence; 1.0 keeps the
            # detections visible through the dashboard confidence filter.
            detections.append(
                SegmentationDetection(
                    label=class_idx,
                    confidence=1.0,
                    coords=_parse_rect(rect),
                )
            )

    raw_mask = _downsample_mask(raw_mask, mask_max_dim)

    return _build_segmentation_detections(detections, class_to_detection[raw_mask])


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
    detections: dai.ImgDetections | Classifications | dai.SegmentationMask,
    mask_max_dim: int | None = None,
):
    if isinstance(detections, dai.ImgDetections):
        return parse_img_detections(detections, mask_max_dim=mask_max_dim)
    elif isinstance(detections, Classifications):
        return parse_classifications(detections)
    elif isinstance(detections, dai.SegmentationMask):
        return parse_segmentation_mask(detections, mask_max_dim=mask_max_dim)
    else:
        raise ValueError("Unsupported detections type")
