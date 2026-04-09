from ..models.dashboard.dashboard_config import DashboardConfig
from ..models.detection.detection import BaseNNDetections
from .evaluators import DashboardEvaluator, EvaluationResult, LineCrossingTracker
from .threshold_tracker import ThresholdTracker
from .events_store import events_store_factory

_line_crossing_tracker = LineCrossingTracker()
_threshold_tracker = ThresholdTracker()
_dashboard_evaluator = DashboardEvaluator(_line_crossing_tracker, _threshold_tracker)


def _build_label_id_to_index(config: DashboardConfig) -> dict[int, int]:
    """Map label.id → index in config.labels list."""
    return {label.id: i for i, label in enumerate(config.labels)}


def _annotate_detections(
    result: dict,
    evaluation_results: list[EvaluationResult],
    label_id_to_index: dict[int, int],
) -> None:
    """Embed violation info directly into each detection dict."""
    for ev in evaluation_results:
        if ev.violated_limit_target_label_id is None or ev.violated_limit_severity is None:
            continue
        label_index = label_id_to_index.get(ev.violated_limit_target_label_id)
        if label_index is None:
            continue
        violation = {
            "limit_name": ev.violated_limit_name,
            "severity": ev.violated_limit_severity,
        }
        for det in result["detections"]:
            if det["label"] == label_index:
                if "violations" not in det:
                    det["violations"] = []
                det["violations"].append(violation)


def handle_detections(
    dashboard_config: DashboardConfig | None,
    detections: BaseNNDetections,
    dashboard_run_session_id: int | None,
) -> dict:
    """Evaluate dashboard test cases against detections and return enriched result.

    When running is False, skips evaluation entirely (no dashboard_detections).
    """
    result = detections.model_dump()

    if dashboard_config is None or dashboard_run_session_id is None:
        return result

    evaluation_results = _dashboard_evaluator.evaluate(
        dashboard_config, detections.detections, dashboard_run_session_id
    )

    # Build dashboard_detections from evaluation results (one per unique test case)
    seen_tc_ids: set[str] = set()
    dashboard_detections = []
    for ev in evaluation_results:
        if ev.test_case_id in seen_tc_ids:
            continue
        seen_tc_ids.add(ev.test_case_id)
        # Look up test case severity from config
        tc = next(
            (tc for tc in dashboard_config.testCases if tc.id == ev.test_case_id),
            None,
        )
        if tc is None or tc.severity is None:
            continue
        dashboard_detections.append(
            {"test_case_id": ev.test_case_id, "type": tc.severity.value}
        )
    result["dashboard_detections"] = dashboard_detections

    # Embed violation info into individual detections
    label_id_to_index = _build_label_id_to_index(dashboard_config)
    _annotate_detections(result, evaluation_results, label_id_to_index)

    result["threshold_status"] = _threshold_tracker.get_status(
        dashboard_config.id, dashboard_config.testCases
    )
    events_store = events_store_factory()
    result["counters"] = events_store.get_counters(dashboard_run_session_id)

    return result


def reset_line_crossing(config_id: int) -> None:
    """Reset line crossing and threshold state for a config (called on dashboard start)."""
    _line_crossing_tracker.reset(config_id)
    _threshold_tracker.reset(config_id)
