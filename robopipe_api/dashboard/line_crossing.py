from __future__ import annotations

from dataclasses import dataclass

from .geometry import bbox_center, euclidean_distance
from ..models.dashboard.dashboard_config import (
    DashboardConfig,
    DashboardLineDirection,
    DashboardLineFlow,
)
from ..models.detection.bbox_detection import BBoxDetection


@dataclass
class TrackedDetection:
    label: int
    cx: float
    cy: float
    is_past_line: bool
    has_crossed: bool
    missing_frames: int = 0


class LineCrossingTracker:
    """Tracks per-config detection line crossings across frames."""

    def __init__(self, max_missing_frames: int = 5) -> None:
        self._state: dict[int, list[TrackedDetection]] = {}
        self._max_missing_frames = max_missing_frames

    def _is_past_line(
        self,
        coords: tuple[float, float, float, float],
        config: DashboardConfig,
    ) -> bool:
        cx, cy = bbox_center(coords)
        positive = config.lineFlow == DashboardLineFlow.POSITIVE

        if config.lineDirection == DashboardLineDirection.HORIZONTAL:
            return cy >= config.linePosition if positive else cy <= config.linePosition
        return cx >= config.linePosition if positive else cx <= config.linePosition

    def find_crossed_detections(
        self,
        detections: list[BBoxDetection],
        config: DashboardConfig,
    ) -> tuple[list[BBoxDetection], set[int]]:
        """Return (crossed, just_crossed_label_indices).

        crossed: currently-visible detections that have ever crossed the line.
        just_crossed_label_indices: set of detection label indices (d.label)
            that had at least one new crossing this frame.
        """
        prev_state = self._state.get(config.id, [])

        prev_not_past = [d for d in prev_state if not d.is_past_line]
        curr_not_past: list[TrackedDetection] = []
        curr_past: list[TrackedDetection] = []
        ret_past: list[BBoxDetection] = []
        curr_used: set[int] = set()
        not_past_used: set[int] = set()
        matched_prev: set[int] = set()

        for det in detections:
            cx, cy = bbox_center(det.coords)
            past = self._is_past_line(det.coords, config)

            if past:
                curr_past.append(TrackedDetection(det.label, cx, cy, True, False))
                ret_past.append(det)
            else:
                curr_not_past.append(TrackedDetection(det.label, cx, cy, False, False))

        for pi, prev in enumerate(prev_not_past):
            best_dist = float("inf")
            best_index = None
            best_in_past = False

            for i, curr in enumerate(curr_past):
                if curr.label != prev.label or i in curr_used:
                    continue
                dist = euclidean_distance((prev.cx, prev.cy), (curr.cx, curr.cy))
                if dist < best_dist:
                    best_dist = dist
                    best_index = i
                    best_in_past = True

            for i, curr in enumerate(curr_not_past):
                if curr.label != prev.label or i in not_past_used:
                    continue
                dist = euclidean_distance((prev.cx, prev.cy), (curr.cx, curr.cy))
                if dist < best_dist:
                    best_dist = dist
                    best_index = i
                    best_in_past = False

            if best_index is not None:
                matched_prev.add(pi)
                if best_in_past:
                    curr_used.add(best_index)
                    curr_past[best_index].has_crossed = True
                else:
                    not_past_used.add(best_index)

        # Keep unmatched prev not-past detections alive until grace period expires
        for pi, prev in enumerate(prev_not_past):
            if pi in matched_prev:
                continue
            prev.missing_frames += 1
            if prev.missing_frames <= self._max_missing_frames:
                curr_not_past.append(prev)

        self._state[config.id] = curr_not_past + curr_past
        return ret_past, curr_used

    def reset(self, config_id: int) -> None:
        """Clear crossing state for a config (e.g. on dashboard start)."""
        self._state.pop(config_id, None)
