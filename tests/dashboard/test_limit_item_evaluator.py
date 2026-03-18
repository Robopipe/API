import pytest

from robopipe_api.dashboard.evaluators import LimitItemEvaluator
from robopipe_api.models.dashboard.eval_models import EvalLimitItemParameter

from .conftest import make_detection, make_limit_item


class TestCountEvaluation:
    def test_count_within_range(self):
        item = make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection() for _ in range(3)]
        assert evaluator.evaluate(targets, None, targets) is True

    def test_count_below_range(self):
        item = make_limit_item(EvalLimitItemParameter.COUNT, limit_from=5, limit_to=10)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection() for _ in range(2)]
        assert evaluator.evaluate(targets, None, targets) is False

    def test_count_above_range(self):
        item = make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=3)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection() for _ in range(5)]
        assert evaluator.evaluate(targets, None, targets) is False

    def test_count_zero_targets(self):
        item = make_limit_item(EvalLimitItemParameter.COUNT, limit_from=1, limit_to=5)
        evaluator = LimitItemEvaluator(item)
        assert evaluator.evaluate([], None, []) is False

    def test_count_zero_in_range(self):
        item = make_limit_item(EvalLimitItemParameter.COUNT, limit_from=0, limit_to=5)
        evaluator = LimitItemEvaluator(item)
        assert evaluator.evaluate([], None, []) is True

    def test_count_only_upper_bound(self):
        item = make_limit_item(EvalLimitItemParameter.COUNT, limit_to=3)
        evaluator = LimitItemEvaluator(item)
        assert evaluator.evaluate([], None, []) is True
        targets = [make_detection() for _ in range(5)]
        assert evaluator.evaluate(targets, None, targets) is False


class TestAreaEvaluation:
    def test_area_percentage_of_frame(self):
        # Detection: (0.0, 0.0, 0.5, 0.5) → area = 0.25 → 25% of frame
        item = make_limit_item(EvalLimitItemParameter.AREA, limit_from=20, limit_to=30)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection(coords=(0.0, 0.0, 0.5, 0.5))]
        assert evaluator.evaluate(targets, None, targets) is True

    def test_area_percentage_of_parent(self):
        # Parent: (0.0, 0.0, 1.0, 1.0) → area = 1.0
        # Target: (0.0, 0.0, 0.5, 0.5) → area = 0.25 → 25% of parent
        item = make_limit_item(EvalLimitItemParameter.AREA, limit_from=20, limit_to=30)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection(coords=(0.0, 0.0, 0.5, 0.5))]
        parents = [make_detection(label=2, coords=(0.0, 0.0, 1.0, 1.0))]
        assert evaluator.evaluate(targets, parents, targets + parents) is True

    def test_area_outside_range(self):
        # area = 0.25 → 25% → outside 50-100 range
        item = make_limit_item(EvalLimitItemParameter.AREA, limit_from=50, limit_to=100)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection(coords=(0.0, 0.0, 0.5, 0.5))]
        assert evaluator.evaluate(targets, None, targets) is False

    def test_area_multiple_targets_sum(self):
        # Two targets each 0.25 area → total 0.5 → 50%
        item = make_limit_item(EvalLimitItemParameter.AREA, limit_from=45, limit_to=55)
        evaluator = LimitItemEvaluator(item)
        targets = [
            make_detection(coords=(0.0, 0.0, 0.5, 0.5)),
            make_detection(coords=(0.5, 0.5, 1.0, 1.0)),
        ]
        assert evaluator.evaluate(targets, None, targets) is True

    def test_area_zero_parent_area(self):
        item = make_limit_item(EvalLimitItemParameter.AREA, limit_from=0, limit_to=100)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection(coords=(0.5, 0.5, 0.6, 0.6))]
        parents = [make_detection(label=2, coords=(0.5, 0.5, 0.5, 0.5))]  # zero area
        assert evaluator.evaluate(targets, parents, targets + parents) is True  # 0.0 in range


class TestPositionalEvaluation:
    def test_pos_left_all_in_range(self):
        # Detections at center x=0.4 and x=0.6 → POS_LEFT = 40% and 60%
        item = make_limit_item(EvalLimitItemParameter.POS_LEFT, limit_from=30, limit_to=70)
        evaluator = LimitItemEvaluator(item)
        targets = [
            make_detection(coords=(0.3, 0.3, 0.5, 0.5)),  # cx=0.4
            make_detection(coords=(0.5, 0.3, 0.7, 0.5)),  # cx=0.6
        ]
        assert evaluator.evaluate(targets, None, targets) is True

    def test_pos_left_one_outside_range(self):
        item = make_limit_item(EvalLimitItemParameter.POS_LEFT, limit_from=30, limit_to=50)
        evaluator = LimitItemEvaluator(item)
        targets = [
            make_detection(coords=(0.3, 0.3, 0.5, 0.5)),  # cx=0.4 → 40% ✓
            make_detection(coords=(0.5, 0.3, 0.7, 0.5)),  # cx=0.6 → 60% ✗
        ]
        # ALL must satisfy → False
        assert evaluator.evaluate(targets, None, targets) is False

    def test_positional_no_targets_returns_false(self):
        item = make_limit_item(EvalLimitItemParameter.POS_LEFT, limit_from=0, limit_to=100)
        evaluator = LimitItemEvaluator(item)
        assert evaluator.evaluate([], None, []) is False

    def test_positional_with_parent_reference(self):
        # Parent: (0.2, 0.2, 0.8, 0.8) → width=0.6
        # Detection center: (0.5, 0.5) → POS_LEFT = (0.5-0.2)/0.6*100 = 50%
        item = make_limit_item(EvalLimitItemParameter.POS_LEFT, limit_from=40, limit_to=60)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection(coords=(0.4, 0.4, 0.6, 0.6))]
        parents = [make_detection(label=2, coords=(0.2, 0.2, 0.8, 0.8))]
        assert evaluator.evaluate(targets, parents, targets + parents) is True

    def test_positional_not_in_any_parent(self):
        # Detection center (0.05, 0.05) is not inside parent (0.5, 0.5, 1.0, 1.0)
        # Falls back to full frame reference
        item = make_limit_item(EvalLimitItemParameter.POS_LEFT, limit_from=0, limit_to=10)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection(coords=(0.0, 0.0, 0.1, 0.1))]  # cx=0.05 → 5%
        parents = [make_detection(label=2, coords=(0.5, 0.5, 1.0, 1.0))]
        assert evaluator.evaluate(targets, parents, targets + parents) is True

    def test_pos_center(self):
        # Center at (0.5, 0.5) in full frame → 0% from center
        item = make_limit_item(EvalLimitItemParameter.POS_CENTER, limit_from=0, limit_to=10)
        evaluator = LimitItemEvaluator(item)
        targets = [make_detection(coords=(0.4, 0.4, 0.6, 0.6))]
        assert evaluator.evaluate(targets, None, targets) is True

    def test_pos_top_and_bottom(self):
        # center y=0.3 → POS_TOP=30%, POS_BOTTOM=70%
        item_top = make_limit_item(EvalLimitItemParameter.POS_TOP, limit_from=25, limit_to=35)
        item_bot = make_limit_item(EvalLimitItemParameter.POS_BOTTOM, limit_from=65, limit_to=75)
        targets = [make_detection(coords=(0.4, 0.2, 0.6, 0.4))]  # cy=0.3
        assert LimitItemEvaluator(item_top).evaluate(targets, None, targets) is True
        assert LimitItemEvaluator(item_bot).evaluate(targets, None, targets) is True
