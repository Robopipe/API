from __future__ import annotations

import math
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..models.dashboard.dashboard_config import DashboardConfig

# Labels whose commit share (baseline and window alike) stays below this get
# proportionally down-weighted in the mix divergence, so a label that is rare
# on the trained product doesn't false-alarm by naturally missing from a
# window. max(p, p̂) keeps full weight for foreign labels surging in the window.
RARE_LABEL_SHARE = 0.15


def product_check_enabled(config: DashboardConfig | None) -> bool:
    """Per-dashboard opt-in; the sole gate for product-switch monitoring."""
    return config is not None and config.productCheckEnabled


@dataclass
class _Baseline:
    share: dict[int, float]  # label_id -> share of calibration commits
    mean_conf: dict[int, float]  # label_id -> mean dwell confidence
    anchor_label_id: int  # most-committed label during calibration
    # Estimated gap between consecutive products (not consecutive commits —
    # one product commits all its labels in a burst). None disables the
    # starvation watchdog.
    typical_interval_s: float | None


@dataclass
class _RunState:
    phase: str = "calibrating"  # calibrating | ok | mismatch | snoozed
    # Anchors the starvation watchdog before any commit arrives. Run start
    # resets the monitor, so state creation lands within one WS tick of it.
    started_mono: float = field(default_factory=time.monotonic)
    calib: list[tuple[int, float | None]] = field(default_factory=list)
    calib_times: list[float] = field(default_factory=list)
    baseline: _Baseline | None = None
    window: deque[tuple[int, float | None]] = field(default_factory=deque)
    dwell_conf: dict[int, tuple[float, int]] = field(default_factory=dict)
    last_commit_mono: float | None = None
    last_score: float | None = None
    alarm_started_wall: str | None = None
    alarm_deadline_mono: float | None = None
    alarm_deadline_epoch_ms: int | None = None
    alarm_total_s: float | None = None
    snooze_started_mono: float | None = None
    snooze_commits_seen: int = 0
    auto_stop_claimed: bool = False


class ProductMonitor:
    """Detects a product switch from the model's own output statistics.

    Learns a per-run baseline (label commit shares, per-label mean dwell
    confidence, typical inter-product interval) from the first
    productCheckCalibrationCount clean zone-exit commits, then scores a
    sliding window of the last productCheckWindowSize commits against it.
    Sustained divergence raises a mismatch alarm with a backend-owned
    auto-stop countdown; a cancel snoozes and re-arms.

    All state is per config_id and process-local (like ThresholdTracker);
    it is reset on run start/stop and wiped for recalibration. Methods are
    guarded by a lock because commits arrive on the WS producer thread while
    cancel/claim arrive on endpoint threads.
    """

    def __init__(self) -> None:
        self._runs: dict[int, _RunState] = {}
        self._lock = threading.Lock()

    def observe_dwell_confidence(
        self, config: DashboardConfig, tracker_id: int, confidence: float
    ) -> None:
        """Accumulate a per-frame confidence sample for an in-zone dwell."""
        if not product_check_enabled(config):
            return
        with self._lock:
            st = self._state(config)
            total, n = st.dwell_conf.get(tracker_id, (0.0, 0))
            st.dwell_conf[tracker_id] = (total + confidence, n + 1)

    def discard_dwell(self, config: DashboardConfig, tracker_id: int) -> None:
        """Drop the accumulator for a dwell that won't commit."""
        if not product_check_enabled(config):
            return
        with self._lock:
            st = self._runs.get(config.id)
            if st is not None:
                st.dwell_conf.pop(tracker_id, None)

    def observe_commit(
        self,
        config: DashboardConfig,
        tracker_id: int,
        label_id: int,
        now: float | None = None,
    ) -> None:
        """Step the state machine with one clean zone-exit commit."""
        if not product_check_enabled(config):
            return
        if now is None:
            now = time.monotonic()
        with self._lock:
            st = self._state(config)
            total, n = st.dwell_conf.pop(tracker_id, (0.0, 0))
            conf = total / n if n else None
            st.last_commit_mono = now

            if st.phase == "calibrating":
                st.calib.append((label_id, conf))
                st.calib_times.append(now)
                if len(st.calib) >= config.productCheckCalibrationCount:
                    self._finish_calibration(st, config)
                return

            st.window.append((label_id, conf))

            if st.phase == "snoozed":
                st.snooze_commits_seen += 1
                if not self._snooze_expired(st, config, now):
                    return
                self._end_snooze(st)

            if st.phase == "ok" and len(st.window) == st.window.maxlen:
                st.last_score = self._score(st.baseline, st.window)
                if st.last_score >= config.productCheckDivergenceThreshold:
                    st.phase = "mismatch"
                    st.alarm_started_wall = datetime.now(timezone.utc).isoformat()
                    st.alarm_deadline_mono = now + config.productCheckAlarmSeconds
                    st.alarm_deadline_epoch_ms = int(
                        (time.time() + config.productCheckAlarmSeconds) * 1000
                    )
                    # Stamped rather than read live in status(): a mid-alarm
                    # settings change must not desync the total from the
                    # deadline it was derived from.
                    st.alarm_total_s = config.productCheckAlarmSeconds

    def is_suspended(self, config_id: int) -> bool:
        """Evaluation (events, counters, threshold samples) pauses only
        while the mismatch alarm is active — not when snoozed or starved."""
        with self._lock:
            st = self._runs.get(config_id)
            return st is not None and st.phase == "mismatch"

    def status(
        self, config: DashboardConfig, now: float | None = None
    ) -> dict | None:
        """WS payload fragment; also applies time-based snooze expiry and
        derives the starved state (never stored — it clears itself)."""
        if not product_check_enabled(config):
            return None
        if now is None:
            now = time.monotonic()
        with self._lock:
            st = self._state(config)
            if st.phase == "snoozed" and self._snooze_expired(st, config, now):
                self._end_snooze(st)

            if st.phase == "calibrating":
                return {
                    "state": (
                        "starved"
                        if self._is_starved(st, config, now)
                        else "calibrating"
                    ),
                    "calibrated": len(st.calib),
                    "calibration_target": config.productCheckCalibrationCount,
                }

            result: dict = {
                "state": st.phase,
                "score": (
                    round(st.last_score, 4) if st.last_score is not None else None
                ),
                "threshold": config.productCheckDivergenceThreshold,
            }
            if st.phase == "mismatch":
                result["deadline_epoch_ms"] = st.alarm_deadline_epoch_ms
                result["deadline_in_s"] = round(
                    max(0.0, st.alarm_deadline_mono - now), 1
                )
                result["total_in_s"] = st.alarm_total_s
            elif st.phase == "snoozed":
                result["snooze_remaining_commits"] = max(
                    0, config.productCheckSnoozeCommits - st.snooze_commits_seen
                )
                result["snooze_remaining_s"] = round(
                    max(
                        0.0,
                        st.snooze_started_mono
                        + config.productCheckSnoozeSeconds
                        - now,
                    ),
                    1,
                )
            elif self._is_starved(st, config, now):
                result["state"] = "starved"
            return result

    def cancel_alarm(
        self, config: DashboardConfig, now: float | None = None
    ) -> bool:
        """Operator dismissed the alarm modal: snooze and re-arm later.
        Returns False when there is no live alarm (already auto-stopped)."""
        if now is None:
            now = time.monotonic()
        with self._lock:
            st = self._runs.get(config.id)
            if st is None or st.phase != "mismatch" or st.auto_stop_claimed:
                return False
            st.phase = "snoozed"
            st.snooze_started_mono = now
            st.snooze_commits_seen = 0
            st.alarm_started_wall = None
            st.alarm_deadline_mono = None
            st.alarm_deadline_epoch_ms = None
            st.alarm_total_s = None
            return True

    def claim_auto_stop(
        self, config_id: int, now: float | None = None
    ) -> str | None:
        """Exactly-once claim of an expired alarm countdown. Returns the
        alarm's wall timestamp when this caller must stop the run, else None.
        The lock arbitrates the race against cancel_alarm: whichever lands
        first wins."""
        if now is None:
            now = time.monotonic()
        with self._lock:
            st = self._runs.get(config_id)
            if (
                st is None
                or st.phase != "mismatch"
                or st.auto_stop_claimed
                or st.alarm_deadline_mono is None
                or now < st.alarm_deadline_mono
            ):
                return None
            st.auto_stop_claimed = True
            return st.alarm_started_wall

    def get_alarm_time(self, config_id: int) -> str | None:
        with self._lock:
            st = self._runs.get(config_id)
            return st.alarm_started_wall if st is not None else None

    def recalibrate(self, config_id: int) -> None:
        """Wipe to a fresh calibration (explicit request or tuning change)."""
        self.reset(config_id)

    def reset(self, config_id: int) -> None:
        with self._lock:
            self._runs.pop(config_id, None)

    def _state(self, config: DashboardConfig) -> _RunState:
        st = self._runs.get(config.id)
        if st is None:
            st = _RunState(window=deque(maxlen=config.productCheckWindowSize))
            self._runs[config.id] = st
        return st

    @staticmethod
    def _finish_calibration(st: _RunState, config: DashboardConfig) -> None:
        n = len(st.calib)
        counts = Counter(label for label, _ in st.calib)
        conf_samples: dict[int, list[float]] = {}
        for label, conf in st.calib:
            if conf is not None:
                conf_samples.setdefault(label, []).append(conf)
        intervals = [
            b - a for a, b in zip(st.calib_times, st.calib_times[1:])
        ]
        # One product commits all its labels in a burst, so most gaps measure
        # within-burst spacing (~0). A high percentile skips the burst noise
        # and lands on the between-product gap — the cadence the starvation
        # watchdog should scale with.
        if len(intervals) >= 2:
            ranked = sorted(intervals)
            typical = ranked[math.ceil(0.9 * (len(ranked) - 1))]
        else:
            typical = None
        st.baseline = _Baseline(
            share={label: count / n for label, count in counts.items()},
            mean_conf={
                label: sum(vals) / len(vals)
                for label, vals in conf_samples.items()
            },
            # Ties break toward the smaller label id for determinism.
            anchor_label_id=max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0],
            typical_interval_s=typical,
        )
        st.window.extend(st.calib[-st.window.maxlen :])
        st.calib = []
        st.calib_times = []
        st.phase = "ok"

    @staticmethod
    def _score(
        baseline: _Baseline, window: deque[tuple[int, float | None]]
    ) -> float:
        m = len(window)
        counts = Counter(label for label, _ in window)
        if counts.get(baseline.anchor_label_id, 0) == 0:
            return 1.0

        # Weighted total variation over the commit-share distributions.
        d_mix = 0.0
        for label in set(baseline.share) | set(counts):
            share = baseline.share.get(label, 0.0)
            window_share = counts.get(label, 0) / m
            weight = min(1.0, max(share, window_share) / RARE_LABEL_SHARE)
            d_mix += weight * abs(window_share - share)
        d_mix *= 0.5

        # Confidence drop (only) per baseline label, weighted by window count.
        drop_sum = 0.0
        sample_count = 0
        for label, base_conf in baseline.mean_conf.items():
            confs = [c for lab, c in window if lab == label and c is not None]
            if len(confs) < 2:
                continue
            window_conf = sum(confs) / len(confs)
            drop_sum += len(confs) * max(0.0, base_conf - window_conf)
            sample_count += len(confs)
        d_conf = drop_sum / sample_count if sample_count else 0.0

        return max(d_mix, d_conf)

    @staticmethod
    def _snooze_expired(
        st: _RunState, config: DashboardConfig, now: float
    ) -> bool:
        return (
            st.snooze_commits_seen >= config.productCheckSnoozeCommits
            or now >= st.snooze_started_mono + config.productCheckSnoozeSeconds
        )

    @staticmethod
    def _end_snooze(st: _RunState) -> None:
        st.phase = "ok"
        st.snooze_started_mono = None
        st.snooze_commits_seen = 0

    @staticmethod
    def _is_starved(
        st: _RunState, config: DashboardConfig, now: float
    ) -> bool:
        anchor = (
            st.last_commit_mono
            if st.last_commit_mono is not None
            else st.started_mono
        )
        # productCheckIdleTimeoutSeconds is the floor even with a baseline —
        # on very fast lines a scaled timeout of a couple of seconds would
        # flash the banner in every ordinary gap between products.
        if st.baseline is not None and st.baseline.typical_interval_s is not None:
            timeout = max(
                config.productCheckStarvationMultiplier
                * st.baseline.typical_interval_s,
                config.productCheckIdleTimeoutSeconds,
            )
        else:
            timeout = config.productCheckIdleTimeoutSeconds
        return now - anchor > timeout
