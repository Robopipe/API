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

    def __init__(self, max_missing_frames: int = 5) -> None:
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

        # Build current TrackedDetections and classify past/not-past
        curr: list[TrackedDetection] = []
        ret_past: list[BBoxDetection] = []
        ret_past_curr_indices: list[int] = []  # which curr[] indices are past

        for det in detections:
            cx, cy = bbox_center(det.coords)
            past = self._is_past_line(det.coords, config)
            curr.append(TrackedDetection(det.label, cx, cy, past, False))
            if past:
                ret_past_curr_indices.append(len(curr) - 1)
                ret_past.append(det)

        # --- Global matching: all prev → all curr by label + proximity ---
        # Build candidate pairs sorted by distance (greedy nearest-first)
        pairs: list[tuple[float, int, int]] = []
        for pi, prev in enumerate(prev_state):
            for ci, cur in enumerate(curr):
                if prev.label != cur.label:
                    continue
                dist = euclidean_distance((prev.cx, prev.cy), (cur.cx, cur.cy))
                pairs.append((dist, pi, ci))
        pairs.sort()

        matched_prev: set[int] = set()
        matched_curr: set[int] = set()
        for _dist, pi, ci in pairs:
            if pi in matched_prev or ci in matched_curr:
                continue
            matched_prev.add(pi)
            matched_curr.add(ci)

            prev = prev_state[pi]
            cur = curr[ci]
            cur.tracking_id = prev.tracking_id

            # Crossing: was not-past, now is past
            if not prev.is_past_line and cur.is_past_line:
                cur.has_crossed = True

        # --- Assign new IDs to unmatched current detections ---
        for td in curr:
            if td.tracking_id is None:
                td.tracking_id = self._allocate_id(config.id)

        # --- Grace period: keep unmatched prev alive ---
        carryover: list[TrackedDetection] = []
        for pi, prev in enumerate(prev_state):
            if pi in matched_prev:
                continue
            prev.missing_frames += 1
            prev.has_crossed = False
            if prev.missing_frames <= self._max_missing_frames:
                carryover.append(prev)

        self._state[config.id] = curr + carryover

        # Build tracking_ids parallel to input detections
        tracking_ids = [curr[i].tracking_id for i in range(len(detections))]  # type: ignore[misc]

        # Build just-crossed set (indices into ret_past)
        just_crossed: set[int] = set()
        for rpi, ci in enumerate(ret_past_curr_indices):
            if curr[ci].has_crossed:
                just_crossed.add(rpi)

        return ret_past, just_crossed, tracking_ids

    def reset(self, config_id: int) -> None:
        """Clear crossing state for a config (e.g. on dashboard start)."""
        self._state.pop(config_id, None)
        self._next_id.pop(config_id, None)
