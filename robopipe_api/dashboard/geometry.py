from __future__ import annotations

from ..models.dashboard.eval_models import EvalLimitItemEdge


def bbox_area(coords: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = coords
    return max(0, x2 - x1) * max(0, y2 - y1)


def bbox_iou(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    inter_x1 = max(a[0], b[0])
    inter_y1 = max(a[1], b[1])
    inter_x2 = min(a[2], b[2])
    inter_y2 = min(a[3], b[3])
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)

    area_a = bbox_area(a)
    area_b = bbox_area(b)
    union = area_a + area_b - inter_area

    if union <= 0:
        return 0.0
    return inter_area / union


def bbox_center(coords: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = coords
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def bbox_dimensions(coords: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = coords
    return (x2 - x1, y2 - y1)


def euclidean_distance(c1: tuple[float, float], c2: tuple[float, float]) -> float:
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5


def is_within_bbox(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
) -> bool:
    """Check if the center of inner bbox falls within the outer bbox."""
    cx, cy = bbox_center(inner)
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]


def compute_position_pct(
    target_coords: tuple[float, float, float, float],
    reference_coords: tuple[float, float, float, float],
    target_edge: EvalLimitItemEdge,
    parent_edge: EvalLimitItemEdge,
) -> float:
    """Unsigned edge-to-edge distance as a percentage of the parent's relevant dimension.

    Axis is determined by whichever edge is non-CENTER:
      LEFT or RIGHT → X-axis (divisor = parent width)
      TOP or BOTTOM → Y-axis (divisor = parent height)
      CENTER + CENTER → max off-center deviation: max(|dx|/(rw/2), |dy|/(rh/2)) × 100
    """
    tx1, ty1, tx2, ty2 = target_coords
    rx1, ry1, rx2, ry2 = reference_coords
    rw = rx2 - rx1
    rh = ry2 - ry1

    if target_edge == EvalLimitItemEdge.CENTER and parent_edge == EvalLimitItemEdge.CENTER:
        if rw == 0 or rh == 0:
            return 0.0
        tcx, tcy = bbox_center(target_coords)
        rcx = (rx1 + rx2) / 2
        rcy = (ry1 + ry2) / 2
        return max(
            abs(tcx - rcx) / (rw / 2) * 100,
            abs(tcy - rcy) / (rh / 2) * 100,
        )

    x_axis = (
        target_edge in (EvalLimitItemEdge.LEFT, EvalLimitItemEdge.RIGHT)
        or parent_edge in (EvalLimitItemEdge.LEFT, EvalLimitItemEdge.RIGHT)
    )
    if x_axis:
        if rw == 0:
            return 0.0
        t = tx1 if target_edge == EvalLimitItemEdge.LEFT else (tx2 if target_edge == EvalLimitItemEdge.RIGHT else (tx1 + tx2) / 2)
        r = rx1 if parent_edge == EvalLimitItemEdge.LEFT else (rx2 if parent_edge == EvalLimitItemEdge.RIGHT else (rx1 + rx2) / 2)
        return abs(t - r) / rw * 100
    else:
        if rh == 0:
            return 0.0
        t = ty1 if target_edge == EvalLimitItemEdge.TOP else (ty2 if target_edge == EvalLimitItemEdge.BOTTOM else (ty1 + ty2) / 2)
        r = ry1 if parent_edge == EvalLimitItemEdge.TOP else (ry2 if parent_edge == EvalLimitItemEdge.BOTTOM else (ry1 + ry2) / 2)
        return abs(t - r) / rh * 100


def value_within_limits(
    value: float,
    limit_from: float | None,
    limit_to: float | None,
) -> bool:
    if limit_from is not None and value < limit_from:
        return False
    if limit_to is not None and value > limit_to:
        return False
    return True
