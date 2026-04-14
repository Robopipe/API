from __future__ import annotations

from dataclasses import dataclass

from .events_store import events_store_factory
from .geometry import (
    bbox_area,
    compute_position_pct,
    is_within_bbox,
    value_within_limits,
)
from .line_crossing import LineCrossingTracker
from .threshold_tracker import ThresholdTracker

from ..models.dashboard.dashboard_config import DashboardConfig
from ..models.dashboard.eval_models import (
    EvalLimit,
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


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LimitResult:
    """Intermediate result from evaluating a single limit."""

    is_satisfied: bool
    fired: bool
    limit: EvalLimit
    satisfying: list[BBoxDetection]
    non_satisfying: list[BBoxDetection]
    all_targets: list[BBoxDetection]


@dataclass
class EvaluationResult:
    """Final result for a single violated limit within a test case."""

    test_case_id: str
    test_case_name: str
    violated_limit_id: str | None
    violated_limit_name: str | None
    violated_limit_severity: str | None
    violated_limit_target_label_id: int | None
    violating_detections: list[BBoxDetection]
    db_event_id: int | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dedupe(detections: list[BBoxDetection]) -> list[BBoxDetection]:
    """Deduplicate detections by object identity."""
    seen: set[int] = set()
    result: list[BBoxDetection] = []
    for d in detections:
        if id(d) not in seen:
            seen.add(id(d))
            result.append(d)
    return result


# ---------------------------------------------------------------------------
# Limit item evaluator
# ---------------------------------------------------------------------------


class LimitItemEvaluator:
    """Evaluates a single limit item against a set of target detections."""

    def __init__(self, item) -> None:
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

    def _filter_by_label(self, detections: list[BBoxDetection]) -> list[BBoxDetection]:
        """Filter detections to those matching the limit's target label."""
        return [
            d
            for d in detections
            if self.config.labels[d.label].id == self.limit.targetLabel.id
        ]

    def _evaluate_items(
        self,
        count_targets: list[BBoxDetection],
        eval_targets: list[BBoxDetection],
        parents: list[BBoxDetection] | None,
    ) -> tuple[bool, bool, list[BBoxDetection], list[BBoxDetection]]:
        """Evaluate all limit items and combine with left-to-right AND/OR.

        Returns (value, fired, satisfying, non_satisfying).
        """
        satisfying: list[BBoxDetection] = []
        non_satisfying: list[BBoxDetection] = []

        value, fired, sat, nsat = self.item_evaluators[0].evaluate(
            count_targets, eval_targets, parents
        )
        satisfying.extend(sat)
        non_satisfying.extend(nsat)

        for i in range(1, len(self.item_evaluators)):
            op = self.item_evaluators[i - 1].item.operator
            next_value, next_fired, sat, nsat = self.item_evaluators[i].evaluate(
                count_targets, eval_targets, parents
            )
            satisfying.extend(sat)
            non_satisfying.extend(nsat)
            fired = fired or next_fired

            if op == EvalLimitItemOperator.AND:
                value = value and next_value
            else:  # OR
                value = value or next_value

        return value, fired, satisfying, non_satisfying

    def evaluate(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> LimitResult:
        """Evaluate the limit. Returns a LimitResult with per-detection breakdown."""
        if not self.item_evaluators:
            return LimitResult(
                is_satisfied=True,
                fired=False,
                limit=self.limit,
                satisfying=[],
                non_satisfying=[],
                all_targets=[],
            )

        # No parent label: evaluate globally
        if self.limit.targetParentLabel is None:
            count_targets = self._filter_by_label(all_detections)
            eval_targets = self._filter_by_label(crossed)

            value, fired, sat, nsat = self._evaluate_items(
                count_targets, eval_targets, None
            )
            all_targets = count_targets if not eval_targets else eval_targets

            return LimitResult(
                is_satisfied=value,
                fired=fired,
                limit=self.limit,
                satisfying=_dedupe(sat),
                non_satisfying=_dedupe(nsat),
                all_targets=all_targets,
            )

        # Parent label set: evaluate each parent independently
        all_labeled = self._filter_by_label(all_detections)
        parents = [
            d
            for d in crossed
            if self.config.labels[d.label].id == self.limit.targetParentLabel.id
        ]
        # No parents crossed → this limit is not applicable this frame
        if not parents:
            return LimitResult(
                is_satisfied=True,
                fired=False,
                limit=self.limit,
                satisfying=[],
                non_satisfying=[],
                all_targets=[],
            )

        overall_satisfied = True
        overall_fired = False
        all_satisfying: list[BBoxDetection] = []
        all_non_satisfying: list[BBoxDetection] = []
        violating_parents: list[BBoxDetection] = []
        violating_children: list[BBoxDetection] = []

        for p in parents:
            children = [t for t in all_labeled if is_within_bbox(t.coords, p.coords)]

            value, fired, sat, nsat = self._evaluate_items(children, children, [p])
            overall_fired = overall_fired or fired
            all_satisfying.extend(sat)
            all_non_satisfying.extend(nsat)

            if not value:
                overall_satisfied = False
                violating_parents.append(p)
                violating_children.extend(children)

        return LimitResult(
            is_satisfied=overall_satisfied,
            fired=overall_fired,
            limit=self.limit,
            satisfying=_dedupe(all_satisfying),
            non_satisfying=_dedupe(all_non_satisfying),
            all_targets=violating_children + violating_parents,
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
                result = result and value

            pending_op = None

        return (
            (result, fired, collected)
            if result is not None
            else (True, fired, collected)
        )


# ---------------------------------------------------------------------------
# Test case evaluator
# ---------------------------------------------------------------------------


class TestCaseEvaluator:
    """Evaluates a single test case, applying CHECK/DEFECT semantics."""

    def __init__(self, test_case: EvalTestCase, config: DashboardConfig) -> None:
        self.test_case = test_case
        self._is_check = test_case.type == EvalTestCaseType.CHECK
        self._logic_evaluator = LogicTreeEvaluator(test_case, config)

    def _is_violated(self, is_satisfied: bool) -> bool:
        """Apply CHECK/DEFECT inversion: CHECK is violated when NOT satisfied."""
        return not is_satisfied if self._is_check else is_satisfied

    def is_violated(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> tuple[bool, bool]:
        """Quick check returning (is_violated, fired). Used for threshold tracking."""
        result, fired, _ = self._logic_evaluator.evaluate(all_detections, crossed)
        return self._is_violated(result), fired

    def evaluate(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> list[EvaluationResult]:
        """Evaluate and return per-limit EvaluationResults if the test case is violated."""
        combined, _, limit_results = self._logic_evaluator.evaluate(
            all_detections, crossed
        )

        if not self._is_violated(combined):
            return []

        tc = self.test_case
        results: list[EvaluationResult] = []
        for lr in limit_results:
            if not lr.fired or not self._is_violated(lr.is_satisfied):
                continue

            # CHECK: non-satisfying detections failed the check
            # DEFECT: satisfying detections are the defects
            # Fall back to all_targets for COUNT (no per-detection split)
            if self._is_check:
                violating = lr.non_satisfying or lr.all_targets
            else:
                violating = lr.satisfying or lr.all_targets

            results.append(
                EvaluationResult(
                    test_case_id=tc.id,
                    test_case_name=tc.name,
                    violated_limit_id=lr.limit.id,
                    violated_limit_name=lr.limit.name,
                    violated_limit_severity=(
                        lr.limit.severity.value if lr.limit.severity else None
                    ),
                    violated_limit_target_label_id=lr.limit.targetLabel.id,
                    violating_detections=violating,
                )
            )

        # If no individual limit produced a result, still record the test case violation
        if not results:
            results.append(
                EvaluationResult(
                    test_case_id=tc.id,
                    test_case_name=tc.name,
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

    def evaluate(
        self,
        config: DashboardConfig,
        detections: list[BBoxDetection],
        dashboard_run_session_id: int,
    ) -> tuple[list[EvaluationResult], list[int], list[int]]:
        """Evaluate test cases and return evaluation results.

        Returns a tuple of:
        - list of EvaluationResult for each violated test case / limit pair
        - list of violation event IDs (for picture capture by the frontend)
        """
        events_store = events_store_factory()
        crossed, just_crossed_indices, tracking_ids = (
            self._tracker.find_crossed_detections(detections, config)
        )
        for i in just_crossed_indices:
            label = config.labels[crossed[i].label]
            events_store.inc_counter(dashboard_run_session_id, label.id, label.name)
        just_crossed = [d for i, d in enumerate(crossed) if i in just_crossed_indices]
        tc_evaluators = [TestCaseEvaluator(tc, config) for tc in config.testCases]

        # Record threshold tracking and save events for just-crossed detections
        violation_event_ids: list[int] = []
        for evaluator in tc_evaluators:
            violated, fired = evaluator.is_violated(detections, just_crossed)
            if fired:
                self._threshold_tracker.record(
                    config.id, evaluator.test_case.id, passed=not violated
                )
                tc = evaluator.test_case
                if violated:
                    eval_results = evaluator.evaluate(detections, just_crossed)
                    for r in eval_results:
                        event_id = events_store.save_event(
                            dashboard_run_session_id,
                            tc.id,
                            tc.name,
                            r.violated_limit_id,
                            r.violated_limit_name,
                        )
                        violation_event_ids.append(event_id)
                    if not eval_results:
                        event_id = events_store.save_event(
                            dashboard_run_session_id,
                            tc.id,
                            tc.name,
                            None,
                            None,
                        )
                        violation_event_ids.append(event_id)
                else:
                    events_store.save_event(
                        dashboard_run_session_id,
                        tc.id,
                        tc.name,
                        None,
                        None,
                    )

        # Collect per-limit evaluation results from all violated test cases
        results: list[EvaluationResult] = []
        for evaluator in tc_evaluators:
            results.extend(evaluator.evaluate(detections, detections))

        return results, violation_event_ids, tracking_ids
