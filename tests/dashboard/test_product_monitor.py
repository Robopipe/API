"""Unit tests for the product-switch monitor state machine and scoring.

All clocks are injected via the explicit `now` parameter; no test sleeps.
Label ids follow conftest LABELS: 1=defect, 2=part, 3=container.
"""

import itertools
from collections import deque

import pytest

from robopipe_api.dashboard.product_monitor import (
    ProductMonitor,
    _Baseline,
    product_check_enabled,
)
from robopipe_api.models.dashboard.dashboard_config import DashboardConfig

from .conftest import make_config


def pc_config(**overrides) -> DashboardConfig:
    params = dict(
        productCheckEnabled=True,
        productCheckCalibrationCount=5,
        productCheckWindowSize=5,
        productCheckDivergenceThreshold=0.35,
        productCheckSnoozeCommits=3,
        productCheckSnoozeSeconds=120.0,
        productCheckStarvationMultiplier=10.0,
    )
    params.update(overrides)
    return make_config().model_copy(update=params)


_tids = itertools.count(1)


def commit(monitor, config, label_id, conf=0.9, now=0.0):
    tid = next(_tids)
    if conf is not None:
        monitor.observe_dwell_confidence(config, tid, conf)
    monitor.observe_commit(config, tid, label_id, now=now)


def calibrate(monitor, config, labels=(1, 1, 1, 2, 2), conf=0.9, start=0.0):
    """Feed one calibration's worth of commits at 1s intervals."""
    for i, label in enumerate(labels):
        commit(monitor, config, label, conf=conf, now=start + float(i))


class TestCalibration:
    def test_baseline_built_at_target_and_window_seeded(self):
        m, config = ProductMonitor(), pc_config()
        calibrate(m, config)  # 3× label 1, 2× label 2 at t=0..4

        st = m._runs[config.id]
        assert st.phase == "ok"
        assert st.baseline.share == {1: 0.6, 2: 0.4}
        assert st.baseline.mean_conf == {1: pytest.approx(0.9), 2: pytest.approx(0.9)}
        assert st.baseline.anchor_label_id == 1
        assert st.baseline.typical_interval_s == pytest.approx(1.0)
        assert len(st.window) == 5  # seeded with the calibration commits
        assert st.calib == []

    def test_status_reports_calibration_progress(self):
        m, config = ProductMonitor(), pc_config()
        commit(m, config, 1, now=0.0)
        commit(m, config, 1, now=1.0)

        status = m.status(config, now=1.5)
        assert status == {
            "state": "calibrating",
            "calibrated": 2,
            "calibration_target": 5,
        }

    def test_dwell_confidence_is_mean_over_frames(self):
        m, config = ProductMonitor(), pc_config()
        tid = next(_tids)
        m.observe_dwell_confidence(config, tid, 0.6)
        m.observe_dwell_confidence(config, tid, 0.8)
        m.observe_commit(config, tid, 1, now=0.0)

        assert m._runs[config.id].calib == [(1, pytest.approx(0.7))]

    def test_discarded_dwell_leaves_no_confidence(self):
        m, config = ProductMonitor(), pc_config()
        tid = next(_tids)
        m.observe_dwell_confidence(config, tid, 0.6)
        m.discard_dwell(config, tid)
        m.observe_commit(config, tid, 1, now=0.0)

        assert m._runs[config.id].calib == [(1, None)]


class TestScoring:
    """Direct tests of the divergence math on hand-built baselines."""

    @staticmethod
    def baseline(share, mean_conf=None, anchor=1):
        return _Baseline(
            share=share,
            mean_conf=mean_conf or {},
            anchor_label_id=anchor,
            typical_interval_s=1.0,
        )

    def test_steady_mix_scores_zero(self):
        b = self.baseline({1: 0.6, 2: 0.4}, {1: 0.9, 2: 0.9})
        window = deque([(1, 0.9)] * 6 + [(2, 0.9)] * 4)
        assert ProductMonitor._score(b, window) == pytest.approx(0.0)

    def test_mix_flip_scores_total_variation(self):
        b = self.baseline({1: 0.6, 2: 0.4})
        window = deque([(1, None)] * 2 + [(2, None)] * 8)  # 0.2 / 0.8
        assert ProductMonitor._score(b, window) == pytest.approx(0.4)

    def test_rare_baseline_label_absence_is_downweighted(self):
        b = self.baseline({1: 0.9, 3: 0.1})
        window = deque([(1, None)] * 10)
        # w1=1 → 0.1; w3=0.1/0.15 → 0.0667; total variation halved.
        assert ProductMonitor._score(b, window) == pytest.approx(0.0833, abs=1e-3)

    def test_foreign_label_flood_gets_full_weight(self):
        b = self.baseline({1: 1.0})
        window = deque([(1, None)] * 4 + [(9, None)] * 6)
        assert ProductMonitor._score(b, window) == pytest.approx(0.6)

    def test_anchor_vanishing_hard_trips(self):
        b = self.baseline({1: 0.6, 2: 0.4}, anchor=1)
        window = deque([(2, None)] * 10)
        assert ProductMonitor._score(b, window) == 1.0

    def test_confidence_drop_alarms_without_mix_change(self):
        b = self.baseline({1: 1.0}, {1: 0.9})
        window = deque([(1, 0.5)] * 10)
        assert ProductMonitor._score(b, window) == pytest.approx(0.4)

    def test_confidence_rise_does_not_alarm(self):
        b = self.baseline({1: 1.0}, {1: 0.9})
        window = deque([(1, 0.98)] * 10)
        assert ProductMonitor._score(b, window) == pytest.approx(0.0)


class TestStateMachine:
    def test_steady_mix_never_alarms(self):
        m, config = ProductMonitor(), pc_config()
        calibrate(m, config)
        for i in range(10):
            label = 1 if i % 5 < 3 else 2
            commit(m, config, label, now=5.0 + i)
        st = m._runs[config.id]
        assert st.phase == "ok"
        assert st.last_score == pytest.approx(0.0)

    def test_sustained_mix_flip_raises_mismatch(self):
        m, config = ProductMonitor(), pc_config()
        calibrate(m, config)  # window seeded [1,1,1,2,2]
        commit(m, config, 2, now=5.0)  # window [1,1,2,2,2] → D=0.2, ok
        assert m._runs[config.id].phase == "ok"
        commit(m, config, 2, now=6.0)  # window [1,2,2,2,2] → D=0.4 ≥ 0.35
        st = m._runs[config.id]
        assert st.phase == "mismatch"
        assert st.alarm_started_wall is not None
        assert st.alarm_deadline_mono == pytest.approx(16.0)  # now + 10s
        assert st.alarm_deadline_epoch_ms is not None
        assert st.alarm_total_s == pytest.approx(10.0)

    def test_mismatch_status_reports_deadline(self):
        m, config = ProductMonitor(), pc_config()
        calibrate(m, config)
        commit(m, config, 2, now=5.0)
        commit(m, config, 2, now=6.0)

        status = m.status(config, now=9.0)
        assert status["state"] == "mismatch"
        assert status["deadline_in_s"] == pytest.approx(7.0)
        assert status["total_in_s"] == pytest.approx(10.0)
        assert status["score"] == pytest.approx(0.4)
        assert status["threshold"] == 0.35

    def test_is_suspended_only_in_mismatch(self):
        m, config = ProductMonitor(), pc_config()
        assert not m.is_suspended(config.id)
        calibrate(m, config)
        assert not m.is_suspended(config.id)
        commit(m, config, 2, now=5.0)
        commit(m, config, 2, now=6.0)
        assert m.is_suspended(config.id)
        m.cancel_alarm(config, now=7.0)
        assert not m.is_suspended(config.id)  # snoozed does not suspend

    def test_recalibrate_wipes_to_calibrating(self):
        m, config = ProductMonitor(), pc_config()
        calibrate(m, config)
        m.recalibrate(config.id)
        assert m.status(config, now=10.0)["state"] == "calibrating"
        assert m.status(config, now=10.0)["calibrated"] == 0


class TestSnooze:
    def force_mismatch(self, m, config, now=6.0):
        calibrate(m, config)
        commit(m, config, 2, now=now - 1)
        commit(m, config, 2, now=now)
        assert m._runs[config.id].phase == "mismatch"

    def test_cancel_snoozes_and_rearms_after_commits(self):
        m, config = ProductMonitor(), pc_config()  # snooze after 3 commits
        self.force_mismatch(m, config)
        assert m.cancel_alarm(config, now=7.0)
        assert m._runs[config.id].alarm_total_s is None

        # Window is still anchor-free-ish; keep pushing the foreign label.
        commit(m, config, 2, now=8.0)
        assert m._runs[config.id].phase == "snoozed"
        commit(m, config, 2, now=9.0)
        assert m._runs[config.id].phase == "snoozed"
        # Third commit ends the snooze and immediately re-scores: the window
        # is now all label 2 → anchor vanished → S=1.0 → re-fires.
        commit(m, config, 2, now=10.0)
        assert m._runs[config.id].phase == "mismatch"

    def test_snooze_expires_by_time_via_status(self):
        m, config = ProductMonitor(), pc_config(
            productCheckStarvationMultiplier=1000.0  # keep starved out of the way
        )
        self.force_mismatch(m, config)
        m.cancel_alarm(config, now=10.0)

        status = m.status(config, now=129.9)  # 10 + 120s not yet elapsed
        assert status["state"] == "snoozed"
        assert status["snooze_remaining_s"] == pytest.approx(0.1)
        assert status["snooze_remaining_commits"] == 3

        assert m.status(config, now=130.1)["state"] == "ok"

    def test_cancel_returns_false_without_active_alarm(self):
        m, config = ProductMonitor(), pc_config()
        assert not m.cancel_alarm(config, now=0.0)
        calibrate(m, config)
        assert not m.cancel_alarm(config, now=5.0)


class TestAutoStopClaim:
    def force_mismatch(self, m, config):
        calibrate(m, config)
        commit(m, config, 2, now=5.0)
        commit(m, config, 2, now=6.0)  # deadline at 16.0

    def test_claim_only_after_deadline_and_exactly_once(self):
        m, config = ProductMonitor(), pc_config()
        self.force_mismatch(m, config)

        assert m.claim_auto_stop(config.id, now=15.9) is None
        alarm_time = m.claim_auto_stop(config.id, now=16.0)
        assert alarm_time is not None
        assert m.claim_auto_stop(config.id, now=16.1) is None

    def test_cancel_after_claim_is_rejected(self):
        m, config = ProductMonitor(), pc_config()
        self.force_mismatch(m, config)
        assert m.claim_auto_stop(config.id, now=17.0) is not None
        assert not m.cancel_alarm(config, now=17.1)

    def test_cancel_before_deadline_prevents_claim(self):
        m, config = ProductMonitor(), pc_config()
        self.force_mismatch(m, config)
        assert m.cancel_alarm(config, now=10.0)
        assert m.claim_auto_stop(config.id, now=20.0) is None

    def test_get_alarm_time_matches_claimed(self):
        m, config = ProductMonitor(), pc_config()
        self.force_mismatch(m, config)
        before = m.get_alarm_time(config.id)
        assert before is not None
        assert m.claim_auto_stop(config.id, now=16.0) == before

    def test_configured_alarm_seconds_set_the_deadline(self):
        m, config = ProductMonitor(), pc_config(productCheckAlarmSeconds=5.0)
        self.force_mismatch(m, config)  # mismatch at 6.0 → deadline at 11.0

        assert m.status(config, now=6.0)["deadline_in_s"] == pytest.approx(5.0)
        assert m.status(config, now=6.0)["total_in_s"] == pytest.approx(5.0)
        assert m.claim_auto_stop(config.id, now=10.9) is None
        assert m.claim_auto_stop(config.id, now=11.0) is not None

    def test_recalibrate_mid_alarm_prevents_auto_stop(self):
        """Disabling product check from the settings tab PATCHes the config,
        which recalibrates a running monitor — the in-flight alarm must die
        with the old state instead of still stopping the run."""
        m, config = ProductMonitor(), pc_config()
        self.force_mismatch(m, config)

        m.recalibrate(config.id)
        assert m.claim_auto_stop(config.id, now=20.0) is None
        assert not m.is_suspended(config.id)
        disabled = config.model_copy(update={"productCheckEnabled": False})
        assert m.status(disabled, now=20.0) is None


class TestStarvation:
    def test_starved_derives_and_clears(self):
        m, config = ProductMonitor(), pc_config()
        calibrate(m, config)  # commits at t=0..4, median interval 1s, ×10 → 10s

        assert m.status(config, now=13.9)["state"] == "ok"
        assert m.status(config, now=14.1)["state"] == "starved"

        commit(m, config, 1, now=15.0)
        assert m.status(config, now=15.5)["state"] == "ok"

    def test_bursty_commits_do_not_false_starve(self):
        """One product commits all its labels within a fraction of a second;
        the watchdog must scale with the gap BETWEEN those bursts, not the
        near-zero gaps inside them (regression: median-of-all-gaps made the
        banner fire during every normal between-product pause)."""
        m, config = ProductMonitor(), pc_config()
        times = [0.0, 0.05, 0.1, 2.0, 2.1]  # two products, ~2s cadence
        for label, t in zip([1, 2, 2, 1, 2], times):
            commit(m, config, label, now=t)

        st = m._runs[config.id]
        assert st.baseline.typical_interval_s == pytest.approx(1.9)

        # An ordinary between-product gap stays quiet…
        assert m.status(config, now=2.1 + 5.0)["state"] == "ok"
        # …only ~multiplier × product cadence goes starved.
        assert m.status(config, now=2.1 + 19.1)["state"] == "starved"

    def test_starvation_timeout_has_floor(self):
        m, config = ProductMonitor(), pc_config()
        for i in range(5):  # very fast line: commits every 0.1s
            commit(m, config, 1, now=i * 0.1)

        # multiplier 10 × 0.1s = 1s would flash constantly; the 10s floor
        # keeps the banner quiet until the pause is meaningfully long.
        assert m.status(config, now=0.4 + 5.0)["state"] == "ok"
        assert m.status(config, now=0.4 + 10.1)["state"] == "starved"

    def test_mismatch_takes_precedence_over_starved(self):
        m, config = ProductMonitor(), pc_config()
        calibrate(m, config)
        commit(m, config, 2, now=5.0)
        commit(m, config, 2, now=6.0)
        assert m.status(config, now=500.0)["state"] == "mismatch"

    def test_active_snooze_takes_precedence_over_starved(self):
        m, config = ProductMonitor(), pc_config(productCheckSnoozeSeconds=1000.0)
        calibrate(m, config)
        commit(m, config, 2, now=5.0)
        commit(m, config, 2, now=6.0)
        m.cancel_alarm(config, now=7.0)
        assert m.status(config, now=100.0)["state"] == "snoozed"


class TestFeatureGate:
    def test_disabled_by_default(self):
        m, config = ProductMonitor(), make_config()
        assert not product_check_enabled(config)
        commit(m, config, 1, now=0.0)
        assert m._runs == {}
        assert m.status(config, now=1.0) is None

    def test_config_opt_out_disables_dashboard(self):
        m, config = ProductMonitor(), pc_config(productCheckEnabled=False)
        assert not product_check_enabled(config)
        commit(m, config, 1, now=0.0)
        assert m._runs == {}
        assert m.status(config, now=1.0) is None

    def test_reset_drops_state(self):
        m, config = ProductMonitor(), pc_config()
        calibrate(m, config)
        m.reset(config.id)
        assert m._runs == {}
