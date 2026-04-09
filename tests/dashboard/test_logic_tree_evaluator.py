from robopipe_api.dashboard.evaluators import LogicTreeEvaluator
from robopipe_api.models.dashboard.eval_models import (
    EvalLimitItemParameter,
    EvalLogicOperatorValue,
)

from .conftest import (
    make_config,
    make_detection,
    make_limit,
    make_limit_item,
    make_test_case,
    limit_node,
    operator_node,
    group_node,
)


def _make_always_true_limit(limit_id: str = "lim-true"):
    """Limit that passes for any non-empty defect detections (COUNT >= 0)."""
    return make_limit(
        limit_id=limit_id,
        limit_items=[make_limit_item(EvalLimitItemParameter.COUNT, limit_from=0, limit_to=999)],
    )


def _make_always_false_limit(limit_id: str = "lim-false"):
    """Limit that never passes (COUNT must be negative)."""
    return make_limit(
        limit_id=limit_id,
        limit_items=[make_limit_item(EvalLimitItemParameter.COUNT, limit_from=999, limit_to=1000)],
    )


DETECTIONS = [make_detection(label=0)]


class TestDefaultAndBehavior:
    def test_empty_logic_nodes_ands_all_limits(self):
        tc = make_test_case(limits=[
            _make_always_true_limit("lim-1"),
            _make_always_true_limit("lim-2"),
        ])
        config = make_config()
        evaluator = LogicTreeEvaluator(tc, config)
        result, _, _ = evaluator.evaluate(DETECTIONS, DETECTIONS)
        assert result is True

    def test_empty_logic_nodes_one_false(self):
        tc = make_test_case(limits=[
            _make_always_true_limit("lim-1"),
            _make_always_false_limit("lim-2"),
        ])
        config = make_config()
        evaluator = LogicTreeEvaluator(tc, config)
        result, _, _ = evaluator.evaluate(DETECTIONS, DETECTIONS)
        assert result is False

    def test_no_limits_returns_true(self):
        tc = make_test_case(limits=[])
        config = make_config()
        evaluator = LogicTreeEvaluator(tc, config)
        result, _, _ = evaluator.evaluate(DETECTIONS, DETECTIONS)
        assert result is True


class TestExplicitLogicNodes:
    def test_single_limit_node(self):
        lim = _make_always_true_limit("lim-1")
        tc = make_test_case(
            limits=[lim],
            logic_nodes=[limit_node("lim-1")],
        )
        config = make_config()
        evaluator = LogicTreeEvaluator(tc, config)
        result, _, _ = evaluator.evaluate(DETECTIONS, DETECTIONS)
        assert result is True

    def test_and_operator(self):
        tc = make_test_case(
            limits=[_make_always_true_limit("lim-1"), _make_always_false_limit("lim-2")],
            logic_nodes=[
                limit_node("lim-1"),
                operator_node(EvalLogicOperatorValue.AND),
                limit_node("lim-2"),
            ],
        )
        config = make_config()
        evaluator = LogicTreeEvaluator(tc, config)
        # True AND False → False
        result, _, _ = evaluator.evaluate(DETECTIONS, DETECTIONS)
        assert result is False

    def test_or_operator(self):
        tc = make_test_case(
            limits=[_make_always_true_limit("lim-1"), _make_always_false_limit("lim-2")],
            logic_nodes=[
                limit_node("lim-1"),
                operator_node(EvalLogicOperatorValue.OR),
                limit_node("lim-2"),
            ],
        )
        config = make_config()
        evaluator = LogicTreeEvaluator(tc, config)
        # True OR False → True
        result, _, _ = evaluator.evaluate(DETECTIONS, DETECTIONS)
        assert result is True

    def test_not_operator(self):
        tc = make_test_case(
            limits=[_make_always_true_limit("lim-1")],
            logic_nodes=[
                operator_node(EvalLogicOperatorValue.NOT),
                limit_node("lim-1"),
            ],
        )
        config = make_config()
        evaluator = LogicTreeEvaluator(tc, config)
        # NOT True → False
        result, _, _ = evaluator.evaluate(DETECTIONS, DETECTIONS)
        assert result is False

    def test_not_false_becomes_true(self):
        tc = make_test_case(
            limits=[_make_always_false_limit("lim-1")],
            logic_nodes=[
                operator_node(EvalLogicOperatorValue.NOT),
                limit_node("lim-1"),
            ],
        )
        config = make_config()
        evaluator = LogicTreeEvaluator(tc, config)
        # NOT False → True
        result, _, _ = evaluator.evaluate(DETECTIONS, DETECTIONS)
        assert result is True


class TestGroupNodes:
    def test_simple_group(self):
        # True AND (NOT False) → True AND True → True
        tc = make_test_case(
            limits=[_make_always_true_limit("lim-1"), _make_always_false_limit("lim-2")],
            logic_nodes=[
                limit_node("lim-1"),
                operator_node(EvalLogicOperatorValue.AND),
                group_node([
                    operator_node(EvalLogicOperatorValue.NOT),
                    limit_node("lim-2"),
                ]),
            ],
        )
        config = make_config()
        evaluator = LogicTreeEvaluator(tc, config)
        result, _, _ = evaluator.evaluate(DETECTIONS, DETECTIONS)
        assert result is True

    def test_group_changes_evaluation_order(self):
        # Without group: True OR False AND False → (True OR False) AND False → False
        # With group:    True OR (False AND False) → True OR False → True
        tc_no_group = make_test_case(
            limits=[
                _make_always_true_limit("lim-1"),
                _make_always_false_limit("lim-2"),
                _make_always_false_limit("lim-3"),
            ],
            logic_nodes=[
                limit_node("lim-1"),
                operator_node(EvalLogicOperatorValue.OR),
                limit_node("lim-2"),
                operator_node(EvalLogicOperatorValue.AND),
                limit_node("lim-3"),
            ],
        )
        config = make_config()
        # Left-to-right: (True OR False) AND False → False
        result, _, _ = LogicTreeEvaluator(tc_no_group, config).evaluate(DETECTIONS, DETECTIONS)
        assert result is False

        tc_with_group = make_test_case(
            limits=[
                _make_always_true_limit("lim-1"),
                _make_always_false_limit("lim-2"),
                _make_always_false_limit("lim-3"),
            ],
            logic_nodes=[
                limit_node("lim-1"),
                operator_node(EvalLogicOperatorValue.OR),
                group_node([
                    limit_node("lim-2"),
                    operator_node(EvalLogicOperatorValue.AND),
                    limit_node("lim-3"),
                ]),
            ],
        )
        # True OR (False AND False) → True OR False → True
        result, _, _ = LogicTreeEvaluator(tc_with_group, config).evaluate(DETECTIONS, DETECTIONS)
        assert result is True

    def test_nested_groups(self):
        # NOT (True AND (NOT False))
        # = NOT (True AND True) = NOT True = False
        tc = make_test_case(
            limits=[_make_always_true_limit("lim-1"), _make_always_false_limit("lim-2")],
            logic_nodes=[
                operator_node(EvalLogicOperatorValue.NOT),
                group_node([
                    limit_node("lim-1"),
                    operator_node(EvalLogicOperatorValue.AND),
                    group_node([
                        operator_node(EvalLogicOperatorValue.NOT),
                        limit_node("lim-2"),
                    ]),
                ]),
            ],
        )
        config = make_config()
        result, _, _ = LogicTreeEvaluator(tc, config).evaluate(DETECTIONS, DETECTIONS)
        assert result is False

    def test_missing_limit_reference_evaluates_to_false(self):
        tc = make_test_case(
            limits=[_make_always_true_limit("lim-1")],
            logic_nodes=[limit_node("nonexistent")],
        )
        config = make_config()
        evaluator = LogicTreeEvaluator(tc, config)
        result, _, _ = evaluator.evaluate(DETECTIONS, DETECTIONS)
        assert result is False
