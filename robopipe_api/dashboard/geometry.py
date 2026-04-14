from __future__ import annotations

from ..models.dashboard.eval_models import EvalLimitItemParameter


def bbox_area(coords: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = coords
    return max(0, x2 - x1) * max(0, y2 - y1)


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
    parameter: EvalLimitItemParameter,
) -> float:
    """Compute position of a detection center as percentage within reference bbox.

    POS_LEFT:   % from left edge   (0 = left, 100 = right)
    POS_RIGHT:  % from right edge  (0 = right, 100 = left)
    POS_TOP:    % from top edge    (0 = top, 100 = bottom)
    POS_BOTTOM: % from bottom edge (0 = bottom, 100 = top)
    POS_CENTER: max of x/y distance from center as % of half-dimension
    """
    tcx, tcy = bbox_center(target_coords)
    rx1, ry1, rx2, ry2 = reference_coords
    rw = rx2 - rx1
    rh = ry2 - ry1

    if rw == 0 or rh == 0:
        return 0.0

    if parameter == EvalLimitItemParameter.POS_LEFT:
        return ((tcx - rx1) / rw) * 100
    elif parameter == EvalLimitItemParameter.POS_RIGHT:
        return ((rx2 - tcx) / rw) * 100
    elif parameter == EvalLimitItemParameter.POS_TOP:
        return ((tcy - ry1) / rh) * 100
    elif parameter == EvalLimitItemParameter.POS_BOTTOM:
        return ((ry2 - tcy) / rh) * 100
    elif parameter == EvalLimitItemParameter.POS_CENTER:
        rcx = (rx1 + rx2) / 2
        rcy = (ry1 + ry2) / 2
        dx = abs(tcx - rcx) / (rw / 2) * 100
        dy = abs(tcy - rcy) / (rh / 2) * 100
        return max(dx, dy)

    return 0.0


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
