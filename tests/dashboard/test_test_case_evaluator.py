from robopipe_api.dashboard.evaluators import TestCaseEvaluator
from robopipe_api.models.dashboard.eval_models import (
    EvalLimitItemParameter,
    EvalTestCaseType,
)

from .conftest import (
    make_config,
    make_detection,
    make_limit,
    make_limit_item,
    make_test_case,
)


def _count_limit(limit_from: float, limit_to: float, limit_id: str = "lim-1"):
    return make_limit(
        limit_id=limit_id,
        limit_items=[make_limit_item(EvalLimitItemParameter.COUNT, limit_from=limit_from, limit_to=limit_to)],
    )


class TestCheckSemantics:
    """CHECK: violated when the condition is NOT met (NOT of result)."""

    def test_check_passes_when_condition_met(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[_count_limit(1, 5)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        detections = [make_detection(label=0) for _ in range(3)]
        # Limit True → NOT True = False → no violation
        assert evaluator.is_violated(detections) is False

    def test_check_violated_when_condition_not_met(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[_count_limit(5, 10)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        detections = [make_detection(label=0) for _ in range(2)]
        # count=2 outside 5-10 → Limit False → NOT False = True → violated
        assert evaluator.is_violated(detections) is True

    def test_check_with_no_detections(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[_count_limit(1, 5)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        # count=0 outside 1-5 → Limit False → violated
        assert evaluator.is_violated([]) is True

    def test_check_no_detections_range_includes_zero(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[_count_limit(0, 5)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        # count=0 in 0-5 → Limit True → NOT True → not violated
        assert evaluator.is_violated([]) is False


class TestDefectSemantics:
    """DEFECT: violated when the condition IS met (result directly)."""

    def test_defect_violated_when_condition_met(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[_count_limit(1, 5)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        detections = [make_detection(label=0) for _ in range(3)]
        # Limit True → violated
        assert evaluator.is_violated(detections) is True

    def test_defect_passes_when_condition_not_met(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[_count_limit(5, 10)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        detections = [make_detection(label=0) for _ in range(2)]
        # Limit False → not violated
        assert evaluator.is_violated(detections) is False

    def test_defect_with_no_detections(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[_count_limit(1, 5)],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        # count=0 outside 1-5 → Limit False → not violated
        assert evaluator.is_violated([]) is False


class TestPositionalCheckDefect:
    """Verify CHECK/DEFECT with positional limit items."""

    def test_check_positional_all_in_range(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[make_limit(limit_items=[
                make_limit_item(EvalLimitItemParameter.POS_LEFT, limit_from=30, limit_to=70),
            ])],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        detections = [make_detection(label=0, coords=(0.3, 0.3, 0.5, 0.5))]  # cx=0.4 → 40%
        # All in range → True → NOT True → not violated
        assert evaluator.is_violated(detections) is False

    def test_check_positional_one_outside(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.CHECK,
            limits=[make_limit(limit_items=[
                make_limit_item(EvalLimitItemParameter.POS_LEFT, limit_from=30, limit_to=50),
            ])],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        detections = [
            make_detection(label=0, coords=(0.3, 0.3, 0.5, 0.5)),  # cx=0.4 → 40% ✓
            make_detection(label=0, coords=(0.5, 0.3, 0.7, 0.5)),  # cx=0.6 → 60% ✗
        ]
        # Not all in range → False → NOT False → violated
        assert evaluator.is_violated(detections) is True

    def test_defect_positional_all_in_range(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[make_limit(limit_items=[
                make_limit_item(EvalLimitItemParameter.POS_LEFT, limit_from=30, limit_to=70),
            ])],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        detections = [make_detection(label=0, coords=(0.3, 0.3, 0.5, 0.5))]
        # All in range → True → violated
        assert evaluator.is_violated(detections) is True

    def test_defect_positional_not_all_in_range(self):
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[make_limit(limit_items=[
                make_limit_item(EvalLimitItemParameter.POS_LEFT, limit_from=30, limit_to=50),
            ])],
        )
        config = make_config()
        evaluator = TestCaseEvaluator(tc, config)

        detections = [
            make_detection(label=0, coords=(0.3, 0.3, 0.5, 0.5)),  # 40% ✓
            make_detection(label=0, coords=(0.5, 0.3, 0.7, 0.5)),  # 60% ✗
        ]
        # Not all → False → not violated
        assert evaluator.is_violated(detections) is False
