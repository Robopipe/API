"""Integration: ProductMonitor wired through DashboardEvaluator.

Drives detections across the evaluation zone frame by frame with a real
ZoneTracker and asserts the monitor observes commits, and that an active
mismatch suspends events/counters/threshold samples while tracker state
still pops.
"""

import pytest

from robopipe_api.dashboard import evaluators as evaluators_module
from robopipe_api.dashboard.evaluators import DashboardEvaluator
from robopipe_api.dashboard.product_monitor import ProductMonitor
from robopipe_api.dashboard.threshold_tracker import ThresholdTracker
from robopipe_api.dashboard.zone_tracker import ZoneTracker
from robopipe_api.models.dashboard.eval_models import (
    EvalLimitItemParameter,
    EvalTestCaseType,
)

from .conftest import (
    LABEL_PART,
    limit_node,
    make_config,
    make_detection,
    make_limit,
    make_limit_item,
    make_test_case,
)

SESSION_ID = 1


class StubEventsStore:
    def __init__(self):
        self.events = []
        self.counters = []

    def save_event(self, *args, **kwargs):
        self.events.append((args, kwargs))
        return len(self.events)

    def inc_counter(self, *args, **kwargs):
        self.counters.append((args, kwargs))


@pytest.fixture(autouse=True)
def _enable_flag(monkeypatch):
    monkeypatch.setenv("PRODUCT_CHECK_ENABLED", "1")


@pytest.fixture()
def store(monkeypatch):
    stub = StubEventsStore()
    monkeypatch.setattr(
        evaluators_module, "events_store_factory", lambda: stub
    )
    return stub


def build_config():
    # Zone x ∈ [0.45, 0.55], left-to-right; a COUNT(0..10) CHECK on the part
    # label always passes, so every clean traversal commits one event.
    tc = make_test_case(
        tc_type=EvalTestCaseType.CHECK,
        limits=[
            make_limit(
                target_label=LABEL_PART,
                limit_items=[
                    make_limit_item(
                        EvalLimitItemParameter.COUNT, limit_from=0, limit_to=10
                    )
                ],
            )
        ],
        logic_nodes=[limit_node("lim-1")],  # empty tree never fires
    )
    return make_config(
        test_cases=[tc], debounce_frames=1, max_match_distance=0.2
    ).model_copy(
        update=dict(
            productCheckCalibrationCount=5,
            productCheckWindowSize=5,
            productCheckDivergenceThreshold=0.35,
        )
    )


def drive_product(evaluator, config, confidence=0.9):
    """One product traverses the zone: approach, inside, past.

    Boxes are 0.3 wide moving 0.18/frame so consecutive frames overlap
    (IoU above the association floor) and stay within maxMatchDistance.
    """
    for cx in (0.32, 0.50, 0.68):
        det = make_detection(
            label=1,  # index 1 → LABEL_PART (id 2)
            confidence=confidence,
            coords=(cx - 0.15, 0.3, cx + 0.15, 0.5),
        )
        evaluator.evaluate(config, [det], SESSION_ID)
    # A few empty frames so the leftover track never shadows the next product.
    for _ in range(6):
        evaluator.evaluate(config, [], SESSION_ID)


def make_evaluator():
    monitor = ProductMonitor()
    evaluator = DashboardEvaluator(ZoneTracker(), ThresholdTracker(), monitor)
    return evaluator, monitor


class TestCommitFlow:
    def test_clean_traversal_feeds_monitor_with_dwell_confidence(self, store):
        evaluator, monitor = make_evaluator()
        config = build_config()

        drive_product(evaluator, config, confidence=0.8)

        st = monitor._runs[config.id]
        assert st.calib == [(LABEL_PART.id, pytest.approx(0.8))]
        # Normal operation: counter and event fired for the traversal.
        assert len(store.counters) == 1
        assert len(store.events) == 1

    def test_calibration_completes_after_five_products(self, store):
        evaluator, monitor = make_evaluator()
        config = build_config()

        for _ in range(5):
            drive_product(evaluator, config)

        st = monitor._runs[config.id]
        assert st.phase == "ok"
        assert st.baseline.share == {LABEL_PART.id: 1.0}

    def test_non_clean_exit_discards_dwell(self, store):
        evaluator, monitor = make_evaluator()
        config = build_config()

        # Enter the zone, then vanish mid-zone: the Kalman ghost expires
        # while marked in-zone, which registers an exit with no exit side —
        # a non-clean traversal.
        for cx in (0.32, 0.50):
            det = make_detection(
                label=1, confidence=0.9, coords=(cx - 0.15, 0.3, cx + 0.15, 0.5)
            )
            evaluator.evaluate(config, [det], SESSION_ID)
        for _ in range(6):  # maxMissingFrames=5 → ghost expires
            evaluator.evaluate(config, [], SESSION_ID)

        st = monitor._runs[config.id]
        assert st.calib == []  # no commit observed
        assert st.dwell_conf == {}  # accumulator discarded
        assert store.events == []


class TestSuspension:
    def test_mismatch_suspends_events_counters_thresholds(self, store):
        evaluator, monitor = make_evaluator()
        config = build_config()
        threshold_tracker = evaluator._threshold_tracker

        drive_product(evaluator, config)
        events_before = len(store.events)
        counters_before = len(store.counters)
        totals_before = threshold_tracker._state[config.id]["tc-1"]["total"]

        # Force the alarm, then run another product through the zone.
        st = monitor._runs[config.id]
        st.phase = "mismatch"
        st.alarm_deadline_mono = 1e12  # far future; countdown not the subject

        drive_product(evaluator, config)

        assert len(store.events) == events_before
        assert len(store.counters) == counters_before
        assert (
            threshold_tracker._state[config.id]["tc-1"]["total"] == totals_before
        )
        # The suspended traversal fed nothing into the monitor either, and
        # its dwell accumulator was discarded rather than leaked.
        assert st.calib == [(LABEL_PART.id, pytest.approx(0.9))]
        assert st.dwell_conf == {}

    def test_resumed_evaluation_commits_again(self, store):
        evaluator, monitor = make_evaluator()
        config = build_config()

        drive_product(evaluator, config)
        st = monitor._runs[config.id]
        st.phase = "mismatch"
        drive_product(evaluator, config)
        st.phase = "ok"  # as after a cancel → snooze → re-arm cycle
        drive_product(evaluator, config)

        assert len(store.events) == 2  # first + resumed, none while suspended
        assert len(store.counters) == 2
