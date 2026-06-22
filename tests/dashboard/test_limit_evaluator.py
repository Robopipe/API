from robopipe_api.dashboard.evaluators import LimitEvaluator
from robopipe_api.models.dashboard.eval_models import (
    EvalLimitItemEdge,
    EvalLimitItemOperator,
    EvalLimitItemParameter,
)

from .conftest import (
    LABELS,
    LABEL_DEFECT,
    LABEL_CONTAINER,
    make_config,
    make_detection,
    make_limit,
    make_limit_item,
)


class TestLimitEvaluatorTargetFiltering:
    def test_filters_by_target_label(self):
        limit = make_limit(
            target_label=LABEL_DEFECT,
            limit_items=[make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        detections = [
            make_detection(label=0),  # defect
            make_detection(label=0),  # defect
            make_detection(label=1),  # part (different label)
        ]
        # Count of defects = 2, within 1-5
        lr = evaluator.evaluate(detections, detections)
        assert lr.is_satisfied is True

    def test_filters_by_parent_label(self):
        limit = make_limit(
            target_label=LABEL_DEFECT,
            target_parent_label=LABEL_CONTAINER,
            limit_items=[make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        detections = [
            # Container bbox
            make_detection(label=2, coords=(0.0, 0.0, 0.6, 0.6)),
            # Defect inside container (center 0.25, 0.25 is within container)
            make_detection(label=0, coords=(0.1, 0.1, 0.4, 0.4)),
            # Defect outside container (center 0.85, 0.85)
            make_detection(label=0, coords=(0.7, 0.7, 1.0, 1.0)),
        ]
        # Only 1 defect inside the container → count=1, within 1-5
        lr = evaluator.evaluate(detections, detections)
        assert lr.is_satisfied is True

    def test_no_targets_found(self):
        limit = make_limit(
            target_label=LABEL_DEFECT,
            limit_items=[make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        detections = [make_detection(label=1)]  # only parts, no defects
        # count=0, outside 1-5
        lr = evaluator.evaluate(detections, detections)
        assert lr.is_satisfied is False


class TestLimitEvaluatorItemCombination:
    def test_single_item(self):
        limit = make_limit(
            limit_items=[make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        detections = [make_detection(label=0) for _ in range(3)]
        lr = evaluator.evaluate(detections, detections)
        assert lr.is_satisfied is True

    def test_two_items_and_both_true(self):
        # COUNT(1-5) AND POS_LEFT(30-70)
        limit = make_limit(
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5,
                    operator=EvalLimitItemOperator.AND, item_id="li-1",
                ),
                make_limit_item(
                    EvalLimitItemParameter.POSITION, limit_from=30, limit_to=70,
                    item_id="li-2", parent_edge=EvalLimitItemEdge.LEFT,
                ),
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        # 2 detections, both at ~40% from left
        detections = [
            make_detection(label=0, coords=(0.3, 0.3, 0.5, 0.5)),  # cx=0.4
            make_detection(label=0, coords=(0.35, 0.3, 0.55, 0.5)),  # cx=0.45
        ]
        lr = evaluator.evaluate(detections, detections)
        assert lr.is_satisfied is True

    def test_two_items_and_one_false(self):
        # COUNT(5-10) AND POS_LEFT(30-70) — count=2 is outside 5-10
        limit = make_limit(
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.COUNT, limit_from=5, limit_to=10,
                    operator=EvalLimitItemOperator.AND, item_id="li-1",
                ),
                make_limit_item(
                    EvalLimitItemParameter.POSITION, limit_from=30, limit_to=70,
                    item_id="li-2", parent_edge=EvalLimitItemEdge.LEFT,
                ),
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        detections = [
            make_detection(label=0, coords=(0.3, 0.3, 0.5, 0.5)),
            make_detection(label=0, coords=(0.35, 0.3, 0.55, 0.5)),
        ]
        # False AND True → False
        lr = evaluator.evaluate(detections, detections)
        assert lr.is_satisfied is False

    def test_two_items_or_one_true(self):
        # COUNT(5-10) OR POS_LEFT(30-70) — count fails but pos passes
        limit = make_limit(
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.COUNT, limit_from=5, limit_to=10,
                    operator=EvalLimitItemOperator.OR, item_id="li-1",
                ),
                make_limit_item(
                    EvalLimitItemParameter.POSITION, limit_from=30, limit_to=70,
                    item_id="li-2", parent_edge=EvalLimitItemEdge.LEFT,
                ),
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        detections = [
            make_detection(label=0, coords=(0.3, 0.3, 0.5, 0.5)),
        ]
        # False OR True → True
        lr = evaluator.evaluate(detections, detections)
        assert lr.is_satisfied is True

    def test_three_items_mixed_operators(self):
        # COUNT(1-5) AND POS_LEFT(30-70) OR AREA(0-100)
        # Evaluation: (COUNT AND POS_LEFT) OR AREA — left-to-right
        limit = make_limit(
            limit_items=[
                make_limit_item(
                    EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5,
                    operator=EvalLimitItemOperator.AND, item_id="li-1",
                ),
                make_limit_item(
                    EvalLimitItemParameter.POSITION, limit_from=80, limit_to=100,
                    operator=EvalLimitItemOperator.OR, item_id="li-2",
                    parent_edge=EvalLimitItemEdge.LEFT,
                ),
                make_limit_item(
                    EvalLimitItemParameter.AREA, limit_from=0, limit_to=100,
                    item_id="li-3",
                ),
            ],
        )
        config = make_config()
        evaluator = LimitEvaluator(limit, config)

        detections = [make_detection(label=0, coords=(0.3, 0.3, 0.5, 0.5))]
        # COUNT: 1 in 1-5 → True
        # POS_LEFT: 40% not in 80-100 → False
        # AREA: always True (0-100)
        # True AND False = False, False OR True = True
        lr = evaluator.evaluate(detections, detections)
        assert lr.is_satisfied is True

    def test_empty_limit_items(self):
        limit = make_limit(limit_items=[])
        config = make_config()
        evaluator = LimitEvaluator(limit, config)
        lr = evaluator.evaluate([make_detection(label=0)], [make_detection(label=0)])
        assert lr.is_satisfied is True
