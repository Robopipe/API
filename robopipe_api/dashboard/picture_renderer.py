from dataclasses import dataclass
from typing import Literal

import av
import cv2
import numpy as np

HighlightRole = Literal["child", "parent"]

_RED_BGR = (0, 0, 255)
_LABEL_BG = (0, 0, 0)
_LABEL_FG = (255, 255, 255)
_BBOX_THICKNESS = 1
_FONT = cv2.FONT_HERSHEY_SIMPLEX
_FONT_SCALE = 0.3
_FONT_THICKNESS = 1
_LABEL_PAD = 2


def encode_frame_jpeg(video_frame: av.VideoFrame) -> bytes:
    """Encode the frame exactly as received (no annotations) to JPEG q90.

    Event pictures are saved clean; the detections that used to be drawn
    onto them live in dashboard_evaluation_event_detection instead.
    """
    img = video_frame.to_ndarray(format="bgr24")
    success, jpeg = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not success:
        raise RuntimeError("cv2.imencode failed for event picture")
    return bytes(jpeg)


@dataclass(frozen=True)
class Highlight:
    role: HighlightRole
    display_id: int | None
    coords: tuple[float, float, float, float]
    color: tuple[int, int, int] | None = None


def _draw_highlights(img: np.ndarray, highlights: list[Highlight]) -> None:
    """Draw highlight bboxes onto `img` in place.

    `coords` are normalized [0,1] xmin/ymin/xmax/ymax. Each box is tagged
    `#<display_id>` (untagged when display_id is None). Duplicate
    (role, display_id, coords) entries are skipped — a parent referenced by
    multiple child rows is drawn once.
    """
    h, w = img.shape[:2]

    seen: set[tuple[HighlightRole, int | None, tuple[float, float, float, float]]] = (
        set()
    )
    # Draw parents first so child outlines sit on top when they overlap.
    ordered = sorted(highlights, key=lambda hl: 0 if hl.role == "parent" else 1)
    for hl in ordered:
        key = (hl.role, hl.display_id, hl.coords)
        if key in seen:
            continue
        seen.add(key)

        x1, y1, x2, y2 = hl.coords
        px1 = max(0, min(w - 1, int(round(x1 * w))))
        py1 = max(0, min(h - 1, int(round(y1 * h))))
        px2 = max(0, min(w - 1, int(round(x2 * w))))
        py2 = max(0, min(h - 1, int(round(y2 * h))))
        if px2 <= px1 or py2 <= py1:
            continue

        color = _RED_BGR if hl.role == "parent" else (hl.color or _RED_BGR)
        cv2.rectangle(img, (px1, py1), (px2, py2), color, _BBOX_THICKNESS)

        if hl.display_id is None:
            continue

        text = f"#{hl.display_id}"
        (tw, th), baseline = cv2.getTextSize(text, _FONT, _FONT_SCALE, _FONT_THICKNESS)
        label_x = px1
        label_y = py1 - _LABEL_PAD
        # If the label would clip off the top, drop it inside the box.
        if label_y - th - _LABEL_PAD < 0:
            label_y = py1 + th + _LABEL_PAD
        bg_x1 = label_x
        bg_y1 = label_y - th - _LABEL_PAD
        bg_x2 = label_x + tw + 2 * _LABEL_PAD
        bg_y2 = label_y + baseline
        cv2.rectangle(img, (bg_x1, bg_y1), (bg_x2, bg_y2), _LABEL_BG, -1)
        cv2.putText(
            img,
            text,
            (label_x + _LABEL_PAD, label_y),
            _FONT,
            _FONT_SCALE,
            _LABEL_FG,
            _FONT_THICKNESS,
            cv2.LINE_AA,
        )


def render_event_picture(jpeg_bytes: bytes, detections: list[dict]) -> bytes:
    """Draw an event's highlighted detections onto its clean stored JPEG.

    Used by the report export to reproduce the pre-migration burned-in
    pictures. Only rows with a role are drawn: 'parent' as parent,
    'violated_child' and 'violation' as children; plain detections
    (role None) are ignored, matching what the live renderer used to burn in.
    """
    img = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("cv2.imdecode failed for event picture")

    highlights = [
        Highlight(
            role="parent" if d["role"] == "parent" else "child",
            display_id=d.get("display_id"),
            coords=(d["x_min"], d["y_min"], d["x_max"], d["y_max"]),
        )
        for d in detections
        if d.get("role") is not None
    ]
    _draw_highlights(img, highlights)

    success, jpeg = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not success:
        raise RuntimeError("cv2.imencode failed for event picture")
    return bytes(jpeg)
