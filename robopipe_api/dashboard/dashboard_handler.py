from ..models.dashboard.dashboard_config import DashboardConfig
from ..models.detection.detection import BaseNNDetections
from .evaluators import DashboardEvaluator, LineCrossingTracker
from .threshold_tracker import ThresholdTracker

_line_crossing_tracker = LineCrossingTracker()
_threshold_tracker = ThresholdTracker()
_dashboard_evaluator = DashboardEvaluator(_line_crossing_tracker, _threshold_tracker)


def handle_detections(
    dashboard_config: DashboardConfig | None,
    detections: BaseNNDetections,
    running: bool = False,
) -> dict:
    """Evaluate dashboard test cases against detections and return enriched result.

    When running is False, skips evaluation entirely (no dashboard_detections).
    """
    result = detections.model_dump()

    if dashboard_config is None or not running:
        return result

    detections = _dashboard_evaluator.evaluate(dashboard_config, detections.detections)
    result["dashboard_detections"] = detections
    result["threshold_status"] = _threshold_tracker.get_status(
        dashboard_config.id, dashboard_config.testCases
    )

    # dashboard_detections, display_violation = _dashboard_evaluator.evaluate(
    #     dashboard_config, detections.detections
    # )
    # result["dashboard_detections"] = dashboard_detections

    # if display_violation is not None:
    #     result["display_violation"] = display_violation

    # if dashboard_detections is not None:
    #     threshold_status = _threshold_tracker.get_status(
    #         dashboard_config.id, dashboard_config.testCases
    #     )
    #     if threshold_status:
    #         result["threshold_status"] = threshold_status

    return result


def reset_line_crossing(config_id: int) -> None:
    """Reset line crossing and threshold state for a config (called on dashboard start)."""
    _line_crossing_tracker.reset(config_id)
    _threshold_tracker.reset(config_id)
