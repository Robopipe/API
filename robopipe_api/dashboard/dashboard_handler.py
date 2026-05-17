import hashlib

import av

from ..models.dashboard.dashboard_config import DashboardConfig
from ..models.dashboard.user_settings import (
    TUNING_OVERRIDE_FIELDS,
    DashboardUserSettings,
)
from ..models.detection.bbox_detection import BBoxDetection
from ..models.detection.detection import BaseNNDetections
from .evaluators import DashboardEvaluator, EvaluationResult
from .zone_tracker import ZoneTracker
from .threshold_tracker import ThresholdTracker
from .events_store import events_store_factory

_zone_tracker = ZoneTracker()
_threshold_tracker = ThresholdTracker()
_dashboard_evaluator = DashboardEvaluator(_zone_tracker, _threshold_tracker)

# Mirror in Studio: apps/web/src/modules/run/utils/dashboardUnlock.ts
def compute_settings_unlock(mxid: str, stream_name: str) -> str:
    """Deterministic token both Studio and the camera derive from public
    deployment identifiers. Acts as a casual lock that hides settings UI from
    users who reach the dashboard without going through Studio."""
    return hashlib.sha256(f"{mxid}:{stream_name}".encode()).hexdigest()[:16]


def apply_tuning_overrides(
    config: DashboardConfig, user_settings: DashboardUserSettings
) -> DashboardConfig:
    """Return a copy of `config` with user tuning overrides applied.

    Optional fields (None on user_settings) leave the config's default in place.
    `labelConfidenceThresholds` is always taken from user_settings since its
    "no override" state is an empty dict.
    """
    overrides: dict[str, object] = {}
    for field in TUNING_OVERRIDE_FIELDS:
        value = getattr(user_settings, field)
        if field == "labelConfidenceThresholds":
            overrides[field] = value
            continue
        if value is not None:
            overrides[field] = value
    return config.model_copy(update=overrides) if overrides else config


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
    video_frame: av.VideoFrame | None = None,
) -> dict:
    """Evaluate dashboard test cases against detections and return enriched result.

    `video_frame` is forwarded to the evaluator so the commit branch can
    render the violation picture server-side at zone exit. When None (no
    frame available — e.g. WebRTC isn't connected yet), the evaluation still
    runs and events are saved without a picture.
    """
    result = detections.model_dump()

    if dashboard_config is None or dashboard_run_session_id is None:
        return result

    overrides = dashboard_config.labelConfidenceThresholds
    global_threshold = dashboard_config.confidenceThreshold
    filtered = [
        d
        for d in detections.detections
        if d.confidence >= overrides.get(d.label, global_threshold)
    ]

    evaluation_results, tracking_ids, display_ids = _dashboard_evaluator.evaluate(
        dashboard_config, filtered, dashboard_run_session_id, video_frame=video_frame
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

    return result


def reset_zone_tracking(config_id: int) -> None:
    """Reset zone tracking and threshold state for a config (called on dashboard start)."""
    _dashboard_evaluator.reset(config_id)
    _threshold_tracker.reset(config_id)
