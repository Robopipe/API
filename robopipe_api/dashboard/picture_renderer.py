from dataclasses import dataclass
from typing import Literal

import av
import cv2


HighlightRole = Literal["child", "parent"]

_RED_BGR = (0, 0, 255)
_BLUE_BGR = (255, 0, 0)
_LABEL_BG = (0, 0, 0)
_LABEL_FG = (255, 255, 255)
_BBOX_THICKNESS = 1
_FONT = cv2.FONT_HERSHEY_DUPLEX
_FONT_SCALE = 0.35
_FONT_THICKNESS = 1
_LABEL_PAD = 3


@dataclass(frozen=True)
class Highlight:
    role: HighlightRole
    display_id: int
    coords: tuple[float, float, float, float]


def render_violation_picture(
    video_frame: av.VideoFrame,
    highlights: list[Highlight],
) -> bytes:
    """Draw the violating bboxes onto a copy of `video_frame` and return JPEG bytes.

    `coords` are normalized [0,1] xmin/ymin/xmax/ymax. Children draw red,
    parents draw blue; each box is annotated with `#<display_id>`. Duplicate
    (role, display_id) entries are skipped — a parent referenced by multiple
    child rows is drawn once.
    """
    img = video_frame.to_ndarray(format="bgr24")
    h, w = img.shape[:2]

    seen: set[tuple[HighlightRole, int]] = set()
    # Draw parents first so child outlines sit on top when they overlap.
    ordered = sorted(highlights, key=lambda hl: 0 if hl.role == "parent" else 1)
    for hl in ordered:
        key = (hl.role, hl.display_id)
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

        color = _BLUE_BGR if hl.role == "parent" else _RED_BGR
        cv2.rectangle(img, (px1, py1), (px2, py2), color, _BBOX_THICKNESS)

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

    success, jpeg = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not success:
        raise RuntimeError("cv2.imencode failed for violation picture")
    return bytes(jpeg)
