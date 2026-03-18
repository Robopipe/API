from __future__ import annotations

from ..models.dashboard.dashboard_config import (
    DashboardConfig,
    DashboardLineDirection,
    DashboardLineFlow,
)
from ..models.dashboard.eval_models import (
    EvalLimit,
    EvalLimitItem,
    EvalLimitItemParameter,
    EvalLimitItemOperator,
    EvalLogicNode,
    EvalLogicNodeType,
    EvalLogicOperatorValue,
    EvalTestCase,
    EvalTestCaseType,
)
from ..models.detection.bbox_detection import BBoxDetection


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def bbox_area(coords: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = coords
    return max(0, x2 - x1) * max(0, y2 - y1)


def bbox_center(coords: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = coords
    return ((x1 + x2) / 2, (y1 + y2) / 2)


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


# ---------------------------------------------------------------------------
# Line crossing tracker
# ---------------------------------------------------------------------------


class LineCrossingTracker:
    """Tracks per-config detection line crossings across frames."""

    def __init__(self) -> None:
        # config_id -> [(label, cx, cy, is_past_line, has_crossed)]
        self._state: dict[int, list[tuple[int, float, float, bool, bool]]] = {}

    def _is_past_line(
        self,
        coords: tuple[float, float, float, float],
        config: DashboardConfig,
    ) -> bool:
        cx, cy = bbox_center(coords)
        positive = config.lineFlow == DashboardLineFlow.POSITIVE

        if config.lineDirection == DashboardLineDirection.HORIZONTAL:
            return cy >= config.linePosition if positive else cy <= config.linePosition
        return cx >= config.linePosition if positive else cx <= config.linePosition

    def find_crossed_detections(
        self,
        detections: list[BBoxDetection],
        config: DashboardConfig,
    ) -> tuple[list[BBoxDetection], bool]:
        """Return visible detections that have crossed the line and whether
        any NEW crossings happened this frame."""
        prev = self._state.get(config.id, [])

        current_info: list[tuple[int, float, float, bool]] = []
        for det in detections:
            cx, cy = bbox_center(det.coords)
            current_info.append(
                (det.label, cx, cy, self._is_past_line(det.coords, config))
            )

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
                has_crossed = past
                if has_crossed:
                    has_new = True

            new_state.append((label, cx, cy, past, has_crossed))
            if has_crossed:
                crossed.append(detections[i])

        self._state[config.id] = new_state
        return crossed, has_new

    def reset(self, config_id: int) -> None:
        """Clear crossing state for a config (e.g. on dashboard start)."""
        self._state.pop(config_id, None)


# ---------------------------------------------------------------------------
# Limit item evaluator
# ---------------------------------------------------------------------------

POSITIONAL_PARAMETERS = {
    EvalLimitItemParameter.POS_LEFT,
    EvalLimitItemParameter.POS_RIGHT,
    EvalLimitItemParameter.POS_TOP,
    EvalLimitItemParameter.POS_BOTTOM,
    EvalLimitItemParameter.POS_CENTER,
}


class LimitItemEvaluator:
    """Evaluates a single limit item against a set of target detections."""

    def __init__(self, item: EvalLimitItem) -> None:
        self.item = item

    def evaluate(
        self,
        targets: list[BBoxDetection],
        parent_detections: list[BBoxDetection] | None,
        all_detections: list[BBoxDetection],
    ) -> bool:
        """Evaluate this limit item. Returns True if the condition is met."""
        if self.item.parameter == EvalLimitItemParameter.COUNT:
            return self._evaluate_count(targets)
        elif self.item.parameter == EvalLimitItemParameter.AREA:
            return self._evaluate_area(targets, parent_detections)
        else:
            return self._evaluate_positional(targets, parent_detections)

    def _evaluate_count(self, targets: list[BBoxDetection]) -> bool:
        return value_within_limits(
            float(len(targets)), self.item.limitFrom, self.item.limitTo
        )

    def _evaluate_area(
        self,
        targets: list[BBoxDetection],
        parent_detections: list[BBoxDetection] | None,
    ) -> bool:
        """Area is always evaluated as percentage."""
        target_area = sum(bbox_area(d.coords) for d in targets)

        if parent_detections is not None:
            parent_area = sum(bbox_area(d.coords) for d in parent_detections)
            pct = (target_area / parent_area * 100) if parent_area > 0 else 0.0
        else:
            # Percentage of full frame (frame area = 1.0 in normalized coords)
            pct = target_area * 100

        return value_within_limits(pct, self.item.limitFrom, self.item.limitTo)

    def _evaluate_positional(
        self,
        targets: list[BBoxDetection],
        parent_detections: list[BBoxDetection] | None,
    ) -> bool:
        """Positional: ALL targets must be within the range (implicit ALL quantifier)."""
        if not targets:
            return False

        for t in targets:
            ref = self._get_reference_coords(t, parent_detections)
            pct = compute_position_pct(t.coords, ref, self.item.parameter)
            if not value_within_limits(pct, self.item.limitFrom, self.item.limitTo):
                return False

        return True

    @staticmethod
    def _get_reference_coords(
        target: BBoxDetection,
        parent_detections: list[BBoxDetection] | None,
    ) -> tuple[float, float, float, float]:
        """Get reference bbox for positional computation."""
        if parent_detections:
            containing = [
                p for p in parent_detections if is_within_bbox(target.coords, p.coords)
            ]
            if containing:
                return containing[0].coords
        return (0.0, 0.0, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Limit evaluator
# ---------------------------------------------------------------------------


class LimitEvaluator:
    """Evaluates a limit: resolves target detections and combines limit items."""

    def __init__(self, limit: EvalLimit, config: DashboardConfig) -> None:
        self.limit = limit
        self.config = config
        self.item_evaluators = [
            LimitItemEvaluator(item) for item in limit.limitItems
        ]

    def _get_target_detections(
        self, detections: list[BBoxDetection]
    ) -> list[BBoxDetection]:
        targets = [
            d
            for d in detections
            if self.config.labels[d.label].id == self.limit.targetLabel.id
        ]
        if self.limit.targetParentLabel is None:
            return targets

        parents = self._get_parent_detections(detections)
        return [
            t for t in targets if any(is_within_bbox(t.coords, p.coords) for p in parents)
        ]

    def _get_parent_detections(
        self, detections: list[BBoxDetection]
    ) -> list[BBoxDetection]:
        if self.limit.targetParentLabel is None:
            return []
        return [
            d
            for d in detections
            if self.config.labels[d.label].id == self.limit.targetParentLabel.id
        ]

    def evaluate(self, detections: list[BBoxDetection]) -> bool:
        """Evaluate the limit. Returns True if the combined condition is met."""
        if not self.item_evaluators:
            return True

        targets = self._get_target_detections(detections)
        parents = (
            self._get_parent_detections(detections)
            if self.limit.targetParentLabel is not None
            else None
        )

        # Evaluate items and combine with left-to-right AND/OR
        result = self.item_evaluators[0].evaluate(targets, parents, detections)

        for i in range(1, len(self.item_evaluators)):
            # The operator on item[i-1] sits between item[i-1] and item[i]
            op = self.item_evaluators[i - 1].item.operator
            item_result = self.item_evaluators[i].evaluate(targets, parents, detections)

            if op == EvalLimitItemOperator.AND:
                result = result and item_result
            else:  # OR
                result = result or item_result

        return result


# ---------------------------------------------------------------------------
# Logic tree evaluator
# ---------------------------------------------------------------------------


class LogicTreeEvaluator:
    """Evaluates the logic node tree that combines limit results."""

    def __init__(
        self, test_case: EvalTestCase, config: DashboardConfig
    ) -> None:
        self.test_case = test_case
        self.config = config
        self.limit_evaluators: dict[str, LimitEvaluator] = {
            limit.id: LimitEvaluator(limit, config)
            for limit in test_case.limits
        }

    def evaluate(self, detections: list[BBoxDetection]) -> bool:
        """Evaluate the logic tree. Returns True if the combined condition is met."""
        if not self.test_case.logicNodes:
            # Default: AND all limits
            return all(
                ev.evaluate(detections) for ev in self.limit_evaluators.values()
            )

        return self._evaluate_nodes(self.test_case.logicNodes, detections)

    def _evaluate_nodes(
        self,
        nodes: list[EvalLogicNode],
        detections: list[BBoxDetection],
    ) -> bool:
        """Evaluate a list of logic nodes (infix notation, left-to-right)."""
        result: bool | None = None
        pending_op: EvalLogicOperatorValue | None = None
        negate_next = False

        for node in nodes:
            if node.type == EvalLogicNodeType.OPERATOR:
                if node.operatorValue == EvalLogicOperatorValue.NOT:
                    negate_next = True
                else:
                    pending_op = node.operatorValue
                continue

            # Operand: LIMIT or GROUP
            if node.type == EvalLogicNodeType.LIMIT:
                evaluator = self.limit_evaluators.get(node.id)
                value = evaluator.evaluate(detections) if evaluator else False
            else:  # GROUP
                value = self._evaluate_nodes(node.children or [], detections)

            if negate_next:
                value = not value
                negate_next = False

            if result is None:
                result = value
            elif pending_op == EvalLogicOperatorValue.AND:
                result = result and value
            elif pending_op == EvalLogicOperatorValue.OR:
                result = result or value
            else:
                # No explicit operator between operands — default AND
                result = result and value

            pending_op = None

        return result if result is not None else True


# ---------------------------------------------------------------------------
# Test case evaluator
# ---------------------------------------------------------------------------


class TestCaseEvaluator:
    """Evaluates a single test case, applying CHECK/DEFECT semantics."""

    def __init__(
        self, test_case: EvalTestCase, config: DashboardConfig
    ) -> None:
        self.test_case = test_case
        self.logic_evaluator = LogicTreeEvaluator(test_case, config)

    def is_violated(self, detections: list[BBoxDetection]) -> bool:
        """Returns True if the test case is violated (should trigger alert/warning)."""
        result = self.logic_evaluator.evaluate(detections)

        if self.test_case.type == EvalTestCaseType.CHECK:
            return not result  # CHECK: violated when condition NOT met
        return result  # DEFECT: violated when condition IS met


# ---------------------------------------------------------------------------
# Dashboard evaluator (top-level)
# ---------------------------------------------------------------------------


class DashboardEvaluator:
    """Top-level evaluator: manages line crossing state and evaluates test cases."""

    def __init__(self, line_crossing_tracker: LineCrossingTracker) -> None:
        self._tracker = line_crossing_tracker

    def evaluate(
        self, config: DashboardConfig, detections: list[BBoxDetection]
    ) -> list[dict] | None:
        """Evaluate all test cases against detections that crossed the line.

        Returns a list of violation dicts, or None if no new crossings occurred.
        """
        crossed, has_new = self._tracker.find_crossed_detections(detections, config)

        if not has_new:
            return None

        test_case_evaluators = [
            TestCaseEvaluator(tc, config) for tc in config.testCases
        ]

        violations: list[dict] = []
        for evaluator in test_case_evaluators:
            if evaluator.is_violated(crossed):
                violations.append(
                    {
                        "test_case_id": evaluator.test_case.id,
                        "type": evaluator.test_case.severity.value.lower(),
                    }
                )

        return violations or None
