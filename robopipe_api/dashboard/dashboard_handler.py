from ..models.dashboard.dashboard_config import DashboardConfig, DashboardLineDirection
from ..models.dashboard.dashboard_item import (
    DashboardItem,
    DashboardItemLimitUnit,
    DashboardItemPosition,
    DashboardItemType,
)
from ..models.detection.bbox_detection import BBoxDetection
from ..models.detection.detection import BaseNNDetections

# Per-config state tracking for line crossing:
# config_id -> [(label, cx, cy, is_past_line, has_crossed)]
_line_crossing_state: dict[int, list[tuple[int, float, float, bool, bool]]] = {}


def _bbox_area(coords: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box from normalized coordinates."""
    x1, y1, x2, y2 = coords
    return max(0, x2 - x1) * max(0, y2 - y1)


def _bbox_center(coords: tuple[float, float, float, float]) -> tuple[float, float]:
    """Get the center point of a bounding box."""
    x1, y1, x2, y2 = coords
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _is_within_bbox(
    inner_coords: tuple[float, float, float, float],
    outer_coords: tuple[float, float, float, float],
) -> bool:
    """Check if the center of inner bbox falls within the outer bbox."""
    cx, cy = _bbox_center(inner_coords)
    return (
        outer_coords[0] <= cx <= outer_coords[2]
        and outer_coords[1] <= cy <= outer_coords[3]
    )


def _compute_position_pct(
    target_coords: tuple[float, float, float, float],
    reference_coords: tuple[float, float, float, float],
    position: DashboardItemPosition,
) -> float:
    """Compute the position of a detection center as a percentage along
    the specified axis within the reference bbox.

    POS_LEFT:   % from the left edge   (0 = left edge, 100 = right edge)
    POS_RIGHT:  % from the right edge  (0 = right edge, 100 = left edge)
    POS_TOP:    % from the top edge     (0 = top edge, 100 = bottom edge)
    POS_BOTTOM: % from the bottom edge  (0 = bottom edge, 100 = top edge)
    POS_CENTER: max of x/y distance from center as % of half-dimension
    """
    tcx, tcy = _bbox_center(target_coords)
    rx1, ry1, rx2, ry2 = reference_coords
    rw = rx2 - rx1
    rh = ry2 - ry1

    if rw == 0 or rh == 0:
        return 0.0

    if position == DashboardItemPosition.POS_LEFT:
        return ((tcx - rx1) / rw) * 100
    elif position == DashboardItemPosition.POS_RIGHT:
        return ((rx2 - tcx) / rw) * 100
    elif position == DashboardItemPosition.POS_TOP:
        return ((tcy - ry1) / rh) * 100
    elif position == DashboardItemPosition.POS_BOTTOM:
        return ((ry2 - tcy) / rh) * 100
    elif position == DashboardItemPosition.POS_CENTER:
        rcx = (rx1 + rx2) / 2
        rcy = (ry1 + ry2) / 2
        dx = abs(tcx - rcx) / (rw / 2) * 100
        dy = abs(tcy - rcy) / (rh / 2) * 100
        return max(dx, dy)

    return 0.0


def _get_target_detections(
    item: DashboardItem,
    detections: list[BBoxDetection],
    dashboard_config: DashboardConfig,
) -> list[BBoxDetection]:
    """Filter detections matching the target label, optionally constrained to parent bboxes."""
    targets = [
        d
        for d in detections
        if dashboard_config.labels[d.label].id == item.targetLabel.id
    ]

    if item.targetParentLabel is None:
        return targets

    parents = [
        d
        for d in detections
        if dashboard_config.labels[d.label].id == item.targetParentLabel.id
    ]
    return [
        t for t in targets if any(_is_within_bbox(t.coords, p.coords) for p in parents)
    ]


def _value_within_limits(
    value: float,
    limit_from: float | None,
    limit_to: float | None,
) -> bool:
    """Check if a value falls within the [limitFrom, limitTo] range."""
    if limit_from is not None and value < limit_from:
        return False
    if limit_to is not None and value > limit_to:
        return False
    return True


def _compute_metric(
    item: DashboardItem,
    detections: list[BBoxDetection],
    dashboard_config: DashboardConfig,
) -> float:
    """Compute the numeric metric for a COUNT or AREA dashboard item."""
    targets = _get_target_detections(item, detections, dashboard_config)

    if item.position == DashboardItemPosition.COUNT:
        count = len(targets)
        if item.unit == DashboardItemLimitUnit.PERCENTAGE:
            if item.targetParentLabel is not None:
                parents = [
                    d
                    for d in detections
                    if dashboard_config.labels[d.label].id == item.targetParentLabel.id
                ]
                total = len(parents) if parents else 1
            else:
                total = len(detections) if detections else 1
            return (count / total) * 100
        return float(count)

    elif item.position == DashboardItemPosition.AREA:
        target_area = sum(_bbox_area(d.coords) for d in targets)
        if item.unit == DashboardItemLimitUnit.PERCENTAGE:
            if item.targetParentLabel is not None:
                parents = [
                    d
                    for d in detections
                    if dashboard_config.labels[d.label].id == item.targetParentLabel.id
                ]
                parent_area = sum(_bbox_area(d.coords) for d in parents)
                return (target_area / parent_area * 100) if parent_area > 0 else 0.0
            return target_area * 100
        return target_area

    return 0.0


def _evaluate_positional_item(
    item: DashboardItem,
    detections: list[BBoxDetection],
    dashboard_config: DashboardConfig,
) -> bool:
    """Evaluate a positional dashboard item. Returns True if violated.

    For each target detection, computes its position percentage along the
    axis defined by item.position within the reference area (parent bbox
    or full frame), then checks against [limitFrom, limitTo].

    CHECK:  violation if any detection is OUTSIDE the positional range.
    DEFECT: violation if any detection is INSIDE the positional range.
    """
    targets = _get_target_detections(item, detections, dashboard_config)

    if not targets:
        # No targets: CHECK fails (expected condition not met), DEFECT passes
        return item.type == DashboardItemType.CHECK

    if item.targetParentLabel is not None:
        parents = [
            d
            for d in detections
            if dashboard_config.labels[d.label].id == item.targetParentLabel.id
        ]
    else:
        parents = None

    for t in targets:
        if parents:
            containing = [p for p in parents if _is_within_bbox(t.coords, p.coords)]
            if not containing:
                continue
            ref = containing[0].coords
        else:
            ref = (0.0, 0.0, 1.0, 1.0)

        pct = _compute_position_pct(t.coords, ref, item.position)
        within = map(
            lambda lim: _value_within_limits(pct, lim.from_value, lim.to_value),
            item.limits,
        )

        if item.type == DashboardItemType.CHECK and not any(within):
            return True
        elif item.type == DashboardItemType.DEFECT and any(within):
            return True

    return False


def _is_past_line(
    coords: tuple[float, float, float, float],
    config: DashboardConfig,
) -> bool:
    """Check if a detection center is past the line.

    HORIZONTAL line: past means center Y >= line_position (top-to-bottom).
    VERTICAL   line: past means center X >= line_position (left-to-right).
    """
    cx, cy = _bbox_center(coords)
    if config.lineDirection == DashboardLineDirection.HORIZONTAL:
        return cy >= config.linePosition
    return cx >= config.linePosition


def _find_crossed_detections(
    detections: list[BBoxDetection],
    config: DashboardConfig,
) -> tuple[list[BBoxDetection], bool]:
    """Return all currently-visible detections that have crossed the line,
    plus a flag indicating whether any NEW crossings happened this frame.

    Matching between frames is done per-label using nearest-neighbour distance.
    A detection is marked as "has_crossed" when its center transitions from
    before the line to past it (or appears for the first time already past it).
    Once marked, it stays crossed as long as it remains visible, so aggregate
    metrics like COUNT accumulate correctly across frames.

    Returns:
        (crossed, has_new): crossed is the full accumulated list of visible
        detections that have ever crossed; has_new is True only when at least
        one detection crossed for the first time in this frame.
    """
    prev = _line_crossing_state.get(config.id, [])

    current_info: list[tuple[int, float, float, bool]] = []
    for det in detections:
        cx, cy = _bbox_center(det.coords)
        current_info.append((det.label, cx, cy, _is_past_line(det.coords, config)))

    crossed: list[BBoxDetection] = []
    new_state: list[tuple[int, float, float, bool, bool]] = []
    used_prev: set[int] = set()
    has_new = False

    for i, (label, cx, cy, past) in enumerate(current_info):
        best_match: int | None = None
        best_dist = float("inf")
        for j, (plabel, pcx, pcy, _ppast, _pcrossed) in enumerate(prev):
            if j in used_prev or plabel != label:
                continue
            dist = (cx - pcx) ** 2 + (cy - pcy) ** 2
            if dist < best_dist:
                best_dist = dist
                best_match = j

        if best_match is not None:
            used_prev.add(best_match)
            prev_past, prev_crossed = prev[best_match][3], prev[best_match][4]
            just_crossed = not prev_past and past
            has_crossed = prev_crossed or just_crossed
            if just_crossed:
                has_new = True
        else:
            # New detection: crossed if it appeared already past the line
            has_crossed = past
            if has_crossed:
                has_new = True

        new_state.append((label, cx, cy, past, has_crossed))
        if has_crossed:
            crossed.append(detections[i])

    _line_crossing_state[config.id] = new_state
    return crossed, has_new


def _evaluate_item(
    item: DashboardItem,
    detections: list[BBoxDetection],
    dashboard_config: DashboardConfig,
) -> bool:
    """Evaluate a dashboard item. Returns True if violated."""
    if item.position in (DashboardItemPosition.COUNT, DashboardItemPosition.AREA):
        metric = _compute_metric(item, detections, dashboard_config)
        within = map(
            lambda lim: _value_within_limits(metric, lim.from_value, lim.to_value),
            item.limits,
        )
        if item.type == DashboardItemType.CHECK:
            return not any(within)
        elif item.type == DashboardItemType.DEFECT:
            return any(within)
        return False
    else:
        return _evaluate_positional_item(item, detections, dashboard_config)


def handle_detections(
    dashboard_config: DashboardConfig | None, detections: BaseNNDetections
) -> dict:
    """Evaluate dashboard rules against detections and return enriched result.

    For each dashboard item, evaluates whether the item is violated:
    - COUNT/AREA: computes a single aggregate metric and checks limits.
    - Positional: checks each detection's position % along the axis against limits.

    CHECK items trigger when the condition is NOT fulfilled.
    DEFECT items trigger when the condition IS fulfilled.
    """
    result = detections.model_dump()

    if dashboard_config is None:
        return result

    crossed, has_new = _find_crossed_detections(detections.detections, dashboard_config)

    if not has_new:
        result["dashboard_detections"] = None
        return result

    dashboard_detections: list[dict] = []

    for item in dashboard_config.items:
        if _evaluate_item(item, crossed, dashboard_config):
            dashboard_detections.append(
                {
                    "item_id": item.id,
                    "type": item.severity.value.lower(),
                }
            )

    result["dashboard_detections"] = dashboard_detections or None
    return result
