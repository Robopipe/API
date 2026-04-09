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
    EvalLimitItemQuantifierType,
    EvalLimitItemQuantifierUnit,
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


@dataclass
class EvaluationResult:
    passed: bool
    fired: bool
    test_case_id: str
    test_case_name: str
    violated_limit_id: str | None
    violated_limit_name: str | None
    violated_limit_severity: str | None
    violated_limit_target_label_id: int | None
    violating_detections: list[BBoxDetection]


@dataclass
class LimitResult:
    is_satisfied: bool
    fired: bool
    limit: EvalLimit
    satisfying: list[BBoxDetection]
    non_satisfying: list[BBoxDetection]
    all_targets: list[BBoxDetection]


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
    ) -> tuple[bool, bool, list[BBoxDetection], list[BBoxDetection]]:
        """Evaluate this limit item.

        Returns (is_satisfied, fired, satisfying, non_satisfying).

        count_targets: targets used for COUNT (all visible, or within crossed parents).
        eval_targets: targets used for AREA/positional (crossed-based).
        satisfying/non_satisfying: per-detection breakdown (empty for COUNT).
        """
        if self.item.parameter == EvalLimitItemParameter.COUNT:
            return self._evaluate_count(count_targets)
        elif self.item.parameter == EvalLimitItemParameter.AREA:
            return self._evaluate_area(eval_targets, parent_detections)
        else:
            return self._evaluate_positional(eval_targets, parent_detections)

    def _check_quantifier(self, satisfied: int, total: int) -> bool:
        """Return True if the number of satisfied detections meets the quantifier."""
        v = self.item.quantifierValue
        if self.item.quantifierUnit == EvalLimitItemQuantifierUnit.PERCENT:
            threshold = round(total * v / 100)
        else:  # PCS
            threshold = v

        qt = self.item.quantifierType
        if qt == EvalLimitItemQuantifierType.MIN:
            return satisfied >= threshold
        elif qt == EvalLimitItemQuantifierType.MAX:
            return satisfied <= threshold
        else:  # EXACT
            return satisfied == threshold

    def _evaluate_count(
        self, targets: list[BBoxDetection]
    ) -> tuple[bool, bool, list[BBoxDetection], list[BBoxDetection]]:
        return (
            value_within_limits(
                float(len(targets)), self.item.limitFrom, self.item.limitTo
            ),
            True,
            [],
            [],
        )

    def _evaluate_area(
        self,
        targets: list[BBoxDetection],
        parent_detections: list[BBoxDetection] | None,
    ) -> tuple[bool, bool, list[BBoxDetection], list[BBoxDetection]]:
        """Area: each detection is evaluated individually against the limit;
        the quantifier specifies how many must satisfy it."""
        if not targets:
            return True, False, [], []

        satisfying: list[BBoxDetection] = []
        non_satisfying: list[BBoxDetection] = []
        for d in targets:
            if parent_detections is not None:
                containing = [
                    p for p in parent_detections if is_within_bbox(d.coords, p.coords)
                ]
                ref_area = (
                    sum(bbox_area(p.coords) for p in containing) if containing else 1.0
                )
            else:
                ref_area = 1.0  # normalized frame area
            pct = (bbox_area(d.coords) / ref_area * 100) if ref_area > 0 else 0.0
            if value_within_limits(pct, self.item.limitFrom, self.item.limitTo):
                satisfying.append(d)
            else:
                non_satisfying.append(d)

        return (
            self._check_quantifier(len(satisfying), len(targets)),
            True,
            satisfying,
            non_satisfying,
        )

    def _evaluate_positional(
        self,
        targets: list[BBoxDetection],
        parent_detections: list[BBoxDetection] | None,
    ) -> tuple[bool, bool, list[BBoxDetection], list[BBoxDetection]]:
        """Positional: quantifier specifies how many targets must be within the range."""
        if not targets:
            return True, False, [], []

        satisfying: list[BBoxDetection] = []
        non_satisfying: list[BBoxDetection] = []
        for t in targets:
            ref = self._get_reference_coords(t, parent_detections)
            pct = compute_position_pct(t.coords, ref, self.item.parameter)
            if value_within_limits(pct, self.item.limitFrom, self.item.limitTo):
                satisfying.append(t)
            else:
                non_satisfying.append(t)

        return (
            self._check_quantifier(len(satisfying), len(targets)),
            True,
            satisfying,
            non_satisfying,
        )

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
    ) -> LimitResult:
        """Evaluate the limit. Returns a LimitResult with per-detection breakdown."""
        if not self.item_evaluators:
            return LimitResult(
                is_satisfied=True, fired=False, limit=self.limit,
                satisfying=[], non_satisfying=[], all_targets=[],
            )

        count_targets = self._get_count_targets(all_detections, crossed)
        eval_targets = self._get_eval_targets(all_detections, crossed)
        parents = (
            self._get_parent_detections(crossed)
            if self.limit.targetParentLabel is not None
            else None
        )

        all_satisfying: list[BBoxDetection] = []
        all_non_satisfying: list[BBoxDetection] = []

        # Evaluate items and combine with left-to-right AND/OR
        value, fired, sat, nsat = self.item_evaluators[0].evaluate(
            count_targets, eval_targets, parents
        )
        all_satisfying.extend(sat)
        all_non_satisfying.extend(nsat)

        for i in range(1, len(self.item_evaluators)):
            # The operator on item[i-1] sits between item[i-1] and item[i]
            op = self.item_evaluators[i - 1].item.operator
            next_value, next_fired, sat, nsat = self.item_evaluators[i].evaluate(
                count_targets, eval_targets, parents
            )
            all_satisfying.extend(sat)
            all_non_satisfying.extend(nsat)
            fired = fired or next_fired

            if op == EvalLimitItemOperator.AND:
                value = value and next_value
            else:  # OR
                value = value or next_value

        # Deduplicate by object identity
        seen: set[int] = set()
        unique_sat = [d for d in all_satisfying if not (id(d) in seen or seen.add(id(d)))]
        seen.clear()
        unique_nsat = [d for d in all_non_satisfying if not (id(d) in seen or seen.add(id(d)))]

        return LimitResult(
            is_satisfied=value,
            fired=fired,
            limit=self.limit,
            satisfying=unique_sat,
            non_satisfying=unique_nsat,
            all_targets=count_targets if not eval_targets else eval_targets,
        )


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
    ) -> tuple[bool, bool, list[LimitResult]]:
        """Evaluate the logic tree. Returns (is_satisfied, fired, limit_results)."""
        if not self.test_case.logicNodes:
            # Default: AND all limits
            limit_results = [
                ev.evaluate(all_detections, crossed)
                for ev in self.limit_evaluators.values()
            ]
            if not limit_results:
                return True, False, []
            return (
                all(lr.is_satisfied for lr in limit_results),
                any(lr.fired for lr in limit_results),
                limit_results,
            )

        return self._evaluate_nodes(self.test_case.logicNodes, all_detections, crossed)

    def _evaluate_nodes(
        self,
        nodes: list[EvalLogicNode],
        all_detections: list[BBoxDetection],
        crossed: list[BBoxDetection],
    ) -> tuple[bool, bool, list[LimitResult]]:
        """Evaluate a list of logic nodes (infix notation, left-to-right)."""
        result: bool | None = None
        fired = False
        pending_op: EvalLogicOperatorValue | None = None
        negate_next = False
        collected: list[LimitResult] = []

        for node in nodes:
            if node.type == EvalLogicNodeType.OPERATOR:
                if node.operatorValue == EvalLogicOperatorValue.NOT:
                    negate_next = True
                else:
                    pending_op = node.operatorValue
                continue

            # Operand: LIMIT or GROUP
            if node.type == EvalLogicNodeType.LIMIT:
                if node.id not in self.limit_evaluators:
                    value, node_fired = False, False
                else:
                    lr = self.limit_evaluators[node.id].evaluate(
                        all_detections, crossed
                    )
                    collected.append(lr)
                    value, node_fired = lr.is_satisfied, lr.fired
            else:  # GROUP
                value, node_fired, child_results = self._evaluate_nodes(
                    node.children or [], all_detections, crossed
                )
                collected.extend(child_results)

            fired = fired or node_fired

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

        return (result, fired, collected) if result is not None else (True, fired, collected)


# ---------------------------------------------------------------------------
# Test case evaluator
# ---------------------------------------------------------------------------


class TestCaseEvaluator:
    """Evaluates a single test case, applying CHECK/DEFECT semantics."""

    def __init__(self, test_case: EvalTestCase, config: DashboardConfig) -> None:
        self.test_case = test_case
        self.logic_evaluator = LogicTreeEvaluator(test_case, config)

    def _is_limit_violated(self, limit_result: bool) -> bool:
        """Apply CHECK/DEFECT inversion to an individual limit result."""
        if self.test_case.type == EvalTestCaseType.CHECK:
            return not limit_result
        return limit_result

    def is_violated(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> tuple[bool, bool]:
        """Evaluate the test case and determine if it's violated.
        CHECK: violated when condition NOT met
        DEFECT: violated when condition IS met

        returns (is_violated, fired)
        """
        result, fired, _ = self.logic_evaluator.evaluate(all_detections, crossed)

        if self.test_case.type == EvalTestCaseType.CHECK:
            return (not result, fired)
        return result, fired

    def evaluate(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> list[EvaluationResult]:
        """Evaluate and return per-limit EvaluationResults if the test case is violated."""
        combined, _, limit_results = self.logic_evaluator.evaluate(
            all_detections, crossed
        )

        violated = (
            not combined
            if self.test_case.type == EvalTestCaseType.CHECK
            else combined
        )
        if not violated:
            return []

        results: list[EvaluationResult] = []
        for lr in limit_results:
            if not lr.fired or not self._is_limit_violated(lr.is_satisfied):
                continue

            # Determine violating detections based on CHECK/DEFECT semantics
            if self.test_case.type == EvalTestCaseType.CHECK:
                violating = lr.non_satisfying if lr.non_satisfying else lr.all_targets
            else:
                violating = lr.satisfying if lr.satisfying else lr.all_targets

            results.append(
                EvaluationResult(
                    passed=False,
                    fired=True,
                    test_case_id=self.test_case.id,
                    test_case_name=self.test_case.name,
                    violated_limit_id=lr.limit.id,
                    violated_limit_name=lr.limit.name,
                    violated_limit_severity=lr.limit.severity.value if lr.limit.severity else None,
                    violated_limit_target_label_id=lr.limit.targetLabel.id,
                    violating_detections=violating,
                )
            )

        # If no individual limit produced a result, still record the test case violation
        if not results:
            results.append(
                EvaluationResult(
                    passed=False,
                    fired=True,
                    test_case_id=self.test_case.id,
                    test_case_name=self.test_case.name,
                    violated_limit_id=None,
                    violated_limit_name=None,
                    violated_limit_severity=None,
                    violated_limit_target_label_id=None,
                    violating_detections=[],
                )
            )

        return results


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

    def reset(self, config_id: int) -> None:
        """Clear all state for a config (called on dashboard start)."""
        return

    def evaluate(
        self,
        config: DashboardConfig,
        detections: list[BBoxDetection],
        dashboard_run_session_id: int,
    ) -> list[EvaluationResult]:
        """Evaluate test cases and return evaluation results.

        Returns a list of EvaluationResult for each violated test case / limit pair.
        A single test case may produce multiple results (one per individually violated limit).
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

        # Record threshold tracking for just-crossed detections
        for evaluator in tc_evaluators:
            violated, fired = evaluator.is_violated(detections, just_crossed)
            if fired:
                self._threshold_tracker.record(
                    config.id, evaluator.test_case.id, passed=not violated
                )

        # Collect per-limit evaluation results from all violated test cases
        results: list[EvaluationResult] = []
        for evaluator in tc_evaluators:
            results.extend(evaluator.evaluate(detections, crossed))

        return results
