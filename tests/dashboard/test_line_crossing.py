from robopipe_api.dashboard.line_crossing import LineCrossingTracker
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

        # center y=0.7 >= 0.5 → past, but first frame so not a "new crossing"
        detections = [make_detection(coords=(0.4, 0.6, 0.6, 0.8))]
        crossed, has_new, _tids = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 1
        assert bool(has_new) is False

    def test_horizontal_detection_before_line(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.POSITIVE)

        # center y=0.3 < 0.5 → not past
        detections = [make_detection(coords=(0.4, 0.2, 0.6, 0.4))]
        crossed, has_new, _tids = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 0
        assert bool(has_new) is False

    def test_vertical_detection_past_line(self):
        tracker = LineCrossingTracker()
        config = make_config(
            line_direction=DashboardLineDirection.VERTICAL,
            line_position=0.5,
            line_flow=DashboardLineFlow.POSITIVE,
        )

        # center x=0.7 >= 0.5 → past, but first frame so not a "new crossing"
        detections = [make_detection(coords=(0.6, 0.4, 0.8, 0.6))]
        crossed, has_new, _tids = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 1
        assert bool(has_new) is False


class TestLineCrossingNegativeFlow:
    """NEGATIVE flow: past = coord <= linePosition."""

    def test_horizontal_detection_above_line_is_past(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.NEGATIVE)

        # center y=0.3 <= 0.5 → past in negative flow, first frame so not new
        detections = [make_detection(coords=(0.4, 0.2, 0.6, 0.4))]
        crossed, has_new, _tids = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 1
        assert bool(has_new) is False

    def test_horizontal_detection_below_line_is_not_past(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.NEGATIVE)

        # center y=0.7 > 0.5 → not past in negative flow
        detections = [make_detection(coords=(0.4, 0.6, 0.6, 0.8))]
        crossed, has_new, _tids = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 0
        assert bool(has_new) is False

    def test_vertical_negative_flow(self):
        tracker = LineCrossingTracker()
        config = make_config(
            line_direction=DashboardLineDirection.VERTICAL,
            line_position=0.5,
            line_flow=DashboardLineFlow.NEGATIVE,
        )

        # center x=0.3 <= 0.5 → past, first frame so not new
        detections = [make_detection(coords=(0.2, 0.4, 0.4, 0.6))]
        crossed, has_new, _tids = tracker.find_crossed_detections(detections, config)
        assert len(crossed) == 1
        assert bool(has_new) is False


class TestLineCrossingTracking:
    """Multi-frame tracking behavior."""

    def test_crossing_transition(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.POSITIVE)

        # Frame 1: detection before line
        det_before = [make_detection(label=0, coords=(0.4, 0.2, 0.6, 0.4))]  # cy=0.3
        crossed, has_new, _tids = tracker.find_crossed_detections(det_before, config)
        assert len(crossed) == 0
        assert bool(has_new) is False

        # Frame 2: same detection moves past line
        det_after = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]  # cy=0.7
        crossed, has_new, _tids = tracker.find_crossed_detections(det_after, config)
        assert len(crossed) == 1
        assert bool(has_new) is True

    def test_already_past_no_new_crossing(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.POSITIVE)

        # Frame 1: appears past line — no prior not-past state, so not a new crossing
        det = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]
        _, has_new, _tids = tracker.find_crossed_detections(det, config)
        assert bool(has_new) is False

        # Frame 2: still past → still not new
        crossed, has_new, _tids = tracker.find_crossed_detections(det, config)
        assert len(crossed) == 1
        assert bool(has_new) is False

    def test_multiple_configs_independent(self):
        tracker = LineCrossingTracker()
        config_a = make_config(config_id=1, line_position=0.5)
        config_b = make_config(config_id=2, line_position=0.5)

        # Detection starts before line, then crosses
        det_before = [make_detection(label=0, coords=(0.4, 0.2, 0.6, 0.4))]
        det_after = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]

        # Seed config_a with before-line detection
        tracker.find_crossed_detections(det_before, config_a)  # noqa: return unused
        # Cross on config_a
        _, has_new_a, _ = tracker.find_crossed_detections(det_after, config_a)
        assert bool(has_new_a) is True

        # Seed config_b with before-line detection (independent state)
        tracker.find_crossed_detections(det_before, config_b)  # noqa: return unused
        # Cross on config_b
        _, has_new_b, _ = tracker.find_crossed_detections(det_after, config_b)
        assert bool(has_new_b) is True

    def test_detection_disappears_and_reappears(self):
        tracker = LineCrossingTracker()
        config = make_config(line_position=0.5, line_flow=DashboardLineFlow.POSITIVE)

        # Frame 1: detection before line
        det1 = [make_detection(label=0, coords=(0.4, 0.2, 0.6, 0.4))]
        tracker.find_crossed_detections(det1, config)  # noqa: return unused

        # Frame 2: same detection crosses line
        det2 = [make_detection(label=0, coords=(0.4, 0.6, 0.6, 0.8))]
        _, has_new, _tids = tracker.find_crossed_detections(det2, config)
        assert bool(has_new) is True

        # Frame 3: detection disappears
        _, has_new, _tids = tracker.find_crossed_detections([], config)
        assert bool(has_new) is False

        # Frame 4: new detection appears before line (far from ghost at cx=0.5)
        det4 = [make_detection(label=0, coords=(0.0, 0.2, 0.2, 0.4))]
        tracker.find_crossed_detections(det4, config)  # noqa: return unused

        # Frame 5: crosses the line → new crossing
        det5 = [make_detection(label=0, coords=(0.0, 0.6, 0.2, 0.8))]
        crossed, has_new, _tids = tracker.find_crossed_detections(det5, config)
        assert len(crossed) == 1
        assert bool(has_new) is True


class TestMaxMatchDistance:
    """Euclidean distance gate prevents far-apart ID reuse."""

    def test_far_reentry_gets_new_id(self):
        """Object leaving frame should not donate its ID to a far-away entry."""
        tracker = LineCrossingTracker()
        config = make_config(
            line_position=0.5,
            line_flow=DashboardLineFlow.POSITIVE,
            max_match_distance=0.2,
        )

        # Frame 1: detection at left side of frame (center ~0.15, 0.35)
        det1 = [make_detection(label=0, coords=(0.1, 0.3, 0.2, 0.4))]
        _, _, tids1 = tracker.find_crossed_detections(det1, config)

        # Frame 2: detection disappears
        tracker.find_crossed_detections([], config)

        # Frame 3: detection reappears far away at right side (center ~0.85, 0.35)
        det3 = [make_detection(label=0, coords=(0.8, 0.3, 0.9, 0.4))]
        _, _, tids3 = tracker.find_crossed_detections(det3, config)

        # The new detection must get a different tracking ID
        id1 = tids1[0]
        id3 = tids3[0]
        # Both may be None if not yet confirmed, but if assigned they must differ
        if id1 is not None and id3 is not None:
            assert id1 != id3

    def test_nearby_reentry_preserves_id(self):
        """Object that briefly disappears nearby should keep its tracking ID."""
        tracker = LineCrossingTracker()
        config = make_config(
            line_position=0.5,
            line_flow=DashboardLineFlow.POSITIVE,
            max_match_distance=0.2,
        )

        # Frame 1: detection appears (confirmed immediately with debounce=1)
        det = [make_detection(label=0, coords=(0.4, 0.3, 0.6, 0.4))]
        _, _, tids = tracker.find_crossed_detections(det, config)
        id_before = tids[0]
        assert id_before is not None

        # Frame 2: detection disappears for 1 frame
        tracker.find_crossed_detections([], config)

        # Frame 3: reappears very close to where it was (center shifts by ~0.02)
        det_near = [make_detection(label=0, coords=(0.42, 0.3, 0.62, 0.4))]
        _, _, tids_after = tracker.find_crossed_detections(det_near, config)
        assert tids_after[0] == id_before
