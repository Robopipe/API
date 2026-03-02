from ..models.dashboard.dashboard_config import DashboardConfig
from ..models.dashboard.dashboard_item import (
    DashboardItem,
    DashboardItemLimitUnit,
    DashboardItemPosition,
    DashboardItemType,
)
from ..models.detection.bbox_detection import BBoxDetection
from ..models.detection.detection import BaseNNDetections


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
        within = _value_within_limits(pct, item.limitFrom, item.limitTo)

        if item.type == DashboardItemType.CHECK and not within:
            return True
        elif item.type == DashboardItemType.DEFECT and within:
            return True

    return False


def _evaluate_item(
    item: DashboardItem,
    detections: list[BBoxDetection],
    dashboard_config: DashboardConfig,
) -> bool:
    """Evaluate a dashboard item. Returns True if violated."""
    if item.position in (DashboardItemPosition.COUNT, DashboardItemPosition.AREA):
        metric = _compute_metric(item, detections, dashboard_config)
        within = _value_within_limits(metric, item.limitFrom, item.limitTo)
        if item.type == DashboardItemType.CHECK:
            return not within
        elif item.type == DashboardItemType.DEFECT:
            return within
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

    dashboard_detections: list[dict] = []

    for item in dashboard_config.items:
        if _evaluate_item(item, detections.detections, dashboard_config):
            dashboard_detections.append(
                {
                    "item_id": item.id,
                    "type": item.severity.value.lower(),
                }
            )

    result["dashboard_detections"] = dashboard_detections or None
    return result
