from ..models.dashboard.dashboard_config import DashboardConfig
from ..models.detection.bbox_detection import BBoxDetection
from ..models.detection.detection import BaseNNDetections
from .evaluators import DashboardEvaluator, EvaluationResult
from .zone_tracker import ZoneTracker
from .threshold_tracker import ThresholdTracker
from .events_store import events_store_factory

_zone_tracker = ZoneTracker()
_threshold_tracker = ThresholdTracker()
_dashboard_evaluator = DashboardEvaluator(_zone_tracker, _threshold_tracker)


def _annotate_detections(
    result: dict,
    evaluation_results: list[EvaluationResult],
    source_detections: list[BBoxDetection],
) -> None:
    """Embed violation info into the specific detections that violated each limit."""
    id_to_index = {id(det): i for i, det in enumerate(source_detections)}
    for ev in evaluation_results:
        if ev.violated_limit_severity is None:
            continue
        violation = {
            "limit_name": ev.violated_limit_name,
            "severity": ev.violated_limit_severity,
        }
        for det in ev.violating_detections:
            idx = id_to_index.get(id(det))
            if idx is None:
                continue
            target = result["detections"][idx]
            if "violations" not in target:
                target["violations"] = []
            target["violations"].append(violation)


def handle_detections(
    dashboard_config: DashboardConfig | None,
    detections: BaseNNDetections,
    dashboard_run_session_id: int | None,
) -> dict:
    """Evaluate dashboard test cases against detections and return enriched result."""
    result = detections.model_dump()

    if dashboard_config is None or dashboard_run_session_id is None:
        return result

    filtered = [
        d
        for d in detections.detections
        if d.confidence >= dashboard_config.confidenceThreshold
    ]

    evaluation_results, violation_events, tracking_ids, display_ids = (
        _dashboard_evaluator.evaluate(
            dashboard_config, filtered, dashboard_run_session_id
        )
    )

    # Build after evaluate — line crossing sorts filtered in-place for stable ID assignment
    result["detections"] = [d.model_dump() for d in filtered]

    # Build dashboard_detections from evaluation results (one per unique test case)
    seen_tc_ids: set[str] = set()
    dashboard_detections = []
    for ev in evaluation_results:
        if ev.test_case_id in seen_tc_ids:
            continue
        seen_tc_ids.add(ev.test_case_id)
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

    _annotate_detections(result, evaluation_results, filtered)

    for i, tid in enumerate(tracking_ids):
        result["detections"][i]["tracking_id"] = tid
        result["detections"][i]["display_id"] = display_ids[i]

    result["threshold_status"] = _threshold_tracker.get_status(
        dashboard_config.id, dashboard_config.testCases
    )
    result["master_threshold_status"] = _threshold_tracker.get_master_status(
        dashboard_config.id, dashboard_config.testCases, dashboard_config.thresholds
    )
    events_store = events_store_factory()
    result["counters"] = events_store.get_counters(dashboard_run_session_id)

    if violation_events:
        result["violation_events"] = violation_events

    return result


def reset_zone_tracking(config_id: int) -> None:
    """Reset zone tracking and threshold state for a config (called on dashboard start)."""
    _dashboard_evaluator.reset(config_id)
    _threshold_tracker.reset(config_id)
