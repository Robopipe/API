"""Tests for per-detection violation tracking (the bug fix).

Verifies that only the specific detections that violated a limit are marked,
not all detections of the same label type.
"""

from robopipe_api.dashboard.evaluators import (
    DashboardEvaluator,
    LimitItemEvaluator,
    LimitEvaluator,
    TestCaseEvaluator,
    _aggregate_limit_value,
)
from robopipe_api.dashboard.dashboard_handler import _annotate_detections
from robopipe_api.models.dashboard.eval_models import (
    EvalLimitItemEdge,
    EvalLimitItemOperator,
    EvalLimitItemParameter,
    EvalLimitItemQuantifierType,
    EvalLimitItemQuantifierUnit,
    EvalSeverity,
    EvalTestCaseType,
)

from .conftest import (
    LABEL_CONTAINER,
    LABEL_DEFECT,
    make_config,
    make_detection,
    make_limit,
    make_limit_item,
    make_test_case,
    limit_node,
)


class TestLimitItemViolatingDetections:
    """LimitItemEvaluator returns per-detection satisfying/non_satisfying lists."""

    def test_area_splits_satisfying_and_non_satisfying(self):
        item = make_limit_item(EvalLimitItemParameter.AREA, limit_from=20, limit_to=30)
        evaluator = LimitItemEvaluator(item)
        d_in = make_detection(coords=(0.0, 0.0, 0.5, 0.5))  # area=25%
        d_out = make_detection(coords=(0.0, 0.0, 0.8, 0.8))  # area=64%
        _, _, satisfying, non_satisfying = evaluator.evaluate(
            [d_in, d_out], [d_in, d_out], None
        )
        assert d_in in satisfying
        assert d_out in non_satisfying
        assert d_in not in non_satisfying
        assert d_out not in satisfying

    def test_positional_splits_satisfying_and_non_satisfying(self):
        item = make_limit_item(
            EvalLimitItemParameter.POSITION, limit_from=30, limit_to=50,
            parent_edge=EvalLimitItemEdge.LEFT,
        )
        evaluator = LimitItemEvaluator(item)
        d_in = make_detection(coords=(0.3, 0.3, 0.5, 0.5))  # cx=0.4 → 40%
        d_out = make_detection(coords=(0.5, 0.3, 0.7, 0.5))  # cx=0.6 → 60%
        _, _, satisfying, non_satisfying = evaluator.evaluate(
            [d_in, d_out], [d_in, d_out], None
        )
        assert d_in in satisfying
        assert d_out in non_satisfying

    def test_count_returns_empty_detection_lists(self):
        item = make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection() for _ in range(3)]
        _, _, satisfying, non_satisfying = evaluator.evaluate(targets, targets, None)
        assert satisfying == []
        assert non_satisfying == []

    def test_empty_targets_returns_empty_lists(self):
        item = make_limit_item(EvalLimitItemParameter.AREA, limit_from=0, limit_to=100)
        evaluator = LimitItemEvaluator(item)
        _, _, satisfying, non_satisfying = evaluator.evaluate([], [], None)
        assert satisfying == []
        assert non_satisfying == []


class TestLimitResultDetections:
    """LimitEvaluator.evaluate() returns LimitResult with detection breakdown."""

    def test_area_limit_tracks_satisfying_detections(self):
        limit = make_limit(
            target_label=LABEL_DEFECT,
            limit_items=[
                make_limit_item(EvalLimitItemParameter.AREA, limit_from=20, limit_to=30)
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        d_in = make_detection(label=0, coords=(0.0, 0.0, 0.5, 0.5))  # 25%
        d_out = make_detection(label=0, coords=(0.0, 0.0, 0.8, 0.8))  # 64%
        lr = evaluator.evaluate([d_in, d_out], [d_in, d_out])

        assert d_in in lr.satisfying
        assert d_out in lr.non_satisfying

    def test_count_limit_populates_all_targets(self):
        limit = make_limit(
            target_label=LABEL_DEFECT,
            limit_items=[
                make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        d1 = make_detection(label=0)
        d2 = make_detection(label=0)
        lr = evaluator.evaluate([d1, d2], [d1, d2])

        assert lr.satisfying == []
        assert lr.non_satisfying == []
        assert d1 in lr.all_targets
        assert d2 in lr.all_targets

    def test_parent_label_count_populates_satisfying_parents(self):
        """Parent-label COUNT with a satisfying parent: per-parent lists track
        which parent/children matched. Used by DEFECT highlighting."""
        limit = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[
                make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        parent = make_detection(label=2, coords=(0.1, 0.1, 0.9, 0.9))
        child = make_detection(label=0, coords=(0.4, 0.4, 0.5, 0.5))
        lr = evaluator.evaluate([parent, child], [parent, child])

        assert lr.is_satisfied is True
        assert lr.satisfying_parents == [parent]
        assert lr.satisfying_children == [child]
        # CHECK-side lists stay empty when the parent satisfies.
        assert lr.all_targets == []

    def test_parent_label_count_failing_parent_populates_violating(self):
        """Parent-label COUNT with a failing parent: violating lists track it.
        Regression check that CHECK semantics still work after the DEFECT fix."""
        limit = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[
                make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        parent = make_detection(label=2, coords=(0.1, 0.1, 0.9, 0.9))
        lr = evaluator.evaluate([parent], [parent])

        assert lr.is_satisfied is False
        assert parent in lr.all_targets
        # DEFECT-side lists stay empty when the parent fails.
        assert lr.satisfying_parents == []
        assert lr.satisfying_children == []

    def test_parent_label_multi_item_does_not_leak_across_parents(self):
        """Multi-item AND with parent-label: per-detection lists must respect
        each parent's own verdict. A passing parent's children that failed an
        individual item (but whose siblings carried the quantifier) must not
        appear in `lr.non_satisfying`; a failing parent's children that
        satisfied an individual item must not appear in `lr.satisfying`."""
        limit = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.POSITION,
                    limit_from=0, limit_to=50,
                    quantifier_type=EvalLimitItemQuantifierType.MIN,
                    quantifier_unit=EvalLimitItemQuantifierUnit.PCS,
                    quantifier_value=1,
                    operator=EvalLimitItemOperator.AND,
                    item_id="li-1",
                    parent_edge=EvalLimitItemEdge.LEFT,
                ),
                make_limit_item(
                    EvalLimitItemParameter.POSITION,
                    limit_from=0, limit_to=50,
                    quantifier_type=EvalLimitItemQuantifierType.MIN,
                    quantifier_unit=EvalLimitItemQuantifierUnit.PCS,
                    quantifier_value=1,
                    item_id="li-2",
                    parent_edge=EvalLimitItemEdge.TOP,
                ),
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        # Passing parent on the left half. One child in the top-left quadrant
        # (satisfies both items); one in the bottom-right quadrant (fails both
        # but the parent still passes thanks to its sibling).
        passing_parent = make_detection(label=2, coords=(0.0, 0.0, 0.5, 1.0))
        good_child = make_detection(label=0, coords=(0.05, 0.15, 0.15, 0.25))
        bad_sibling = make_detection(label=0, coords=(0.35, 0.75, 0.45, 0.85))

        # Failing parent on the right half. Its only child sits in the
        # bottom-right quadrant → both quantifiers fail.
        failing_parent = make_detection(label=2, coords=(0.5, 0.0, 1.0, 1.0))
        failing_child = make_detection(label=0, coords=(0.85, 0.75, 0.95, 0.85))

        dets = [
            passing_parent, good_child, bad_sibling,
            failing_parent, failing_child,
        ]
        lr = evaluator.evaluate(dets, dets)

        assert lr.is_satisfied is False  # at least one parent failed
        assert passing_parent in lr.satisfying_parents
        assert failing_parent in lr.all_targets

        # The passing parent's "bad" sibling must NOT leak into non_satisfying.
        assert good_child in lr.satisfying
        assert bad_sibling not in lr.non_satisfying
        assert bad_sibling not in lr.satisfying

        # The failing parent's child belongs in non_satisfying, not satisfying.
        assert failing_child in lr.non_satisfying
        assert failing_child not in lr.satisfying


class TestReduceVerdict:
    """DashboardEvaluator._reduce_verdict aligns optimistic semantics with the
    test case type: any clean frame in the dwell forgives the verdict, whether
    CHECK (clean = limit satisfied) or DEFECT (clean = limit NOT satisfied)."""

    def _evaluator(self):
        # _reduce_verdict is pure — the tracker args are unused.
        return DashboardEvaluator(zone_tracker=None, threshold_tracker=None)

    def test_check_optimistic_any_satisfied_frame_wins(self):
        ev = self._evaluator()
        assert ev._reduce_verdict(
            {"pass": 1, "fail": 9}, optimistic=True, is_check=True
        ) is True
        assert ev._reduce_verdict(
            {"pass": 0, "fail": 5}, optimistic=True, is_check=True
        ) is False

    def test_check_pessimistic_requires_all_satisfied(self):
        ev = self._evaluator()
        assert ev._reduce_verdict(
            {"pass": 5, "fail": 0}, optimistic=False, is_check=True
        ) is True
        assert ev._reduce_verdict(
            {"pass": 5, "fail": 1}, optimistic=False, is_check=True
        ) is False

    def test_defect_optimistic_any_clean_frame_forgives(self):
        """The user's repro: 1 false-negative frame on COUNT defect must
        commit the dwell as passed under optimistic flag."""
        ev = self._evaluator()
        # 9 defective frames, 1 clean frame → optimistic forgives.
        assert ev._reduce_verdict(
            {"pass": 9, "fail": 1}, optimistic=True, is_check=False
        ) is False
        # No clean frames → defect overall.
        assert ev._reduce_verdict(
            {"pass": 9, "fail": 0}, optimistic=True, is_check=False
        ) is True

    def test_defect_pessimistic_any_defective_frame_violates(self):
        ev = self._evaluator()
        assert ev._reduce_verdict(
            {"pass": 1, "fail": 9}, optimistic=False, is_check=False
        ) is True
        assert ev._reduce_verdict(
            {"pass": 0, "fail": 5}, optimistic=False, is_check=False
        ) is False

    def test_empty_samples_return_none(self):
        ev = self._evaluator()
        assert ev._reduce_verdict(
            {"pass": 0, "fail": 0}, optimistic=True, is_check=True
        ) is None
        assert ev._reduce_verdict(
            {"pass": 0, "fail": 0}, optimistic=False, is_check=False
        ) is None


class TestAggregateLimitValue:
    """_aggregate_limit_value picks per-test-case semantics so the lock loop
    and the live-overlay filter agree on which parents are defective."""

    def test_defect_parent_label_uses_or(self):
        """Two parents, one defective + one clean: DEFECT aggregate is True so
        the lock loop knows to compute failing_ids and the defective parent
        avoids a pass-lock. Without OR-aggregation, the AND in lr.is_satisfied
        would silence the defective parent's highlight on later frames."""
        limit = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.COUNT, limit_from=1, limit_to=None
                )
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        defective_parent = make_detection(label=2, coords=(0.0, 0.0, 0.4, 1.0))
        child = make_detection(label=0, coords=(0.1, 0.4, 0.3, 0.6))
        clean_parent = make_detection(label=2, coords=(0.6, 0.0, 1.0, 1.0))
        lr = evaluator.evaluate(
            [defective_parent, child, clean_parent],
            [defective_parent, child, clean_parent],
        )

        assert lr.is_satisfied is False  # AND across parents
        assert _aggregate_limit_value(lr, EvalTestCaseType.DEFECT) is True
        assert _aggregate_limit_value(lr, EvalTestCaseType.CHECK) is False

    def test_no_parent_verdicts_falls_through(self):
        """Flat limits (no parent_verdicts) keep using lr.is_satisfied."""
        limit = make_limit(
            target_label=LABEL_DEFECT,
            limit_items=[
                make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        d = make_detection(label=0)
        lr = evaluator.evaluate([d], [d])

        assert lr.parent_verdicts is None
        assert _aggregate_limit_value(lr, EvalTestCaseType.DEFECT) == lr.is_satisfied
        assert _aggregate_limit_value(lr, EvalTestCaseType.CHECK) == lr.is_satisfied


class TestEvaluationResultViolatingDetections:
    """TestCaseEvaluator.evaluate() populates violating_detections correctly."""

    def test_check_area_only_non_satisfying_are_violating(self):
        """CHECK + AREA: only detections outside the range should be marked."""
        lim = make_limit(
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.AREA,
                    limit_from=20,
                    limit_to=30,
                    quantifier_type=EvalLimitItemQuantifierType.EXACT,
                    quantifier_value=100,
                )
            ],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[lim],
            logic_nodes=[limit_node(lim.id)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        d_good = make_detection(label=0, coords=(0.0, 0.0, 0.5, 0.5))  # 25% in range
        d_bad = make_detection(label=0, coords=(0.0, 0.0, 0.8, 0.8))  # 64% out of range

        results = evaluator.evaluate([d_good, d_bad], [d_good, d_bad])
        assert len(results) == 1
        # CHECK: non_satisfying detections are the violators
        assert d_bad in results[0].violating_detections
        assert d_good not in results[0].violating_detections

    def test_defect_area_only_satisfying_are_violating(self):
        """DEFECT + AREA: only detections matching the defect condition should be marked."""
        lim = make_limit(
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.AREA,
                    limit_from=20,
                    limit_to=30,
                    quantifier_type=EvalLimitItemQuantifierType.EXACT,
                    quantifier_value=100,
                )
            ],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[lim],
            logic_nodes=[limit_node(lim.id)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        d1 = make_detection(label=0, coords=(0.0, 0.0, 0.5, 0.5))  # 25% in range
        d2 = make_detection(label=0, coords=(0.0, 0.0, 0.5, 0.4))  # 20% in range

        results = evaluator.evaluate([d1, d2], [d1, d2])
        assert len(results) == 1
        # DEFECT: satisfying detections are the defects
        assert d1 in results[0].violating_detections
        assert d2 in results[0].violating_detections

    def test_count_violation_includes_all_targets(self):
        """COUNT violation: all targets are included (aggregate check)."""
        lim = make_limit(
            limit_items=[
                make_limit_item(EvalLimitItemParameter.COUNT, limit_from=5, limit_to=10)
            ],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[lim],
            logic_nodes=[limit_node(lim.id)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        detections = [make_detection(label=0) for _ in range(2)]
        # count=2 outside 5-10 → CHECK violated
        results = evaluator.evaluate(detections, detections)
        assert len(results) == 1
        # COUNT has no per-detection split, falls back to all_targets
        assert len(results[0].violating_detections) == 2

    def test_defect_parent_label_count_flags_parent_only(self):
        """DEFECT + parent-label COUNT (limitFrom=1): the defective parent is
        the highlighted unit. The child inside it is NOT in violating_detections
        — COUNT has no per-child verdict so only the parent gets the alert
        border in the live overlay."""
        lim = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.COUNT, limit_from=1, limit_to=None
                )
            ],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[lim],
            logic_nodes=[limit_node(lim.id)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        parent = make_detection(label=2, coords=(0.1, 0.1, 0.9, 0.9))
        child = make_detection(label=0, coords=(0.4, 0.4, 0.5, 0.5))

        results = evaluator.evaluate([parent, child], [parent, child])
        assert len(results) == 1
        assert parent in results[0].violating_detections
        assert child not in results[0].violating_detections

    def test_defect_parent_label_per_parent_isolation(self):
        """DEFECT + parent-label COUNT with one defective and one clean parent:
        the test case must fire and flag only the defective parent. Without
        per-parent OR aggregation, the clean parent's AND-style verdict would
        suppress the violation entirely."""
        lim = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.COUNT, limit_from=1, limit_to=None
                )
            ],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[lim],
            logic_nodes=[limit_node(lim.id)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        defective_parent = make_detection(label=2, coords=(0.0, 0.0, 0.4, 1.0))
        child = make_detection(label=0, coords=(0.1, 0.4, 0.3, 0.6))
        clean_parent = make_detection(label=2, coords=(0.6, 0.0, 1.0, 1.0))

        results = evaluator.evaluate(
            [defective_parent, child, clean_parent],
            [defective_parent, child, clean_parent],
        )
        assert len(results) == 1
        violating = results[0].violating_detections
        assert defective_parent in violating
        assert clean_parent not in violating
        assert child not in violating

    def test_defect_parent_label_area_flags_defective_children(self):
        """DEFECT + parent-label AREA: when the limit splits per child, the
        defective (satisfying) children are the highlighted units — mirrors
        CHECK + parent-label AREA which highlights non_satisfying children."""
        lim = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.AREA,
                    limit_from=0,
                    limit_to=50,
                    quantifier_type=EvalLimitItemQuantifierType.MIN,
                    quantifier_value=1,
                )
            ],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[lim],
            logic_nodes=[limit_node(lim.id)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        parent = make_detection(label=2, coords=(0.0, 0.0, 1.0, 1.0))
        # area within parent = (0.2*0.2)/1.0*100 = 4% → matches limit (0-50)
        defective_child = make_detection(label=0, coords=(0.4, 0.4, 0.6, 0.6))

        results = evaluator.evaluate(
            [parent, defective_child], [parent, defective_child]
        )
        assert len(results) == 1
        assert defective_child in results[0].violating_detections
        assert parent not in results[0].violating_detections

    def test_check_parent_label_count_flags_failing_parent(self):
        """CHECK + parent-label COUNT (limitFrom=1) regression: an empty
        parent fails the check, and only that parent is flagged."""
        lim = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.COUNT, limit_from=1, limit_to=None
                )
            ],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[lim],
            logic_nodes=[limit_node(lim.id)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        parent = make_detection(label=2, coords=(0.1, 0.1, 0.9, 0.9))

        results = evaluator.evaluate([parent], [parent])
        assert len(results) == 1
        assert parent in results[0].violating_detections

    def test_check_parent_label_multi_positional_isolates_failing_parent(self):
        """CHECK + parent-label with two positional MIN-1-PCS items joined by
        AND: when one parent fails the limit, only its child(ren) get
        highlighted. Children of a *passing* sibling parent that happen to be
        outside the positional ranges must not leak into the violation set
        — the quantifier was carried by a sibling and the parent itself is OK.
        """
        lim = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.POSITION,
                    limit_from=0, limit_to=50,
                    quantifier_type=EvalLimitItemQuantifierType.MIN,
                    quantifier_unit=EvalLimitItemQuantifierUnit.PCS,
                    quantifier_value=1,
                    operator=EvalLimitItemOperator.AND,
                    item_id="li-1",
                    parent_edge=EvalLimitItemEdge.LEFT,
                ),
                make_limit_item(
                    EvalLimitItemParameter.POSITION,
                    limit_from=0, limit_to=50,
                    quantifier_type=EvalLimitItemQuantifierType.MIN,
                    quantifier_unit=EvalLimitItemQuantifierUnit.PCS,
                    quantifier_value=1,
                    item_id="li-2",
                    parent_edge=EvalLimitItemEdge.TOP,
                ),
            ],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[lim],
            logic_nodes=[limit_node(lim.id)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        passing_parent = make_detection(label=2, coords=(0.0, 0.0, 0.5, 1.0))
        # Top-left quadrant child: POS_LEFT ≈ 20%, POS_TOP ≈ 20% → in range.
        good_child = make_detection(label=0, coords=(0.05, 0.15, 0.15, 0.25))
        # Bottom-right quadrant child: POS_LEFT ≈ 80%, POS_TOP ≈ 80% → out.
        bad_sibling = make_detection(label=0, coords=(0.35, 0.75, 0.45, 0.85))

        failing_parent = make_detection(label=2, coords=(0.5, 0.0, 1.0, 1.0))
        # Bottom-right of its parent → both quantifiers fail for this parent.
        failing_child = make_detection(label=0, coords=(0.85, 0.75, 0.95, 0.85))

        dets = [
            passing_parent, good_child, bad_sibling,
            failing_parent, failing_child,
        ]
        results = evaluator.evaluate(dets, dets)
        assert len(results) == 1
        violating = results[0].violating_detections
        assert failing_child in violating
        # Pre-fix bug: bad_sibling (in a passing parent) was incorrectly flagged.
        assert bad_sibling not in violating
        assert good_child not in violating

    def test_defect_parent_label_multi_positional_isolates_defective_parent(self):
        """DEFECT-side mirror: with two positional MIN-1-PCS items joined by
        AND, a non-defective parent's per-item satisfying children must not
        leak into the defect highlight set. Only children of the parent
        whose group actually satisfied the combined limit are flagged."""
        lim = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.POSITION,
                    limit_from=0, limit_to=50,
                    quantifier_type=EvalLimitItemQuantifierType.MIN,
                    quantifier_unit=EvalLimitItemQuantifierUnit.PCS,
                    quantifier_value=1,
                    operator=EvalLimitItemOperator.AND,
                    item_id="li-1",
                    parent_edge=EvalLimitItemEdge.LEFT,
                ),
                make_limit_item(
                    EvalLimitItemParameter.POSITION,
                    limit_from=0, limit_to=50,
                    quantifier_type=EvalLimitItemQuantifierType.MIN,
                    quantifier_unit=EvalLimitItemQuantifierUnit.PCS,
                    quantifier_value=1,
                    item_id="li-2",
                    parent_edge=EvalLimitItemEdge.TOP,
                ),
            ],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[lim],
            logic_nodes=[limit_node(lim.id)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        # Defective parent: child sits in the top-left quadrant → both
        # quantifiers are satisfied, the limit fires, the parent is defective.
        defective_parent = make_detection(label=2, coords=(0.0, 0.0, 0.5, 1.0))
        defect_child = make_detection(label=0, coords=(0.05, 0.15, 0.15, 0.25))

        # Non-defective parent: its child satisfies POS_LEFT but not POS_TOP,
        # so the AND of MIN-1 quantifiers fails for this parent.
        clean_parent = make_detection(label=2, coords=(0.5, 0.0, 1.0, 1.0))
        clean_child = make_detection(label=0, coords=(0.55, 0.75, 0.65, 0.85))

        dets = [defective_parent, defect_child, clean_parent, clean_child]
        results = evaluator.evaluate(dets, dets)
        assert len(results) == 1
        violating = results[0].violating_detections
        assert defect_child in violating
        # Pre-fix bug: clean_child (in a non-defective parent, satisfied
        # POS_LEFT individually) was incorrectly flagged as a defect.
        assert clean_child not in violating

    def test_non_violated_returns_empty(self):
        """No violation → no results."""
        lim = make_limit(
            limit_items=[
                make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)
            ],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[lim],
            logic_nodes=[limit_node(lim.id)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        detections = [make_detection(label=0) for _ in range(3)]
        results = evaluator.evaluate(detections, detections)
        assert results == []


class TestAnnotateDetections:
    """_annotate_detections marks only specific violating detections."""

    def test_only_violating_detection_gets_annotation(self):
        """The core bug fix: 3 detections of same label, only 1 violates → only 1 annotated."""
        d_good1 = make_detection(label=0, coords=(0.0, 0.0, 0.5, 0.5))
        d_bad = make_detection(label=0, coords=(0.0, 0.0, 0.8, 0.8))
        d_good2 = make_detection(label=0, coords=(0.1, 0.1, 0.4, 0.4))
        source_detections = [d_good1, d_bad, d_good2]

        from robopipe_api.dashboard.evaluators import EvaluationResult

        ev = EvaluationResult(

            test_case_id="tc-1",
            test_case_name="Test",
            violated_limit_id="lim-1",
            violated_limit_name="Area check",
            violated_limit_severity="ALERT",
            violated_limit_target_label_id=1,
            violating_detections=[d_bad],
        )

        result = {
            "detections": [
                {"label": 0, "confidence": 0.9, "coords": list(d.coords)}
                for d in source_detections
            ]
        }

        _annotate_detections(result, [ev], source_detections)

        # Only index 1 (d_bad) should have violations
        assert "violations" not in result["detections"][0]
        assert "violations" in result["detections"][1]
        assert result["detections"][1]["violations"][0]["severity"] == "ALERT"
        assert "violations" not in result["detections"][2]

    def test_no_annotation_when_severity_is_none(self):
        d = make_detection(label=0)
        source = [d]

        from robopipe_api.dashboard.evaluators import EvaluationResult

        ev = EvaluationResult(

            test_case_id="tc-1",
            test_case_name="Test",
            violated_limit_id=None,
            violated_limit_name=None,
            violated_limit_severity=None,
            violated_limit_target_label_id=None,
            violating_detections=[d],
        )

        result = {"detections": [{"label": 0, "confidence": 0.9}]}
        _annotate_detections(result, [ev], source)
        assert "violations" not in result["detections"][0]

    def test_multiple_violations_on_same_detection(self):
        d = make_detection(label=0)
        source = [d]

        from robopipe_api.dashboard.evaluators import EvaluationResult

        ev1 = EvaluationResult(

            test_case_id="tc-1", test_case_name="Test 1",
            violated_limit_id="lim-1", violated_limit_name="Limit A",
            violated_limit_severity="ALERT", violated_limit_target_label_id=1,
            violating_detections=[d],
        )
        ev2 = EvaluationResult(

            test_case_id="tc-2", test_case_name="Test 2",
            violated_limit_id="lim-2", violated_limit_name="Limit B",
            violated_limit_severity="WARNING", violated_limit_target_label_id=1,
            violating_detections=[d],
        )

        result = {"detections": [{"label": 0, "confidence": 0.9}]}
        _annotate_detections(result, [ev1, ev2], source)
        assert len(result["detections"][0]["violations"]) == 2
