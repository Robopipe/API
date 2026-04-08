from robopipe_api.dashboard.evaluators import LineCrossingTracker
from robopipe_api.models.dashboard.dashboard_config import (
    DashboardLineDirection,
    DashboardLineFlow,
)

from .conftest import make_config, make_detection


class TestLineCrossingPositiveFlow:
    """POSITIVE flow: past = coord >= linePosition."""

    def test_horizontal_detection_past_line(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.POSITIVE)

        # center y=0.7 >= 0.5 → past
        detections = [make_detection(coords=(0.4, 0.6, 0.6, 0.8))]
        crossed, has_new = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 1
        assert bool(has_new) is True

    def test_horizontal_detection_before_line(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.POSITIVE)

        # center y=0.3 < 0.5 → not past
        detections = [make_detection(coords=(0.4, 0.2, 0.6, 0.4))]
        crossed, has_new = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 0
        assert bool(has_new) is False

    def test_vertical_detection_past_line(self):
        tracker = LineCrossingTracker()
        config = make_config(
            line_direction=DashboardLineDirection.VERTICAL,
            line_position=0.5,
            line_flow=DashboardLineFlow.POSITIVE,
        )

        # center x=0.7 >= 0.5 → past
        detections = [make_detection(coords=(0.6, 0.4, 0.8, 0.6))]
        crossed, has_new = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 1
        assert bool(has_new) is True


class TestLineCrossingNegativeFlow:
    """NEGATIVE flow: past = coord <= linePosition."""

    def test_horizontal_detection_above_line_is_past(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.NEGATIVE)

        # center y=0.3 <= 0.5 → past in negative flow
        detections = [make_detection(coords=(0.4, 0.2, 0.6, 0.4))]
        crossed, has_new = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 1
        assert bool(has_new) is True

    def test_horizontal_detection_below_line_is_not_past(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.NEGATIVE)

        # center y=0.7 > 0.5 → not past in negative flow
        detections = [make_detection(coords=(0.4, 0.6, 0.6, 0.8))]
        crossed, has_new = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 0
        assert bool(has_new) is False

    def test_vertical_negative_flow(self):
        tracker = LineCrossingTracker()
        config = make_config(
            line_direction=DashboardLineDirection.VERTICAL,
            line_position=0.5,
            line_flow=DashboardLineFlow.NEGATIVE,
        )

        # center x=0.3 <= 0.5 → past
        detections = [make_detection(coords=(0.2, 0.4, 0.4, 0.6))]
        crossed, has_new = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 1
        assert bool(has_new) is True


class TestLineCrossingTracking:
    """Multi-frame tracking behavior."""

    def test_crossing_transition(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.POSITIVE)

        # Frame 1: detection before line
        det_before = [make_detection(label=0, coords=(0.4, 0.2, 0.6, 0.4))]  # cy=0.3
        crossed, has_new = tracker.find_crossed_detections(det_before, config)
        assert len(crossed) == 0
        assert bool(has_new) is False

        # Frame 2: same detection moves past line
        det_after = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]  # cy=0.7
        crossed, has_new = tracker.find_crossed_detections(det_after, config)
        assert len(crossed) == 1
        assert bool(has_new) is True

    def test_already_crossed_no_new(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.POSITIVE)

        # Frame 1: appears past line → crossed + new
        det = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]
        _, has_new = tracker.find_crossed_detections(det, config)
        assert bool(has_new) is True

        # Frame 2: same detection still past → crossed but NOT new
        crossed, has_new = tracker.find_crossed_detections(det, config)
        assert len(crossed) == 1
        assert bool(has_new) is False

    def test_multiple_configs_independent(self):
        tracker = LineCrossingTracker()
        config_a = make_config(config_id=1, line_position=0.5)
        config_b = make_config(config_id=2, line_position=0.5)

        det = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]

        # First crossing on config_a
        _, has_new_a = tracker.find_crossed_detections(det, config_a)
        assert bool(has_new_a) is True

        # Independent first crossing on config_b
        _, has_new_b = tracker.find_crossed_detections(det, config_b)
        assert bool(has_new_b) is True

    def test_detection_disappears_and_reappears(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.POSITIVE)

        # Frame 1: detection past line
        det1 = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]
        _, has_new = tracker.find_crossed_detections(det1, config)
        assert bool(has_new) is True

        # Frame 2: detection disappears
        _, has_new = tracker.find_crossed_detections([], config)
        assert bool(has_new) is False

        # Frame 3: new detection appears past line → counts as new
        det3 = [make_detection(label=0, coords=(0.3, 0.7, 0.5, 0.9))]
        crossed, has_new = tracker.find_crossed_detections(det3, config)
        assert len(crossed) == 1
        assert bool(has_new) is True
