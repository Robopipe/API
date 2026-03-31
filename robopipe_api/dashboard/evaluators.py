from __future__ import annotations

from dataclasses import dataclass

from .events_store import events_store_factory

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
from .threshold_tracker import ThresholdTracker


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def bbox_area(coords: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = coords
    return max(0, x2 - x1) * max(0, y2 - y1)


def bbox_center(coords: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = coords
    return ((x1 + x2) / 2, (y1 + y2) / 2)


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


# ---------------------------------------------------------------------------
# Line crossing tracker
# ---------------------------------------------------------------------------


@dataclass
class TrackedDetection:
    label: int
    cx: float
    cy: float
    is_past_line: bool
    has_crossed: bool
    missing_frames: int = 0


class LineCrossingTracker:
    """Tracks per-config detection line crossings across frames."""

    def __init__(self, max_missing_frames: int = 5) -> None:
        self._state: dict[int, list[TrackedDetection]] = {}
        self._max_missing_frames = max_missing_frames

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
    ) -> tuple[list[BBoxDetection], set[int]]:
        """Return (crossed, just_crossed_label_indices).

        crossed: currently-visible detections that have ever crossed the line.
        just_crossed_label_indices: set of detection label indices (d.label)
            that had at least one new crossing this frame.
        """
        prev_state = self._state.get(config.id, [])

        prev_not_past = [d for d in prev_state if not d.is_past_line]
        curr_not_past: list[TrackedDetection] = []
        curr_past: list[TrackedDetection] = []
        ret_past: list[BBoxDetection] = []
        curr_used: set[int] = set()
        not_past_used: set[int] = set()
        matched_prev: set[int] = set()

        for det in detections:
            cx, cy = bbox_center(det.coords)
            past = self._is_past_line(det.coords, config)

            if past:
                curr_past.append(TrackedDetection(det.label, cx, cy, True, False))
                ret_past.append(det)
            else:
                curr_not_past.append(TrackedDetection(det.label, cx, cy, False, False))

        for pi, prev in enumerate(prev_not_past):
            best_dist = float("inf")
            best_index = None
            best_in_past = False

            for i, curr in enumerate(curr_past):
                if curr.label != prev.label or i in curr_used:
                    continue
                dist = euclidean_distance((prev.cx, prev.cy), (curr.cx, curr.cy))
                if dist < best_dist:
                    best_dist = dist
                    best_index = i
                    best_in_past = True

            for i, curr in enumerate(curr_not_past):
                if curr.label != prev.label or i in not_past_used:
                    continue
                dist = euclidean_distance((prev.cx, prev.cy), (curr.cx, curr.cy))
                if dist < best_dist:
                    best_dist = dist
                    best_index = i
                    best_in_past = False

            if best_index is not None:
                matched_prev.add(pi)
                if best_in_past:
                    curr_used.add(best_index)
                    curr_past[best_index].has_crossed = True
                else:
                    not_past_used.add(best_index)

        # Keep unmatched prev not-past detections alive until grace period expires
        for pi, prev in enumerate(prev_not_past):
            if pi in matched_prev:
                continue
            prev.missing_frames += 1
            if prev.missing_frames <= self._max_missing_frames:
                curr_not_past.append(prev)

        self._state[config.id] = curr_not_past + curr_past
        return ret_past, curr_used

        # crossed: list[BBoxDetection] = []
        # used_prev: set[int] = set()
        # just_crossed_label_indices: set[int] = set()

        # for i, det in enumerate(detections):
        #     cx, cy = bbox_center(det.coords)
        #     past = self._is_past_line(det.coords, config)

        #     best_match: int | None = None
        #     best_dist = float("inf")
        #     for j, prev_det in enumerate(prev_state):
        #         if j in used_prev or prev_det.label != det.label:
        #             continue
        #         dist = (cx - prev_det.cx) ** 2 + (cy - prev_det.cy) ** 2
        #         if dist < best_dist:
        #             best_dist = dist
        #             best_match = j

        #     if best_match is not None:
        #         used_prev.add(best_match)
        #         match = prev_state[best_match]
        #         just_crossed = not match.is_past_line and past
        #         has_crossed = match.has_crossed or just_crossed
        #         if just_crossed:
        #             just_crossed_label_indices.add(det.label)
        #     else:
        #         has_crossed = past
        #         if has_crossed:
        #             just_crossed_label_indices.add(det.label)

        #     new_state.append(TrackedDetection(det.label, cx, cy, past, has_crossed))
        #     if has_crossed:
        #         crossed.append(detections[i])

        # self._state[config.id] = new_state
        # return crossed, just_crossed_label_indices

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
        count_targets: list[BBoxDetection],
        eval_targets: list[BBoxDetection],
        parent_detections: list[BBoxDetection] | None,
    ) -> tuple[bool, bool]:
        """Evaluate this limit item. Returns (is_violated, fired) if the condition is met.

        count_targets: targets used for COUNT (all visible, or within crossed parents).
        eval_targets: targets used for AREA/positional (crossed-based).
        """
        if self.item.parameter == EvalLimitItemParameter.COUNT:
            return self._evaluate_count(count_targets)
        elif self.item.parameter == EvalLimitItemParameter.AREA:
            return self._evaluate_area(eval_targets, parent_detections)
        else:
            return self._evaluate_positional(eval_targets, parent_detections)

    def _evaluate_count(self, targets: list[BBoxDetection]) -> tuple[bool, bool]:
        return (
            value_within_limits(
                float(len(targets)), self.item.limitFrom, self.item.limitTo
            ),
            True,
        )

    def _evaluate_area(
        self,
        targets: list[BBoxDetection],
        parent_detections: list[BBoxDetection] | None,
    ) -> tuple[bool, bool]:
        """Area is always evaluated as percentage."""
        target_area = sum(bbox_area(d.coords) for d in targets)

        if parent_detections is not None:
            parent_area = sum(bbox_area(d.coords) for d in parent_detections)
            pct = (target_area / parent_area * 100) if parent_area > 0 else 0.0
        else:
            # Percentage of full frame (frame area = 1.0 in normalized coords)
            pct = target_area * 100

        return value_within_limits(pct, self.item.limitFrom, self.item.limitTo), True

    def _evaluate_positional(
        self,
        targets: list[BBoxDetection],
        parent_detections: list[BBoxDetection] | None,
    ) -> tuple[bool, bool]:
        """Positional: ALL targets must be within the range (implicit ALL quantifier)."""

        for t in targets:
            ref = self._get_reference_coords(t, parent_detections)
            pct = compute_position_pct(t.coords, ref, self.item.parameter)
            if not value_within_limits(pct, self.item.limitFrom, self.item.limitTo):
                return False, True

        return True, bool(targets)

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
        self.item_evaluators = [LimitItemEvaluator(item) for item in limit.limitItems]

    def _get_parent_detections(
        self, crossed: list[BBoxDetection]
    ) -> list[BBoxDetection]:
        """Crossed parents — the trigger unit for parent-child limits."""
        if self.limit.targetParentLabel is None:
            return []
        return [
            d
            for d in crossed
            if self.config.labels[d.label].id == self.limit.targetParentLabel.id
        ]

    def _get_count_targets(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> list[BBoxDetection]:
        """Targets for COUNT: all currently visible (no parent) or all within crossed parents."""
        if self.limit.targetParentLabel is None:
            return [
                d
                for d in all_detections
                if self.config.labels[d.label].id == self.limit.targetLabel.id
            ]
        parents = self._get_parent_detections(crossed)
        all_targets = [
            d
            for d in all_detections
            if self.config.labels[d.label].id == self.limit.targetLabel.id
        ]
        return [
            t
            for t in all_targets
            if any(is_within_bbox(t.coords, p.coords) for p in parents)
        ]

    def _get_eval_targets(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> list[BBoxDetection]:
        """Targets for area/positional: crossed targets (no parent) or all within crossed parents."""
        if self.limit.targetParentLabel is None:
            return [
                d
                for d in crossed
                if self.config.labels[d.label].id == self.limit.targetLabel.id
            ]
        parents = self._get_parent_detections(crossed)
        all_targets = [
            d
            for d in all_detections
            if self.config.labels[d.label].id == self.limit.targetLabel.id
        ]
        return [
            t
            for t in all_targets
            if any(is_within_bbox(t.coords, p.coords) for p in parents)
        ]

    def evaluate(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> tuple[bool, bool]:
        """Evaluate the limit. Returns (is_violated, fired) if the combined condition is met."""
        if not self.item_evaluators:
            return True, False

        count_targets = self._get_count_targets(all_detections, crossed)
        eval_targets = self._get_eval_targets(all_detections, crossed)
        parents = (
            self._get_parent_detections(crossed)
            if self.limit.targetParentLabel is not None
            else None
        )

        # Evaluate items and combine with left-to-right AND/OR
        result = self.item_evaluators[0].evaluate(count_targets, eval_targets, parents)

        for i in range(1, len(self.item_evaluators)):
            # The operator on item[i-1] sits between item[i-1] and item[i]
            op = self.item_evaluators[i - 1].item.operator
            item_result = self.item_evaluators[i].evaluate(
                count_targets, eval_targets, parents
            )

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

    def __init__(self, test_case: EvalTestCase, config: DashboardConfig) -> None:
        self.test_case = test_case
        self.config = config
        self.limit_evaluators: dict[str, LimitEvaluator] = {
            limit.id: LimitEvaluator(limit, config) for limit in test_case.limits
        }

    def evaluate(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> tuple[bool, bool]:
        """Evaluate the logic tree. Returns (is_violated, fired) if the combined condition is met."""
        # if not self.test_case.logicNodes:
        #     # Default: AND all limits
        #     results = [
        #         ev.evaluate(all_detections, crossed)
        #         for ev in self.limit_evaluators.values()
        #     ]
        #     return all(result for result, _ in results), any(
        #         fired for _, fired in results
        #     )

        return self._evaluate_nodes(self.test_case.logicNodes, all_detections, crossed)

    def _evaluate_nodes(
        self,
        nodes: list[EvalLogicNode],
        all_detections: list[BBoxDetection],
        crossed: list[BBoxDetection],
    ) -> tuple[bool, bool]:
        """Evaluate a list of logic nodes (infix notation, left-to-right)."""
        result: bool | None = None
        fired = False
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
                evaluator = self.limit_evaluators[node.id]
                value, fired = evaluator.evaluate(all_detections, crossed)
            else:  # GROUP
                value, fired = self._evaluate_nodes(
                    node.children or [], all_detections, crossed
                )

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

        return (result, fired) if result is not None else (True, fired)


# ---------------------------------------------------------------------------
# Test case evaluator
# ---------------------------------------------------------------------------


class TestCaseEvaluator:
    """Evaluates a single test case, applying CHECK/DEFECT semantics."""

    def __init__(self, test_case: EvalTestCase, config: DashboardConfig) -> None:
        self.test_case = test_case
        self.logic_evaluator = LogicTreeEvaluator(test_case, config)

    def is_violated(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> tuple[bool, bool]:
        """Evaluate the test case and determine if it's violated.
        CHECK: violated when condition NOT met (e.g. "no red in zone" violated if red detected in zone)
        DEFECT: violated when condition IS met (e.g. "red in zone" violated if red detected in zone)

        returns (is_violated, fired) where:
        - is_violated: whether the test case condition is currently violated
        - fired: whether the test case was triggered by this crossing event (used for tracking purposes)
        """
        result, fired = self.logic_evaluator.evaluate(all_detections, crossed)

        if self.test_case.type == EvalTestCaseType.CHECK:
            return (not result, fired)  # CHECK: violated when condition NOT met
        return result, fired  # DEFECT: violated when condition IS met


# ---------------------------------------------------------------------------
# Dashboard evaluator (top-level)
# ---------------------------------------------------------------------------


class DashboardEvaluator:
    """Top-level evaluator: manages line crossing state and evaluates test cases."""

    def __init__(
        self,
        line_crossing_tracker: LineCrossingTracker,
        threshold_tracker: ThresholdTracker,
    ) -> None:
        self._tracker = line_crossing_tracker
        self._threshold_tracker = threshold_tracker
        # config_id → active display violation (persists until crossed detections leave)
        # self._active_display_violations: dict[int, dict] = {}

    def reset(self, config_id: int) -> None:
        """Clear all state for a config (called on dashboard start)."""
        # self._active_display_violations.pop(config_id, None)
        return

    def evaluate(
        self,
        config: DashboardConfig,
        detections: list[BBoxDetection],
        dashboard_run_session_id: int,
    ) -> list[dict]:
        """Evaluate test cases and return violations.

        violations: list of {"test_case_id": int, "type": "alert" | "warning"} for test cases violated
        by this frame's detections that are past the trigger boundary.

        Trigger rules per test case:
        - With targetParentLabel: fires when the parent label crosses.
        - Without targetParentLabel: fires when the target label crosses.
        """
        events_store = events_store_factory()
        crossed, just_crossed_indices = self._tracker.find_crossed_detections(
            detections, config
        )
        for i in just_crossed_indices:
            events_store.inc_counter(
                dashboard_run_session_id, config.labels[crossed[i].label].id
            )
        just_crossed = [d for i, d in enumerate(crossed) if i in just_crossed_indices]
        tc_evaluators = [TestCaseEvaluator(tc, config) for tc in config.testCases]
        for evaluator in tc_evaluators:
            violated, fired = evaluator.is_violated(detections, just_crossed)
            if fired:
                self._threshold_tracker.record(
                    config.id, evaluator.test_case.id, passed=not violated
                )

        violations = []
        for evaluator in tc_evaluators:
            violated, _ = evaluator.is_violated(detections, crossed)
            if violated:
                violations.append(
                    {
                        "test_case_id": evaluator.test_case.id,
                        "type": evaluator.test_case.severity.value,
                    }
                )

        return violations
