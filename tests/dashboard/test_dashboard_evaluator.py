from robopipe_api.dashboard.evaluators import DashboardEvaluator
from robopipe_api.dashboard.line_crossing import LineCrossingTracker
from robopipe_api.dashboard.threshold_tracker import ThresholdTracker
from robopipe_api.models.dashboard.eval_models import (
    EvalLimitItemParameter,
    EvalLogicOperatorValue,
    EvalTestCaseType,
    EvalSeverity,
)
from robopipe_api.models.dashboard.dashboard_config import DashboardLineFlow

from .conftest import (
    make_config,
    make_detection,
    make_limit,
    make_limit_item,
    make_test_case,
    limit_node,
    operator_node,
)

SESSION_ID = 1


class TestDashboardEvaluator:
    def _make_evaluator(self):
        tracker = LineCrossingTracker()
        threshold_tracker = ThresholdTracker()
        return DashboardEvaluator(tracker, threshold_tracker)

    def test_no_crossings_count_still_evaluated(self):
        evaluator = self._make_evaluator()
        tc = make_test_case(
            limits=[make_limit(limit_items=[
                make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5),
            ])],
        )
        config = make_config(
            test_cases=[tc],
            line_flow=DashboardLineFlow.POSITIVE,
        )

        # Detection before line → no crossings, but COUNT uses all_detections
        # count=1 in 1-5 → DEFECT condition met → violated
        detections = [make_detection(label=0, coords=(0.4, 0.2, 0.6, 0.4))]
        result, _, _ = evaluator.evaluate(config, detections, SESSION_ID)
        assert len(result) == 1
        assert result[0].test_case_id == "tc-1"

    def test_crossing_with_violation(self):
        evaluator = self._make_evaluator()
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            severity=EvalSeverity.ALERT,
            limits=[make_limit(limit_items=[
                make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5),
            ])],
        )
        config = make_config(test_cases=[tc], line_flow=DashboardLineFlow.POSITIVE)

        # Detection past line
        detections = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]
        result, _, _ = evaluator.evaluate(config, detections, SESSION_ID)
        assert len(result) == 1
        assert result[0].test_case_id == "tc-1"

    def test_crossing_without_violation(self):
        evaluator = self._make_evaluator()
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            limits=[make_limit(limit_items=[
                make_limit_item(EvalLimitItemParameter.COUNT, limit_from=5, limit_to=10),
            ])],
        )
        config = make_config(test_cases=[tc], line_flow=DashboardLineFlow.POSITIVE)

        # 1 detection past line, but count=1 outside 5-10 → DEFECT not triggered
        detections = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]
        result, _, _ = evaluator.evaluate(config, detections, SESSION_ID)
        assert len(result) == 0

    def test_multiple_test_cases(self):
        evaluator = self._make_evaluator()
        tc_defect = make_test_case(
            tc_id="tc-defect",
            tc_type=EvalTestCaseType.DEFECT,
            severity=EvalSeverity.ALERT,
            limits=[make_limit(
                limit_id="lim-1",
                limit_items=[make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)],
            )],
        )
        tc_check = make_test_case(
            tc_id="tc-check",
            tc_type=EvalTestCaseType.CHECK,
            severity=EvalSeverity.WARNING,
            limits=[make_limit(
                limit_id="lim-2",
                limit_items=[make_limit_item(EvalLimitItemParameter.COUNT, limit_from=5, limit_to=10)],
            )],
        )
        config = make_config(test_cases=[tc_defect, tc_check])

        # 2 detections past line
        detections = [
            make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8)),
            make_detection(label=0, coords=(0.3, 0.7, 0.5, 0.9)),
        ]
        result, _, _ = evaluator.evaluate(config, detections, SESSION_ID)
        ids = {r.test_case_id for r in result}

        # tc_defect: count=2 in 1-5 → True → violated
        assert "tc-defect" in ids
        # tc_check: count=2 not in 5-10 → False → NOT False → violated
        assert "tc-check" in ids

    def test_empty_test_cases(self):
        evaluator = self._make_evaluator()
        config = make_config(test_cases=[])

        detections = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]
        result, _, _ = evaluator.evaluate(config, detections, SESSION_ID)
        assert len(result) == 0

    def test_complex_logic_tree_end_to_end(self):
        evaluator = self._make_evaluator()

        # Two limits: count check and positional check
        # Logic: count_limit OR pos_limit
        count_limit = make_limit(
            limit_id="lim-count",
            limit_items=[make_limit_item(EvalLimitItemParameter.COUNT, limit_from=5, limit_to=10)],
        )
        pos_limit = make_limit(
            limit_id="lim-pos",
            limit_items=[make_limit_item(EvalLimitItemParameter.POS_LEFT, limit_from=30, limit_to=70)],
        )
        tc = make_test_case(
            tc_type=EvalTestCaseType.DEFECT,
            severity=EvalSeverity.ALERT,
            limits=[count_limit, pos_limit],
            logic_nodes=[
                limit_node("lim-count"),
                operator_node(EvalLogicOperatorValue.OR),
                limit_node("lim-pos"),
            ],
        )
        config = make_config(test_cases=[tc])

        # 1 detection past line at cx=0.4 (40% from left)
        # count=1 outside 5-10 → False
        # pos=40% in 30-70 → True
        # False OR True → True → DEFECT violated
        detections = [make_detection(label=0, coords=(0.3, 0.6, 0.5, 0.8))]
        result, _, _ = evaluator.evaluate(config, detections, SESSION_ID)
        assert len(result) >= 1
