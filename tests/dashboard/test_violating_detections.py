"""Tests for per-detection violation tracking (the bug fix).

Verifies that only the specific detections that violated a limit are marked,
not all detections of the same label type.
"""

from robopipe_api.dashboard.evaluators import (
    LimitItemEvaluator,
    LimitEvaluator,
    TestCaseEvaluator,
)
from robopipe_api.dashboard.dashboard_handler import _annotate_detections
from robopipe_api.models.dashboard.eval_models import (
    EvalLimitItemParameter,
    EvalLimitItemQuantifierType,
    EvalSeverity,
    EvalTestCaseType,
)

from .conftest import (
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
            EvalLimitItemParameter.POS_LEFT, limit_from=30, limit_to=50
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
