from __future__ import annotations

from ..models.dashboard.eval_models import EvalTestCase


class ThresholdTracker:
    """Tracks cumulative pass/fail counts per test case per config.

    Computes pass rates and determines which threshold zone the rate falls into.
    State resets on dashboard start.
    """

    def __init__(self) -> None:
        # config_id -> {test_case_id -> {total, failures}}
        self._state: dict[int, dict[str, dict[str, int]]] = {}

    def record(self, config_id: int, test_case_id: str, passed: bool) -> None:
        """Record a single evaluation result for a test case."""
        config_state = self._state.setdefault(config_id, {})
        tc_state = config_state.setdefault(test_case_id, {"total": 0, "failures": 0})
        tc_state["total"] += 1
        if not passed:
            tc_state["failures"] += 1

    def get_status(
        self, config_id: int, test_cases: list[EvalTestCase]
    ) -> dict[str, dict] | None:
        """Return threshold status for all test cases with thresholds.

        Returns a dict keyed by test_case_id with:
          total, failures, pass_rate, zone_name, zone_color
        Returns None if no test cases have thresholds.
        """
        config_state = self._state.get(config_id, {})
        result: dict[str, dict] = {}

        for tc in test_cases:
            if not tc.thresholds:
                continue

            tc_state = config_state.get(tc.id, {"total": 0, "failures": 0})
            total = tc_state["total"]
            failures = tc_state["failures"]

            if total == 0:
                pass_rate = 1.0
            else:
                pass_rate = (total - failures) / total

            zone_name, zone_color, is_best_zone = self._determine_zone(tc, pass_rate)

            result[tc.id] = {
                "total": total,
                "failures": failures,
                "pass_rate": round(pass_rate, 2),
                "zone_name": zone_name,
                "zone_color": zone_color,
                "is_best_zone": is_best_zone,
            }

        return result if result else None

    @staticmethod
    def _determine_zone(
        test_case: EvalTestCase, pass_rate: float
    ) -> tuple[str, str, bool]:
        """Find which threshold zone the pass_rate falls into.

        Thresholds are sorted by value ascending. The zone is the first
        threshold where pass_rate < threshold.value. If pass_rate >= all
        threshold values, the last threshold is used.
        """
        sorted_thresholds = sorted(test_case.thresholds, key=lambda t: t.value)

        for threshold in sorted_thresholds[:-1]:
            if pass_rate < threshold.value:
                return threshold.name, threshold.color, False

        # Pass rate >= all threshold values → last (best) zone
        last = sorted_thresholds[-1]
        return last.name, last.color, True

    def reset(self, config_id: int) -> None:
        """Clear all tracking state for a config (called on dashboard start)."""
        self._state.pop(config_id, None)
