from robopipe_api.dashboard.geometry import (
    bbox_area,
    bbox_center,
    is_within_bbox,
    compute_position_pct,
    value_within_limits,
)
from robopipe_api.models.dashboard.eval_models import EvalLimitItemParameter


class TestBboxArea:
    def test_unit_square(self):
        assert bbox_area((0.0, 0.0, 1.0, 1.0)) == 1.0

    def test_quarter(self):
        assert bbox_area((0.0, 0.0, 0.5, 0.5)) == 0.25

    def test_zero_width(self):
        assert bbox_area((0.5, 0.0, 0.5, 1.0)) == 0.0

    def test_inverted_coords_clamps_to_zero(self):
        assert bbox_area((0.8, 0.8, 0.2, 0.2)) == 0.0


class TestBboxCenter:
    def test_unit_square(self):
        assert bbox_center((0.0, 0.0, 1.0, 1.0)) == (0.5, 0.5)

    def test_offset_box(self):
        cx, cy = bbox_center((0.2, 0.4, 0.6, 0.8))
        assert cx == pytest.approx(0.4)
        assert cy == pytest.approx(0.6)


class TestIsWithinBbox:
    def test_center_inside(self):
        inner = (0.4, 0.4, 0.6, 0.6)  # center=(0.5, 0.5)
        outer = (0.0, 0.0, 1.0, 1.0)
        assert is_within_bbox(inner, outer) is True

    def test_center_outside(self):
        inner = (0.0, 0.0, 0.1, 0.1)  # center=(0.05, 0.05)
        outer = (0.5, 0.5, 1.0, 1.0)
        assert is_within_bbox(inner, outer) is False

    def test_center_on_edge(self):
        inner = (0.0, 0.0, 1.0, 1.0)  # center=(0.5, 0.5)
        outer = (0.0, 0.0, 0.5, 0.5)  # right/bottom edge at 0.5
        assert is_within_bbox(inner, outer) is True  # <= boundary


class TestComputePositionPct:
    FULL_FRAME = (0.0, 0.0, 1.0, 1.0)

    def test_pos_left_center(self):
        # center at (0.5, 0.5) in full frame → 50% from left
        pct = compute_position_pct(
            (0.4, 0.4, 0.6, 0.6), self.FULL_FRAME, EvalLimitItemParameter.POS_LEFT
        )
        assert pct == pytest.approx(50.0)

    def test_pos_right_center(self):
        pct = compute_position_pct(
            (0.4, 0.4, 0.6, 0.6), self.FULL_FRAME, EvalLimitItemParameter.POS_RIGHT
        )
        assert pct == pytest.approx(50.0)

    def test_pos_left_at_quarter(self):
        # center at (0.25, 0.5) → 25% from left
        pct = compute_position_pct(
            (0.15, 0.4, 0.35, 0.6), self.FULL_FRAME, EvalLimitItemParameter.POS_LEFT
        )
        assert pct == pytest.approx(25.0)

    def test_pos_right_at_quarter_from_right(self):
        # center at (0.75, 0.5) → 25% from right
        pct = compute_position_pct(
            (0.65, 0.4, 0.85, 0.6), self.FULL_FRAME, EvalLimitItemParameter.POS_RIGHT
        )
        assert pct == pytest.approx(25.0)

    def test_pos_top(self):
        # center at (0.5, 0.3) → 30% from top
        pct = compute_position_pct(
            (0.4, 0.2, 0.6, 0.4), self.FULL_FRAME, EvalLimitItemParameter.POS_TOP
        )
        assert pct == pytest.approx(30.0)

    def test_pos_bottom(self):
        # center at (0.5, 0.7) → 30% from bottom
        pct = compute_position_pct(
            (0.4, 0.6, 0.6, 0.8), self.FULL_FRAME, EvalLimitItemParameter.POS_BOTTOM
        )
        assert pct == pytest.approx(30.0)

    def test_pos_center_at_origin(self):
        # center at (0.5, 0.5) in full frame → 0% from center
        pct = compute_position_pct(
            (0.4, 0.4, 0.6, 0.6), self.FULL_FRAME, EvalLimitItemParameter.POS_CENTER
        )
        assert pct == pytest.approx(0.0)

    def test_pos_center_at_corner(self):
        # center at (1.0, 1.0) in full frame → 100% from center
        pct = compute_position_pct(
            (0.9, 0.9, 1.0, 1.0), self.FULL_FRAME, EvalLimitItemParameter.POS_CENTER
        )
        assert pct == pytest.approx(90.0)

    def test_within_parent_bbox(self):
        # Parent bbox: (0.2, 0.2, 0.8, 0.8) → width/height = 0.6
        # Detection center at (0.5, 0.5) → POS_LEFT = (0.5-0.2)/0.6*100 = 50%
        parent = (0.2, 0.2, 0.8, 0.8)
        pct = compute_position_pct(
            (0.4, 0.4, 0.6, 0.6), parent, EvalLimitItemParameter.POS_LEFT
        )
        assert pct == pytest.approx(50.0)

    def test_zero_dimension_returns_zero(self):
        pct = compute_position_pct(
            (0.5, 0.5, 0.6, 0.6), (0.5, 0.0, 0.5, 1.0),  # zero width
            EvalLimitItemParameter.POS_LEFT,
        )
        assert pct == 0.0


class TestValueWithinLimits:
    def test_within_range(self):
        assert value_within_limits(5.0, 1.0, 10.0) is True

    def test_below_range(self):
        assert value_within_limits(0.5, 1.0, 10.0) is False

    def test_above_range(self):
        assert value_within_limits(11.0, 1.0, 10.0) is False

    def test_no_lower_bound(self):
        assert value_within_limits(5.0, None, 10.0) is True
        assert value_within_limits(11.0, None, 10.0) is False

    def test_no_upper_bound(self):
        assert value_within_limits(5.0, 1.0, None) is True
        assert value_within_limits(0.5, 1.0, None) is False

    def test_no_bounds(self):
        assert value_within_limits(999.0, None, None) is True

    def test_exact_boundary(self):
        assert value_within_limits(1.0, 1.0, 10.0) is True
        assert value_within_limits(10.0, 1.0, 10.0) is True


# pytest.approx import needed at module level
import pytest
