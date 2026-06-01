from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

import av

from .events_store import events_store_factory
from .geometry import (
    bbox_area,
    compute_position_pct,
    is_within_bbox,
    value_within_limits,
)
from .picture_renderer import Highlight, HighlightRole, hex_to_bgr, render_violation_picture
from .threshold_tracker import ThresholdTracker
from .zone_tracker import ZoneTracker, expected_entry_side, expected_exit_side

from ..models.dashboard.dashboard_config import DashboardConfig, DashboardCountMode
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
from ..paths import get_data_dir

logger = logging.getLogger(__name__)

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
    # Per-subject satisfaction for parent-label limits: id(parent_detection) ->
    # whether this parent's group passed the limit independently. None for
    # non-parent limits (where every subject shares the aggregate verdict).
    # Used by sample voting and the per-tracker lock decision so a passing
    # parent doesn't accumulate fail samples just because another in-zone
    # parent failed.
    parent_verdicts: dict[int, bool] | None = None
    # Symmetric to violating_parents/violating_children for the
    # parent-label branch: parents whose group satisfied the limit, and
    # all their children. Lets the test-case layer treat satisfying
    # parents as the "defective unit" under DEFECT semantics.
    satisfying_parents: list[BBoxDetection] | None = None
    satisfying_children: list[BBoxDetection] | None = None
    # Parents that violated (their group failed the limit) and every
    # target-label child inside them, used by the web overlay to expand
    # the highlight set beyond the per-item breakdown.
    violating_parents: list[BBoxDetection] | None = None
    violating_children: list[BBoxDetection] | None = None


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
    violating_parents: list[BBoxDetection] = field(default_factory=list)
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


def _aggregate_limit_value(lr: "LimitResult", tc_type: EvalTestCaseType) -> bool:
    """Reduce a LimitResult to a single 'satisfied' boolean under the test
    case's type semantics.

    For parent-label limits each parent is evaluated independently. CHECK's
    natural aggregate is AND (every parent must pass) — already what
    `lr.is_satisfied` carries. DEFECT's natural aggregate is OR (any
    defective parent = defect found); without this override, one clean
    sibling parent would suppress the violation for all the defective ones.
    """
    if tc_type == EvalTestCaseType.DEFECT and lr.parent_verdicts:
        return any(lr.parent_verdicts.values())
    return lr.is_satisfied


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
        if not self.limit.enabled:
            return True, False, [], []

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
        satisfying_parents: list[BBoxDetection] = []
        satisfying_children: list[BBoxDetection] = []
        parent_verdicts: dict[int, bool] = {}

        for p in parents:
            children = [t for t in all_labeled if is_within_bbox(t.coords, p.coords)]

            value, fired, sat, nsat = self._evaluate_items(children, children, [p])
            overall_fired = overall_fired or fired
            parent_verdicts[id(p)] = value

            # Per-detection attribution must follow each parent's own verdict:
            # a passing parent's per-item nsat (children that failed an
            # individual item but whose siblings carried the quantifier) must
            # not bleed into the failing-parent highlight set, and vice versa
            # for sat under DEFECT.
            if not value:
                overall_satisfied = False
                violating_parents.append(p)
                violating_children.extend(children)
                all_non_satisfying.extend(nsat)
            else:
                satisfying_parents.append(p)
                satisfying_children.extend(children)
                all_satisfying.extend(sat)

        return LimitResult(
            is_satisfied=overall_satisfied,
            fired=overall_fired,
            limit=self.limit,
            satisfying=_dedupe(all_satisfying),
            non_satisfying=_dedupe(all_non_satisfying),
            all_targets=violating_parents or violating_children,
            parent_verdicts=parent_verdicts,
            satisfying_parents=satisfying_parents,
            satisfying_children=_dedupe(satisfying_children),
            violating_parents=_dedupe(violating_parents),
            violating_children=_dedupe(violating_children),
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
            limit.id: LimitEvaluator(limit, config)
            for limit in test_case.limits
            if limit.enabled
        }

    def evaluate(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> tuple[bool, bool, list[LimitResult]]:
        """Evaluate the logic tree. Returns (is_satisfied, fired, limit_results)."""
        if not self.test_case.logicNodes:
            # No logic nodes means no limits → test case is trivially satisfied but not fired.
            return True, False, []

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
                    # Disabled or missing limit: drop the node from the tree
                    # entirely. Discard any pending operator/NOT so they don't
                    # latch onto the next operand. Avoids the AND/OR identity
                    # bias that would otherwise skew DEFECT verdicts.
                    pending_op = None
                    negate_next = False
                    continue
                lr = self.limit_evaluators[node.id].evaluate(
                    all_detections, crossed
                )
                collected.append(lr)
                value = _aggregate_limit_value(lr, self.test_case.type)
                node_fired = lr.fired
            else:  # GROUP
                value, node_fired, child_results = self._evaluate_nodes(
                    node.children or [], all_detections, crossed
                )
                if not child_results and not node_fired:
                    # Group resolved to nothing (all children disabled): drop
                    # like a disabled limit.
                    pending_op = None
                    negate_next = False
                    continue
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

    def combine_verdicts(self, verdicts: dict[str, bool]) -> bool | None:
        """Walk the logic tree using pre-reduced per-limit verdicts.

        verdicts: limit_id -> reduced is_satisfied. Limits absent from the dict
        are dropped from the tree (same drop semantics as disabled or missing
        limits in `_evaluate_nodes`).

        Returns the combined satisfaction, or None if no applicable limits
        remain (all dropped).
        """
        if not self.test_case.logicNodes:
            return None
        return self._combine_nodes(self.test_case.logicNodes, verdicts)

    def _combine_nodes(
        self, nodes: list[EvalLogicNode], verdicts: dict[str, bool]
    ) -> bool | None:
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

            if node.type == EvalLogicNodeType.LIMIT:
                if node.id not in verdicts:
                    pending_op = None
                    negate_next = False
                    continue
                value = verdicts[node.id]
            else:  # GROUP
                value = self._combine_nodes(node.children or [], verdicts)
                if value is None:
                    pending_op = None
                    negate_next = False
                    continue

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

        return result


# ---------------------------------------------------------------------------
# Test case evaluator
# ---------------------------------------------------------------------------


class TestCaseEvaluator:
    """Evaluates a single test case, applying CHECK/DEFECT semantics."""

    def __init__(self, test_case: EvalTestCase, config: DashboardConfig) -> None:
        self.test_case = test_case
        self._is_check = test_case.type == EvalTestCaseType.CHECK
        self._logic_evaluator = LogicTreeEvaluator(test_case, config)

    @property
    def is_check(self) -> bool:
        return self._is_check

    def _is_violated(self, is_satisfied: bool) -> bool:
        """Apply CHECK/DEFECT inversion: CHECK is violated when NOT satisfied."""
        return not is_satisfied if self._is_check else is_satisfied

    def limit_violating_detections(self, lr: LimitResult) -> list[BBoxDetection]:
        """Detections to flag for a violated limit (mirrors evaluate()).

        For parent-label DEFECT limits the defective parent is the highlighted
        unit; when the limit splits per child (AREA/positional) the specific
        satisfying children are highlighted instead — same shape CHECK uses
        with non_satisfying.
        """
        if self._is_check:
            return lr.non_satisfying or lr.all_targets
        if lr.limit.targetParentLabel is not None:
            # Per-child splittable limit (AREA/positional): defective children
            # are the items. COUNT has no per-child split, fall back to the
            # defective parents.
            if lr.satisfying:
                return lr.satisfying
            if lr.satisfying_parents:
                return lr.satisfying_parents
        return lr.satisfying or lr.all_targets

    def limit_highlight_sets(
        self, lr: LimitResult
    ) -> tuple[list[BBoxDetection], list[BBoxDetection]]:
        """Return (violating_parents, violating_children) for the web overlay.

        For parent-label limits: the parents that violated + all target-label
        children inside them (regardless of per-child verdict). For plain limits:
        empty parents + the existing per-detection violating set.
        """
        if lr.limit.targetParentLabel is None:
            return [], self.limit_violating_detections(lr)
        if self._is_check:
            return (lr.violating_parents or []), (lr.violating_children or [])
        # DEFECT: defective = satisfying under DEFECT semantics
        return (lr.satisfying_parents or []), (lr.satisfying_children or [])

    def is_violated(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> tuple[bool, bool]:
        """Quick check returning (is_violated, fired). Used for threshold tracking."""
        result, fired, _ = self._logic_evaluator.evaluate(all_detections, crossed)
        return self._is_violated(result), fired

    def evaluate_with_limit_results(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> tuple[bool, bool, list[LimitResult]]:
        """Returns (test_case_violated, fired, limit_results)."""
        combined, fired, limit_results = self._logic_evaluator.evaluate(
            all_detections, crossed
        )
        return self._is_violated(combined), fired, limit_results

    def build_evaluation_results(
        self, violated: bool, limit_results: list[LimitResult]
    ) -> list[EvaluationResult]:
        """Convert LimitResults to EvaluationResults, applying CHECK/DEFECT semantics."""
        if not violated:
            return []

        tc = self.test_case
        results: list[EvaluationResult] = []
        for lr in limit_results:
            if not lr.fired:
                continue
            # Match the LogicTreeEvaluator's per-test-case aggregate so a
            # parent-label DEFECT limit emits a result for each frame where
            # any defective parent is in the zone, not only when every parent
            # is defective.
            lr_value = _aggregate_limit_value(lr, tc.type)
            if not self._is_violated(lr_value):
                continue

            # CHECK: non-satisfying detections failed the check
            # DEFECT: satisfying detections are the defects
            # Fall back to all_targets for COUNT (no per-detection split)
            highlight_parents, violating = self.limit_highlight_sets(lr)

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
                    violating_parents=highlight_parents,
                )
            )

        # If no individual limit produced a result, still record the test case
        # violation — but only if at least one enabled limit actually fired.
        # Without this gate, an "all-disabled" or trivially-satisfied logic
        # tree would emit a synthetic violation every frame for DEFECT.
        if not results and any(lr.fired for lr in limit_results):
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

    def evaluate(
        self, all_detections: list[BBoxDetection], crossed: list[BBoxDetection]
    ) -> list[EvaluationResult]:
        """Evaluate and return per-limit EvaluationResults if the test case is violated."""
        violated, _, limit_results = self.evaluate_with_limit_results(
            all_detections, crossed
        )
        return self.build_evaluation_results(violated, limit_results)


# ---------------------------------------------------------------------------
# Dashboard evaluator (top-level)
# ---------------------------------------------------------------------------


class DashboardEvaluator:
    """Top-level evaluator: manages zone presence state and evaluates test cases.

    For each confirmed tracker, evaluation samples are accumulated while it is
    inside the configured zone. When the tracker leaves the zone (or its
    Kalman ghost expires), the accumulated pass/fail samples are reduced to a
    single verdict using the config's optimistic/pessimistic flag, and that
    verdict is committed to the threshold tracker and events store exactly
    once per (tracker, test case).
    """

    def __init__(
        self,
        zone_tracker: ZoneTracker,
        threshold_tracker: ThresholdTracker,
    ) -> None:
        self._tracker = zone_tracker
        self._threshold_tracker = threshold_tracker
        # config_id -> tracker_id -> test_case_id -> {
        #   "limits": {limit_id: {"pass": int, "fail": int}},
        #   "last_violation": list[EvaluationResult] | None,
        # }
        # Per-limit pass/fail counts are reduced independently at commit, then
        # combined via the test case's logic tree. This lets a limit that
        # passed on one frame and another that passed on a different frame
        # both count as "passed" for an AND-combined optimistic test case.
        self._samples: dict[int, dict[int, dict[str, dict]]] = {}
        # config_id -> set of tracker_ids whose entry side matched the
        # configured zoneDirection. Only these trackers accumulate samples
        # and are eligible for commit on exit.
        self._valid_entries: dict[int, set[int]] = {}
        # config_id -> tracker_id -> (label_id, label_name). Captured during
        # dwell so the ON_ZONE_ENTER counter can fire on clean exit (where
        # only the tracker_id is available). Write-once via setdefault.
        self._tracker_labels: dict[int, dict[int, tuple[int, str]]] = {}
        # config_id -> tracker_id -> limit_id -> lock entry. Optimistic locks
        # store {"verdict": "pass"} and suppress later violations of that
        # (tracker, limit). Pessimistic locks store {"verdict": "fail", ...
        # limit metadata} so the highlight can be re-emitted as a sticky
        # synthetic violation on later frames where the live evaluator no
        # longer flags the detection. Locks are write-once and survive zone
        # exit; cleared only on reset(config_id).
        self._lock_state: dict[int, dict[int, dict[str, dict]]] = {}
        # config_id -> set of tracker_ids that have completed a successful
        # evaluation commit (valid entry + correct exit). Re-entries of these
        # trackers are ignored so a path reversal that takes the same physical
        # object through the zone twice does not produce two evaluation
        # events. Cleared only on reset(config_id).
        self._committed: dict[int, set[int]] = {}
        # config_id -> set of tracker_ids that have ever validly entered the
        # zone (entry side matched zoneDirection). Persistent gate for the
        # live-overlay violation emission: trackers not in this set never get
        # alerts/warnings, before or after their zone dwell. Cleared only on
        # reset(config_id).
        self._entered_validly: dict[int, set[int]] = {}
        # config_id -> tracker_id -> limit_id -> fail-lock metadata captured
        # during dwell in optimistic mode. At clean exit, promoted into
        # _lock_state as fail-locks (when no pass-lock exists) so the sticky
        # re-emission loop keeps the highlight after the tracker has left the
        # zone. Discarded on any other kind of exit and on reset.
        self._pending_fails: dict[int, dict[int, dict[str, dict]]] = {}

    def reset(self, config_id: int) -> None:
        """Clear all per-tracker state for a config (on dashboard start)."""
        self._tracker.reset(config_id)
        self._samples.pop(config_id, None)
        self._valid_entries.pop(config_id, None)
        self._tracker_labels.pop(config_id, None)
        self._lock_state.pop(config_id, None)
        self._committed.pop(config_id, None)
        self._entered_validly.pop(config_id, None)
        self._pending_fails.pop(config_id, None)

    @staticmethod
    def _build_highlights(
        violated_limits: list[dict],
        limit_defs_by_id: dict[str, EvalLimit],
        display_lookup: dict[tuple[int, int], tuple[float, float, float, float]],
    ) -> list[Highlight]:
        """Map each violated_limit row to the bbox(es) it references.

        Mirrors the (display_id, parent_display_id) shape produced upstream:
          - parent_display_id is None + limit has a parent label: the parent
            itself failed — draw red.
          - parent_display_id is None + limit has no parent label: non-parent
            subject — draw in the target label's color.
          - parent_display_id is not None: hierarchical violation — child draws
            in its label color, parent draws red.

        display_ids absent from `display_lookup` (item off-camera at commit)
        are skipped silently; the picture then highlights whatever is still
        visible from the recorded rows.
        """
        out: list[Highlight] = []
        for row in violated_limits:
            limit_def = limit_defs_by_id.get(row["limit_id"])
            if limit_def is None:
                continue
            child_did = row.get("display_id")
            parent_did = row.get("parent_display_id")

            if parent_did is None:
                if child_did is None:
                    continue
                if limit_def.targetParentLabel is not None:
                    # Parent itself failed (parent-label limit).
                    label_id = limit_def.targetParentLabel.id
                    role: HighlightRole = "parent"
                    coords = display_lookup.get((label_id, child_did))
                    if coords is not None:
                        out.append(
                            Highlight(role=role, display_id=child_did, coords=coords)
                        )
                else:
                    label_id = limit_def.targetLabel.id
                    role = "child"
                    coords = display_lookup.get((label_id, child_did))
                    if coords is not None:
                        out.append(
                            Highlight(
                                role=role,
                                display_id=child_did,
                                coords=coords,
                                color=hex_to_bgr(limit_def.targetLabel.color),
                            )
                        )
            else:
                if child_did is not None:
                    child_coords = display_lookup.get(
                        (limit_def.targetLabel.id, child_did)
                    )
                    if child_coords is not None:
                        out.append(
                            Highlight(
                                role="child",
                                display_id=child_did,
                                coords=child_coords,
                                color=hex_to_bgr(limit_def.targetLabel.color),
                            )
                        )
                if limit_def.targetParentLabel is not None:
                    parent_coords = display_lookup.get(
                        (limit_def.targetParentLabel.id, parent_did)
                    )
                    if parent_coords is not None:
                        out.append(
                            Highlight(
                                role="parent",
                                display_id=parent_did,
                                coords=parent_coords,
                            )
                        )
        return out

    @staticmethod
    def _build_tc_parent_highlights(
        test_case: EvalTestCase,
        exit_label_id: int | None,
        exit_display_id: int | None,
        display_lookup: dict[tuple[int, int], tuple[float, float, float, float]],
    ) -> list[Highlight]:
        """Blue box for the single parent currently exiting the zone, IFF its
        label is the ``targetParentLabel`` of an enabled limit in `test_case`
        and the tracker is still visible in the commit frame. Other parents
        sharing the frame are intentionally not highlighted — the picture is
        about the object whose verdict is being committed, not every parent
        that happens to be on camera.
        """
        if exit_label_id is None or exit_display_id is None:
            return []
        parent_label_ids: set[int] = {
            limit.targetParentLabel.id
            for limit in test_case.limits
            if limit.enabled and limit.targetParentLabel is not None
        }
        if exit_label_id not in parent_label_ids:
            return []
        coords = display_lookup.get((exit_label_id, exit_display_id))
        if coords is None:
            return []
        return [
            Highlight(role="parent", display_id=exit_display_id, coords=coords)
        ]

    @staticmethod
    def _build_tc_child_highlights(
        child_label_colors: dict[int, tuple[int, int, int]],
        exit_coords: tuple[float, float, float, float] | None,
        detections: list[BBoxDetection],
        display_ids: list[int | None],
        label_id_by_idx: dict[int, int],
    ) -> list[Highlight]:
        """Colored boxes for every detection whose label is in ``child_label_colors``
        and whose bbox center falls inside ``exit_coords``.

        Empty ``child_label_colors`` or missing ``exit_coords`` produce an empty list.
        """
        if not child_label_colors or exit_coords is None:
            return []
        out: list[Highlight] = []
        for i, det in enumerate(detections):
            did = display_ids[i]
            if did is None:
                continue
            label_id = label_id_by_idx.get(det.label)
            if label_id is None or label_id not in child_label_colors:
                continue
            if not is_within_bbox(det.coords, exit_coords):
                continue
            out.append(
                Highlight(
                    role="child",
                    display_id=did,
                    coords=det.coords,
                    color=child_label_colors[label_id],
                )
            )
        return out

    @staticmethod
    def _render_and_save_picture(
        video_frame: av.VideoFrame, highlights: list[Highlight]
    ) -> str | None:
        """Render `highlights` onto `video_frame` and write JPEG to disk.

        Returns the relative ``event_pictures/<uuid>.jpg`` path on success or
        None on any failure (corrupt frame, encode error, IO error) — the
        event is still saved in that case, just without a picture.
        """
        try:
            jpeg_bytes = render_violation_picture(video_frame, highlights)
            pictures_dir = get_data_dir() / "event_pictures"
            pictures_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid.uuid4().hex}.jpg"
            (pictures_dir / filename).write_bytes(jpeg_bytes)
            return f"event_pictures/{filename}"
        except Exception:
            logger.exception("Failed to render violation picture")
            return None

    def _reduce_verdict(
        self, samples: dict, optimistic: bool, is_check: bool
    ) -> bool | None:
        """Reduce per-frame samples to a single 'limit satisfied' verdict.

        Samples are accumulated CHECK-style: "pass" = limit was satisfied on
        that frame, "fail" = not satisfied. Optimistic mode forgives toward
        the test-case-passed direction, which means opposite things for
        CHECK and DEFECT:
          - CHECK passes when the limit is satisfied → optimistic = any
            satisfied frame wins.
          - DEFECT passes when the limit is NOT satisfied (no defect this
            frame) → optimistic = any unsatisfied frame wins, so the reduced
            verdict only lands on True ("defect found") when every frame had
            defect.

        Without this flip, a single false-negative frame (NN misses the
        target inside the parent) is enough to commit the dwell as defective
        even though the optimistic flag is on.
        """
        total = samples["pass"] + samples["fail"]
        if total == 0:
            return None
        if is_check:
            return samples["pass"] > 0 if optimistic else samples["fail"] == 0
        return samples["fail"] == 0 if optimistic else samples["pass"] > 0

    @staticmethod
    def _subject_satisfied(lr: LimitResult, det: BBoxDetection) -> bool:
        """Per-subject satisfaction. For parent-label limits, returns the
        individual parent's verdict; for non-parent limits, the aggregate.

        Default True for a parent missing from parent_verdicts (subject not
        evaluated this frame) so we never fabricate a fail vote for a subject
        the limit didn't actually rule on.
        """
        if lr.parent_verdicts is not None:
            return lr.parent_verdicts.get(id(det), True)
        return lr.is_satisfied

    @staticmethod
    def _subject_label_ids(test_case: EvalTestCase) -> set[int]:
        """Label IDs whose trackers accumulate samples for this test case.

        A limit's subject is its parent label (when present) else its target
        label — i.e. the "item" whose verdict we are aggregating across the
        zone dwell.
        """
        ids: set[int] = set()
        for limit in test_case.limits:
            if limit.targetParentLabel is not None:
                ids.add(limit.targetParentLabel.id)
            else:
                ids.add(limit.targetLabel.id)
        return ids

    @staticmethod
    def _build_tracker_maps(
        detections: list[BBoxDetection], zr
    ) -> tuple[dict[int, int], dict[int, int]]:
        """Return (det_tid_by_det_id, tid_to_display_id) for snapshot building."""
        det_tid_by_det_id: dict[int, int] = {
            id(detections[i]): zr.tracking_ids[i]
            for i in range(len(detections))
            if zr.tracking_ids[i] is not None
        }
        tid_to_display_id: dict[int, int] = {}
        for i in range(len(zr.tracking_ids)):
            t, d = zr.tracking_ids[i], zr.display_ids[i]
            if t is not None and d is not None:
                tid_to_display_id[t] = d
        return det_tid_by_det_id, tid_to_display_id

    @staticmethod
    def _build_limit_lookups(
        test_case: EvalTestCase, limit_results: list[LimitResult]
    ) -> tuple[dict[str, EvalLimit], dict[str, LimitResult], dict[str, int]]:
        """Return (limit_defs, lr_by_id, limit_meta) keyed by limit id.

        limit_meta maps each fired limit to the label id that is the
        evaluation subject (parent label when set, else target label).
        """
        limit_defs = {lm.id: lm for lm in test_case.limits}
        lr_by_id = {lr.limit.id: lr for lr in limit_results}
        limit_meta: dict[str, int] = {
            lr.limit.id: (
                lr.limit.targetParentLabel.id
                if lr.limit.targetParentLabel is not None
                else lr.limit.targetLabel.id
            )
            for lr in limit_results
            if lr.fired
        }
        return limit_defs, lr_by_id, limit_meta

    def _accumulate_subject_sample(
        self,
        evaluator: "TestCaseEvaluator",
        det: BBoxDetection,
        det_label_id: int,
        det_did: int | None,
        detections: list[BBoxDetection],
        config: DashboardConfig,
        violated: bool,
        limit_results: list[LimitResult],
        latest_results: list[EvaluationResult],
        tc_samples: dict,
        det_tid_by_det_id: dict[int, int],
        tid_to_display_id: dict[int, int],
        limit_defs: dict[str, EvalLimit],
        lr_by_id: dict[str, LimitResult],
        limit_meta: dict[str, int],
    ) -> None:
        """Accumulate one frame's sample vote and violation snapshot for one subject detection."""
        if violated:
            subj_snapshot: list[dict] = []
            subj_coords_map: dict[
                tuple[int, int], tuple[float, float, float, float]
            ] = {}
            for r in latest_results:
                if r.violated_limit_id is None:
                    continue
                limit_def = limit_defs.get(r.violated_limit_id)
                lr = lr_by_id.get(r.violated_limit_id)
                if limit_def is None or lr is None:
                    continue
                parent_label_id = (
                    limit_def.targetParentLabel.id
                    if limit_def.targetParentLabel is not None
                    else None
                )
                items: list[tuple[int | None, int | None]] = []
                if parent_label_id is not None:
                    if det_label_id != parent_label_id:
                        continue
                    if lr.parent_verdicts is None:
                        subject_violated = evaluator._is_violated(lr.is_satisfied)
                    else:
                        subject_violated = evaluator._is_violated(
                            lr.parent_verdicts.get(id(det), True)
                        )
                    if not subject_violated:
                        continue
                    if det_did is not None:
                        subj_coords_map[(parent_label_id, det_did)] = det.coords
                    for d in r.violating_detections:
                        if id(d) == id(det):
                            items.append((det_did, None))
                        elif (
                            config.labels[d.label].id != parent_label_id
                            and is_within_bbox(d.coords, det.coords)
                        ):
                            d_tid = det_tid_by_det_id.get(id(d))
                            d_did = (
                                tid_to_display_id.get(d_tid)
                                if d_tid is not None
                                else None
                            )
                            items.append((d_did, det_did))
                            if d_did is not None:
                                subj_coords_map[
                                    (limit_def.targetLabel.id, d_did)
                                ] = d.coords
                    if not items:
                        items.append((det_did, None))
                else:
                    if det_label_id != limit_def.targetLabel.id:
                        continue
                    violating_ids = {id(d) for d in r.violating_detections}
                    if not r.violating_detections:
                        items.append((det_did, None))
                    elif id(det) in violating_ids:
                        items.append((det_did, None))
                    else:
                        continue
                    if det_did is not None:
                        subj_coords_map[
                            (limit_def.targetLabel.id, det_did)
                        ] = det.coords
                if items:
                    subj_snapshot.append(
                        {
                            "limit_id": r.violated_limit_id,
                            "limit_name": r.violated_limit_name or "",
                            "items": items,
                        }
                    )
            if subj_snapshot:
                tc_samples["last_violation"] = subj_snapshot
                tc_samples["last_violation_coords"] = subj_coords_map

        for lr in limit_results:
            if not lr.fired:
                continue
            if det_label_id != limit_meta.get(lr.limit.id):
                continue
            l_samples = tc_samples["limits"].setdefault(
                lr.limit.id, {"pass": 0, "fail": 0}
            )
            if self._subject_satisfied(lr, det):
                l_samples["pass"] += 1
            else:
                l_samples["fail"] += 1

    def evaluate(
        self,
        config: DashboardConfig,
        detections: list[BBoxDetection],
        dashboard_run_session_id: int,
        video_frame: av.VideoFrame | None = None,
    ) -> tuple[
        list[EvaluationResult],
        list[int | None],
        list[int | None],
    ]:
        """Evaluate test cases and return per-frame overlay results.

        Returns a tuple of:
        - list of EvaluationResult for the live per-frame overlay
        - tracking IDs parallel to the input detections list
        - display IDs parallel to the input detections list (per-label)

        `video_frame` is the latest camera frame; if provided, the commit
        branch renders a violation picture onto a copy and writes it to
        ``event_pictures/`` before persisting the event.
        """
        events_store = events_store_factory()
        zr = self._tracker.find_in_zone_detections(detections, config)

        expected_in = expected_entry_side(config.zoneDirection)
        expected_out = expected_exit_side(config.zoneDirection)
        valid_entries = self._valid_entries.setdefault(config.id, set())
        cfg_tracker_labels = self._tracker_labels.setdefault(config.id, {})
        committed = self._committed.setdefault(config.id, set())
        entered_validly = self._entered_validly.setdefault(config.id, set())
        cfg_pending = self._pending_fails.setdefault(config.id, {})

        # Record trackers whose entry matched the configured direction. These
        # are the only ones eligible for the direction-aware counter and for
        # an evaluation commit on exit. Trackers that already completed a
        # successful commit are excluded — re-entry of the same Kalman track
        # must not produce a second evaluation.
        for tid, side in zr.entry_sides.items():
            if tid in committed:
                continue
            if side == expected_in:
                valid_entries.add(tid)
                entered_validly.add(tid)

        # ON_ZONE_ENTER counts at exit-commit (below) so the running counter
        # and test-case widgets advance together for the same item. Capture
        # each valid-entry tracker's label here while we still have a
        # detection in hand; the exit branch only sees a tracker_id.
        for i, det in enumerate(zr.in_zone):
            tid = zr.in_zone_tracker_ids[i]
            if tid not in valid_entries:
                continue
            label = config.labels[det.label]
            cfg_tracker_labels.setdefault(tid, (label.id, label.name))

        if config.countMode == DashboardCountMode.ON_CONFIRM:
            # Counter ticks the frame a tracker is confirmed by Kalman,
            # regardless of zone presence.
            for _display_id, label_int in zr.just_confirmed:
                label = config.labels[label_int]
                events_store.inc_counter(dashboard_run_session_id, label.id, label.name)

        tc_evaluators = [
            TestCaseEvaluator(tc, config) for tc in config.testCases if tc.enabled
        ]
        enabled_tc_ids = {e.test_case.id for e in tc_evaluators}
        cfg_samples = self._samples.setdefault(config.id, {})

        # Per-frame sampling: attribute the test case verdict only to the
        # subject trackers in the zone (parent label where present, else the
        # target label). This keeps threshold metrics item-scoped — e.g. a
        # pallet defect is charged to the pallet, not to every crate riding
        # on top of it.
        cfg_locks = self._lock_state.setdefault(config.id, {})
        if zr.in_zone and zr.in_zone_tracker_ids:
            det_tid_by_det_id, tid_to_display_id = self._build_tracker_maps(
                detections, zr
            )
            for evaluator in tc_evaluators:
                violated, fired, limit_results = evaluator.evaluate_with_limit_results(
                    detections, zr.in_zone
                )
                if not fired:
                    continue
                subject_ids = self._subject_label_ids(evaluator.test_case)
                if not subject_ids:
                    continue
                latest_results: list[EvaluationResult] = (
                    evaluator.build_evaluation_results(violated, limit_results)
                    if violated
                    else []
                )
                limit_defs, lr_by_id, limit_meta = self._build_limit_lookups(
                    evaluator.test_case, limit_results
                )
                for i, det in enumerate(zr.in_zone):
                    det_label_id = config.labels[det.label].id
                    if det_label_id not in subject_ids:
                        continue
                    tid = zr.in_zone_tracker_ids[i]
                    if tid not in valid_entries:
                        continue
                    tr_samples = cfg_samples.setdefault(tid, {})
                    tc_samples = tr_samples.setdefault(
                        evaluator.test_case.id,
                        {
                            "limits": {},
                            "last_violation": None,
                            "last_violation_coords": None,
                        },
                    )
                    self._accumulate_subject_sample(
                        evaluator,
                        det,
                        det_label_id,
                        tid_to_display_id.get(tid),
                        detections,
                        config,
                        violated,
                        limit_results,
                        latest_results,
                        tc_samples,
                        det_tid_by_det_id,
                        tid_to_display_id,
                        limit_defs,
                        lr_by_id,
                        limit_meta,
                    )

                # Per-limit, per-tracker lock update: write-once entries that
                # mute (optimistic, locked-pass) or sticky (pessimistic,
                # locked-fail) the live highlight for the rest of the
                # tracker's life. Lock keying mirrors what the live overlay
                # actually highlights — a detection is "failing" only when
                # its own id appears in the limit's violating detections. For
                # AREA/positional with parent-label this means parents are
                # never marked failing (the live overlay flags children, not
                # the parent), so the sticky loop won't extend the highlight
                # onto the parent after exit. Per-parent satisfaction is used
                # for sample voting only.
                for lr in limit_results:
                    if not lr.fired:
                        continue
                    limit_subject_id = limit_meta[lr.limit.id]
                    # Use the per-test-case aggregate so a parent-label DEFECT
                    # limit registers as violated when any defective parent is
                    # present — otherwise a clean sibling parent's False
                    # verdict would AND-out the True one and every parent's
                    # tracker would wrongly get a pass-lock, silently
                    # suppressing the live overlay's red border.
                    lr_value = _aggregate_limit_value(
                        lr, evaluator.test_case.type
                    )
                    limit_violated = (
                        (not lr_value) if evaluator.is_check else lr_value
                    )
                    failing_ids: set[int] = set()
                    if limit_violated:
                        failing_ids = {
                            id(d) for d in evaluator.limit_violating_detections(lr)
                        }
                    for i, det in enumerate(zr.in_zone):
                        if config.labels[det.label].id != limit_subject_id:
                            continue
                        tid = zr.in_zone_tracker_ids[i]
                        if tid not in valid_entries:
                            continue
                        tr_locks = cfg_locks.setdefault(tid, {})
                        if lr.limit.id in tr_locks:
                            continue
                        is_failing = id(det) in failing_ids
                        # For parent-label limits the subject is the parent, but
                        # failing_ids contains children — so is_failing is always
                        # False for parents. Use the parent's own per-subject
                        # verdict for the pass-lock decision instead, so the lock
                        # is only written when that parent actually satisfied the
                        # limit (matching the per-parent commit reduction).
                        # The fail-lock / pending arms below remain keyed on
                        # is_failing to preserve the existing behavior that
                        # parent-label limits flag children, not the parent, and
                        # never sticky-re-emit onto the parent after zone exit.
                        if lr.limit.targetParentLabel is not None:
                            subject_ok = not evaluator._is_violated(
                                self._subject_satisfied(lr, det)
                            )
                        else:
                            subject_ok = not is_failing
                        if config.optimistic and subject_ok:
                            tr_locks[lr.limit.id] = {"verdict": "pass"}
                        elif (not config.optimistic) and is_failing:
                            tr_locks[lr.limit.id] = {
                                "verdict": "fail",
                                "test_case_id": evaluator.test_case.id,
                                "test_case_name": evaluator.test_case.name,
                                "limit_name": lr.limit.name,
                                "severity": (
                                    lr.limit.severity.value
                                    if lr.limit.severity
                                    else None
                                ),
                                "target_label_id": lr.limit.targetLabel.id,
                            }
                        elif config.optimistic and is_failing:
                            # Optimistic mode: capture fail metadata as pending.
                            # On clean exit (no pass occurred during dwell) it's
                            # promoted to a fail-lock so the sticky loop keeps
                            # the highlight after the tracker leaves the zone.
                            # Write-once via setdefault — first failing frame
                            # wins; verdict at exit is "no pass ever", so any
                            # captured metadata is sufficient.
                            cfg_pending.setdefault(tid, {}).setdefault(
                                lr.limit.id,
                                {
                                    "verdict": "fail",
                                    "test_case_id": evaluator.test_case.id,
                                    "test_case_name": evaluator.test_case.name,
                                    "limit_name": lr.limit.name,
                                    "severity": (
                                        lr.limit.severity.value
                                        if lr.limit.severity
                                        else None
                                    ),
                                    "target_label_id": lr.limit.targetLabel.id,
                                },
                            )

        # Commit on zone exit: reduce accumulated samples and record once.
        # Discard everything for trackers whose entry/exit didn't follow the
        # configured zoneDirection (wrong-flow exit, expired ghosts, etc.).
        # Wrong-direction or expired exits also clear any sticky fail-locks
        # so the UI doesn't keep flagging an "incomplete run" — matches the
        # threshold/event-recording behavior, which discards those samples.
        tc_by_id = {e.test_case.id: e.test_case for e in tc_evaluators}

        # detection.label is an index into config.labels; build a flat
        # idx -> label_id map once so the commit-frame loops (display_lookup
        # and the relevant-children walk) don't keep dereferencing it.
        label_id_by_idx: dict[int, int] = {
            i: lbl.id for i, lbl in enumerate(config.labels)
        }

        # (label_id, display_id) -> normalized coords of the matching detection
        # in the current frame. Used at commit to look up bboxes for the
        # violating items recorded in violated_limits, so the saved picture
        # highlights exactly those rows and nothing else. Items already off
        # camera at commit are absent from this map and silently skipped.
        display_lookup: dict[tuple[int, int], tuple[float, float, float, float]] = {}
        for i, det_i in enumerate(detections):
            did_i = zr.display_ids[i]
            if did_i is None:
                continue
            label_id_i = label_id_by_idx[det_i.label]
            display_lookup[(label_id_i, did_i)] = det_i.coords

        # tracker_id -> display_id for the commit frame. Used to resolve the
        # exiting tracker's display_id when rendering a passing-event picture
        # so we highlight only that one parent, not every parent in frame.
        commit_tid_to_did: dict[int, int] = {}
        for di_idx in range(len(zr.tracking_ids)):
            t_at = zr.tracking_ids[di_idx]
            d_at = zr.display_ids[di_idx]
            if t_at is not None and d_at is not None:
                commit_tid_to_did[t_at] = d_at

        # limit_id -> EvalLimit, for resolving targetLabel/targetParentLabel
        # of each violated row at commit. Built once per evaluate() call.
        limit_defs_by_id: dict[str, EvalLimit] = {}
        for tc in config.testCases:
            for limit in tc.limits:
                limit_defs_by_id[limit.id] = limit
        for tid in zr.exited_tracker_ids:
            tr_samples = cfg_samples.pop(tid, None)
            tr_pending = cfg_pending.pop(tid, None)
            tr_label = cfg_tracker_labels.pop(tid, None)
            entry_ok = tid in valid_entries
            valid_entries.discard(tid)
            clean_exit = entry_ok and zr.exit_sides.get(tid) == expected_out
            if not clean_exit:
                # Discard everything for trackers that didn't complete a valid
                # traversal: pessimistic fail-locks written during dwell are
                # cleared (pending fails already popped above), and the tracker
                # is removed from entered_validly so the live overlay also
                # stops emitting until it validly re-enters the zone.
                cfg_locks.pop(tid, None)
                entered_validly.discard(tid)
                continue
            if (
                config.countMode == DashboardCountMode.ON_ZONE_ENTER
                and tr_label is not None
            ):
                label_id, label_name = tr_label
                events_store.inc_counter(
                    dashboard_run_session_id, label_id, label_name
                )
            if tr_samples is None:
                continue
            committed.add(tid)
            # Optimistic: promote pending fails into permanent fail-locks for
            # limits that never passed during dwell. setdefault ensures we
            # never overwrite a pass-lock that was written on a passing frame.
            if tr_pending:
                tr_locks = cfg_locks.setdefault(tid, {})
                for limit_id, info in tr_pending.items():
                    tr_locks.setdefault(limit_id, info)
            # Sample the commit (zone-exit) frame so the saved picture is a
            # frame that contributed to the verdict.
            commit_det_idx = next(
                (i for i, t in enumerate(zr.tracking_ids) if t == tid),
                None,
            )
            if commit_det_idx is not None:
                commit_det = detections[commit_det_idx]
                commit_det_label_id = label_id_by_idx[commit_det.label]
                commit_det_did = zr.display_ids[commit_det_idx]
                commit_tid_map, commit_did_map = self._build_tracker_maps(
                    detections, zr
                )
                for evaluator in tc_evaluators:
                    violated, fired, limit_results = (
                        evaluator.evaluate_with_limit_results(
                            detections, [commit_det]
                        )
                    )
                    if not fired:
                        continue
                    if commit_det_label_id not in self._subject_label_ids(
                        evaluator.test_case
                    ):
                        continue
                    tc_samples = tr_samples.setdefault(
                        evaluator.test_case.id,
                        {
                            "limits": {},
                            "last_violation": None,
                            "last_violation_coords": None,
                        },
                    )
                    latest_results: list[EvaluationResult] = (
                        evaluator.build_evaluation_results(violated, limit_results)
                        if violated
                        else []
                    )
                    c_limit_defs, c_lr_by_id, c_limit_meta = (
                        self._build_limit_lookups(evaluator.test_case, limit_results)
                    )
                    self._accumulate_subject_sample(
                        evaluator,
                        commit_det,
                        commit_det_label_id,
                        commit_det_did,
                        detections,
                        config,
                        violated,
                        limit_results,
                        latest_results,
                        tc_samples,
                        commit_tid_map,
                        commit_did_map,
                        c_limit_defs,
                        c_lr_by_id,
                        c_limit_meta,
                    )
            for tc_id, tc_data in tr_samples.items():
                tc = tc_by_id.get(tc_id)
                if tc is None:
                    continue
                matching_eval = next(
                    (e for e in tc_evaluators if e.test_case.id == tc_id), None
                )
                if matching_eval is None:
                    continue

                # Reduce each limit's per-frame samples into a single verdict,
                # then combine via the test case's logic tree. Limits that
                # never fired are dropped from the tree, mirroring the live
                # evaluator's disabled-limit handling.
                verdicts: dict[str, bool] = {}
                for limit_id, l_samples in tc_data["limits"].items():
                    v = self._reduce_verdict(
                        l_samples, config.optimistic, matching_eval.is_check
                    )
                    if v is not None:
                        verdicts[limit_id] = v
                if not verdicts:
                    continue

                combined = matching_eval._logic_evaluator.combine_verdicts(verdicts)
                if combined is None:
                    continue

                passed = not matching_eval._is_violated(combined)
                self._threshold_tracker.record(config.id, tc_id, passed=passed)

                # One event row per (commit, test case) carrying the
                # passed/violated verdict. When violated, the per-item
                # breakdown from `last_violation` lands in the child
                # dashboard_evaluation_event_violated_limit table — one
                # row per (limit, violating item, parent), deduplicated.
                # Display IDs (per-label sequence numbers visible on the
                # captured picture) are stored, not Kalman tracker IDs.
                violated_limits: list[dict] = []
                if not passed:
                    last_violation = tc_data.get("last_violation") or []
                    seen_keys: set[
                        tuple[str, int | None, int | None]
                    ] = set()
                    for entry in last_violation:
                        limit_id = entry["limit_id"]
                        limit_name = entry["limit_name"]
                        for display_id, parent_display_id in entry["items"]:
                            key = (limit_id, display_id, parent_display_id)
                            if key in seen_keys:
                                continue
                            seen_keys.add(key)
                            violated_limits.append(
                                {
                                    "limit_id": limit_id,
                                    "limit_name": limit_name,
                                    "display_id": display_id,
                                    "parent_display_id": parent_display_id,
                                }
                            )

                picture_url: str | None = None
                if video_frame is not None:
                    exit_label_id = tr_label[0] if tr_label is not None else None
                    exit_did = commit_tid_to_did.get(tid)
                    exit_coords = (
                        display_lookup.get((exit_label_id, exit_did))
                        if exit_label_id is not None and exit_did is not None
                        else None
                    )
                    # Blue exit-parent shown for passing and failing events;
                    # failing events layer violator highlights on top when
                    # resolvable. Bare frame saved as last resort.
                    highlights = self._build_tc_parent_highlights(
                        tc, exit_label_id, exit_did, display_lookup
                    )
                    if not passed:
                        violated_child_label_colors: dict[
                            int, tuple[int, int, int]
                        ] = {
                            ld.targetLabel.id: hex_to_bgr(ld.targetLabel.color)
                            for r in (violated_limits or [])
                            if (ld := limit_defs_by_id.get(r["limit_id"])) is not None
                            and ld.targetParentLabel is not None
                            and exit_label_id is not None
                            and ld.targetParentLabel.id == exit_label_id
                        }
                        highlights += self._build_tc_child_highlights(
                            violated_child_label_colors,
                            exit_coords,
                            detections,
                            zr.display_ids,
                            label_id_by_idx,
                        )
                        parentless_rows = [
                            r for r in (violated_limits or [])
                            if (ld2 := limit_defs_by_id.get(r["limit_id"])) is not None
                            and ld2.targetParentLabel is None
                        ]
                        highlights += self._build_highlights(
                            parentless_rows, limit_defs_by_id, display_lookup
                        )
                    picture_url = self._render_and_save_picture(video_frame, highlights)

                events_store.save_event(
                    dashboard_run_session_id,
                    tc_id,
                    tc.name,
                    passed,
                    violated_limits or None,
                    picture_url,
                )

        # Live overlay: evaluate every visible detection, then gate emission
        # on validated zone entry so trackers that haven't (or won't ever)
        # validly enter the zone never produce alerts. Per-(tracker, limit)
        # locks then reshape the highlight: optimistic pass-locks suppress
        # later violations of a passed limit; fail-locks add sticky violations
        # for limits that have already failed.
        det_to_tid: dict[int, int] = {}
        tid_to_det: dict[int, BBoxDetection] = {}
        for i, d in enumerate(detections):
            tid = zr.tracking_ids[i]
            if tid is None:
                continue
            det_to_tid[id(d)] = tid
            tid_to_det[tid] = d

        results: list[EvaluationResult] = []
        emitted_violations: set[tuple[int, str]] = set()
        for evaluator in tc_evaluators:
            for ev in evaluator.evaluate(detections, detections):
                if ev.violated_limit_id is None:
                    results.append(ev)
                    continue
                if ev.violating_parents:
                    # Parent-label limit: gate and suppress on the parent
                    # (subject) tracker, not on children's trackers.
                    gated_parents = [
                        p
                        for p in ev.violating_parents
                        if det_to_tid.get(id(p)) in entered_validly
                    ]
                    if not gated_parents:
                        continue
                    if config.optimistic:
                        surviving_parents = [
                            p
                            for p in gated_parents
                            if not (
                                det_to_tid.get(id(p)) is not None
                                and cfg_locks.get(
                                    det_to_tid[id(p)], {}
                                ).get(ev.violated_limit_id, {}).get("verdict")
                                == "pass"
                            )
                        ]
                        if not surviving_parents:
                            continue
                        gated_parents = surviving_parents
                    ev.violating_parents = gated_parents
                    # Keep children whose bbox falls inside a surviving parent.
                    ev.violating_detections = [
                        c
                        for c in ev.violating_detections
                        if any(
                            is_within_bbox(c.coords, p.coords)
                            for p in gated_parents
                        )
                    ]
                    results.append(ev)
                    for p in gated_parents:
                        tid = det_to_tid.get(id(p))
                        if tid is not None:
                            emitted_violations.add((tid, ev.violated_limit_id))
                else:
                    # No-parent limit: gate on the detection's own tracker.
                    gated = [
                        d
                        for d in ev.violating_detections
                        if det_to_tid.get(id(d)) in entered_validly
                    ]
                    if not gated:
                        continue
                    if config.optimistic:
                        filtered = []
                        for d in gated:
                            tid = det_to_tid.get(id(d))
                            if tid is not None:
                                entry = cfg_locks.get(tid, {}).get(
                                    ev.violated_limit_id
                                )
                                if (
                                    entry is not None
                                    and entry["verdict"] == "pass"
                                ):
                                    continue
                            filtered.append(d)
                        if not filtered:
                            continue
                        ev.violating_detections = filtered
                    else:
                        ev.violating_detections = gated
                    results.append(ev)
                    for d in ev.violating_detections:
                        tid = det_to_tid.get(id(d))
                        if tid is not None:
                            emitted_violations.add((tid, ev.violated_limit_id))

        # Sticky fail re-emission: for any locked-fail (tracker, limit) that
        # the live evaluator didn't already flag, re-emit a synthetic
        # violation on the tracker's current detection. Runs in both modes:
        # pessimistic locks are written during dwell; optimistic locks are
        # promoted from pending on clean zone exit. Pass-locks (verdict=pass)
        # are filtered below and never re-emit.
        sticky: dict[tuple[str, str], dict] = {}
        for tid, limit_locks in cfg_locks.items():
            det = tid_to_det.get(tid)
            if det is None:
                continue
            for limit_id, info in limit_locks.items():
                if info.get("verdict") != "fail":
                    continue
                if info["test_case_id"] not in enabled_tc_ids:
                    continue
                if (tid, limit_id) in emitted_violations:
                    continue
                key = (info["test_case_id"], limit_id)
                entry = sticky.setdefault(
                    key,
                    {
                        "test_case_name": info["test_case_name"],
                        "limit_name": info["limit_name"],
                        "severity": info["severity"],
                        "target_label_id": info["target_label_id"],
                        "dets": [],
                    },
                )
                entry["dets"].append(det)
        for (tc_id, limit_id), entry in sticky.items():
            if entry["severity"] is None:
                continue
            sticky_limit_def = limit_defs_by_id.get(limit_id)
            sticky_has_parent = (
                sticky_limit_def is not None
                and sticky_limit_def.targetParentLabel is not None
            )
            results.append(
                EvaluationResult(
                    test_case_id=tc_id,
                    test_case_name=entry["test_case_name"],
                    violated_limit_id=limit_id,
                    violated_limit_name=entry["limit_name"],
                    violated_limit_severity=entry["severity"],
                    violated_limit_target_label_id=entry["target_label_id"],
                    violating_detections=[] if sticky_has_parent else entry["dets"],
                    violating_parents=entry["dets"] if sticky_has_parent else [],
                )
            )

        return results, zr.tracking_ids, zr.display_ids
