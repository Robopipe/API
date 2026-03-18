from ..models.dashboard.dashboard_config import DashboardConfig
from ..models.detection.detection import BaseNNDetections
from .evaluators import DashboardEvaluator, LineCrossingTracker

_line_crossing_tracker = LineCrossingTracker()
_dashboard_evaluator = DashboardEvaluator(_line_crossing_tracker)


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

    dashboard_detections = _dashboard_evaluator.evaluate(
        dashboard_config, detections.detections
    )
    result["dashboard_detections"] = dashboard_detections
    return result


def reset_line_crossing(config_id: int) -> None:
    """Reset line crossing state for a config (called on dashboard start)."""
    _line_crossing_tracker.reset(config_id)
