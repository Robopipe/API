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
    tracking_id: int | None = None
    missing_frames: int = 0


class LineCrossingTracker:
    """Tracks per-config detection line crossings across frames."""

    def __init__(self, max_missing_frames: int = 2) -> None:
        self._state: dict[int, list[TrackedDetection]] = {}
        self._max_missing_frames = max_missing_frames
        self._next_id: dict[int, int] = {}

    def _allocate_id(self, config_id: int) -> int:
        tid = self._next_id.get(config_id, 1)
        self._next_id[config_id] = tid + 1
        return tid

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
    ) -> tuple[list[BBoxDetection], set[int], list[int]]:
        """Return (crossed, just_crossed_label_indices, tracking_ids).

        crossed: currently-visible detections that have ever crossed the line.
        just_crossed_label_indices: set of detection label indices (d.label)
            that had at least one new crossing this frame.
        tracking_ids: list parallel to *detections* with a persistent ID per
            tracked object.
        """
        prev_state = self._state.get(config.id, [])

        prev_not_past = [d for d in prev_state if not d.is_past_line]
        prev_past = [d for d in prev_state if d.is_past_line]
        curr_not_past: list[TrackedDetection] = []
        curr_past: list[TrackedDetection] = []
        ret_past: list[BBoxDetection] = []
        past_claimed: set[int] = set()
        not_past_used: set[int] = set()
        matched_prev_not_past: set[int] = set()

        # Maps from input detection index → index in curr_past / curr_not_past
        det_to_past: dict[int, int] = {}
        det_to_not_past: dict[int, int] = {}

        for di, det in enumerate(detections):
            cx, cy = bbox_center(det.coords)
            past = self._is_past_line(det.coords, config)

            if past:
                det_to_past[di] = len(curr_past)
                curr_past.append(TrackedDetection(det.label, cx, cy, True, False))
                ret_past.append(det)
            else:
                det_to_not_past[di] = len(curr_not_past)
                curr_not_past.append(TrackedDetection(det.label, cx, cy, False, False))

        # --- First pass: match prev_not_past → current (crossing detection) ---
        for pi, prev in enumerate(prev_not_past):
            best_dist = float("inf")
            best_index = None
            best_in_past = False

            for i, curr in enumerate(curr_past):
                if curr.label != prev.label or i in past_claimed:
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
                matched_prev_not_past.add(pi)
                if best_in_past:
                    past_claimed.add(best_index)
                    curr_past[best_index].has_crossed = True
                    curr_past[best_index].tracking_id = prev.tracking_id
                else:
                    not_past_used.add(best_index)
                    curr_not_past[best_index].tracking_id = prev.tracking_id

        # --- Second pass: match prev_past → unmatched curr_past (ID persistence) ---
        matched_prev_past: set[int] = set()
        for pi, prev in enumerate(prev_past):
            best_dist = float("inf")
            best_index = None

            for i, curr in enumerate(curr_past):
                if curr.label != prev.label or i in past_claimed:
                    continue
                dist = euclidean_distance((prev.cx, prev.cy), (curr.cx, curr.cy))
                if dist < best_dist:
                    best_dist = dist
                    best_index = i

            if best_index is not None:
                matched_prev_past.add(pi)
                past_claimed.add(best_index)
                curr_past[best_index].tracking_id = prev.tracking_id

        # --- Assign new IDs to unmatched current detections ---
        for td in curr_past:
            if td.tracking_id is None:
                td.tracking_id = self._allocate_id(config.id)
        for td in curr_not_past:
            if td.tracking_id is None:
                td.tracking_id = self._allocate_id(config.id)

        # Keep unmatched prev not-past detections alive until grace period expires
        for pi, prev in enumerate(prev_not_past):
            if pi in matched_prev_not_past:
                continue
            prev.missing_frames += 1
            if prev.missing_frames <= self._max_missing_frames:
                curr_not_past.append(prev)

        self._state[config.id] = curr_not_past + curr_past

        # Build tracking_ids parallel to input detections
        tracking_ids: list[int] = []
        for di in range(len(detections)):
            if di in det_to_past:
                tracking_ids.append(curr_past[det_to_past[di]].tracking_id)  # type: ignore[arg-type]
            else:
                tracking_ids.append(curr_not_past[det_to_not_past[di]].tracking_id)  # type: ignore[arg-type]

        just_crossed = {i for i, td in enumerate(curr_past) if td.has_crossed}
        return ret_past, just_crossed, tracking_ids

    def reset(self, config_id: int) -> None:
        """Clear crossing state for a config (e.g. on dashboard start)."""
        self._state.pop(config_id, None)
        self._next_id.pop(config_id, None)
