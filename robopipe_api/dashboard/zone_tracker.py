from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geometry import bbox_center, bbox_dimensions
from .kalman_tracker import (
    KalmanBoxTracker,
    KalmanParams,
    associate_detections_to_tracks,
)
from ..models.dashboard.dashboard_config import (
    DashboardConfig,
    DashboardZoneDirection,
)
from ..models.detection.bbox_detection import BBoxDetection


def _params_from_config(config: DashboardConfig) -> KalmanParams:
    return KalmanParams(
        iou_floor=config.iouFloor,
        iou_cost_weight=config.iouCostWeight,
        mahalanobis_gate=config.mahalanobisGate,
        ghost_gate_growth=config.ghostGateGrowth,
        process_noise_pos=config.processNoisePos,
        process_noise_size=config.processNoiseSize,
        process_noise_vel=config.processNoiseVel,
        measurement_noise_pos=config.measurementNoisePos,
        measurement_noise_size=config.measurementNoiseSize,
        initial_var_pos=config.initialVarPos,
        initial_var_vel=config.initialVarVel,
    )


def _is_confirmed(track: KalmanBoxTracker, debounce_frames: int) -> bool:
    """A track is confirmed once it has been seen for at least *debounce_frames* frames."""
    return track.hit_streak + 1 >= debounce_frames


_X_AXIS_DIRECTIONS = {
    DashboardZoneDirection.LeftToRight,
    DashboardZoneDirection.RightToLeft,
}
_LO_ENTRY_DIRECTIONS = {
    DashboardZoneDirection.LeftToRight,
    DashboardZoneDirection.TopToBottom,
}


def _zone_axis_coord(
    coords: tuple[float, float, float, float],
    direction: DashboardZoneDirection,
) -> float:
    cx, cy = bbox_center(coords)
    return cx if direction in _X_AXIS_DIRECTIONS else cy


def _side_for_coord(coord: float, lo: float, hi: float) -> str | None:
    """Classify a coord relative to zone bounds: "lo" (before zone), "hi" (after), or None (inside)."""
    if coord < lo:
        return "lo"
    if coord > hi:
        return "hi"
    return None


def expected_entry_side(direction: DashboardZoneDirection) -> str:
    return "lo" if direction in _LO_ENTRY_DIRECTIONS else "hi"


def expected_exit_side(direction: DashboardZoneDirection) -> str:
    return "hi" if direction in _LO_ENTRY_DIRECTIONS else "lo"


@dataclass
class ZoneTrackingResult:
    """Result of a single frame of zone tracking."""

    in_zone: list[BBoxDetection] = field(default_factory=list)
    in_zone_tracker_ids: list[int] = field(default_factory=list)
    just_entered_indices: set[int] = field(default_factory=set)
    exited_tracker_ids: list[int] = field(default_factory=list)
    tracking_ids: list[int | None] = field(default_factory=list)
    display_ids: list[int | None] = field(default_factory=list)
    just_confirmed: list[tuple[int, int]] = field(default_factory=list)
    entry_sides: dict[int, str] = field(default_factory=dict)
    exit_sides: dict[int, str] = field(default_factory=dict)


class ZoneTracker:
    """Tracks per-config detection presence within an evaluation zone across frames."""

    def __init__(self) -> None:
        self._tracks: dict[int, list[KalmanBoxTracker]] = {}
        self._next_id: dict[int, int] = {}
        # Per-label display-id counter per config: config_id -> label -> next value
        self._next_display_id: dict[int, dict[int, int]] = {}
        # Previous frame state per (config_id, tracking_id): (in_zone, axis_coord).
        # The axis coord is the relevant axis (X for L/R directions, Y for T/B);
        # we keep it so we can determine which side of the zone a tracker
        # crossed when transitioning into the zone next frame.
        self._prev_state: dict[int, dict[int, tuple[bool, float]]] = {}

    def _allocate_id(self, config_id: int) -> int:
        tid = self._next_id.get(config_id, 1)
        self._next_id[config_id] = tid + 1
        return tid

    def _allocate_display_id(self, config_id: int, label: int) -> int:
        per_label = self._next_display_id.setdefault(config_id, {})
        did = per_label.get(label, 1)
        per_label[label] = did + 1
        return did

    @staticmethod
    def _zone_range(config: DashboardConfig) -> tuple[float, float]:
        half = config.zoneThickness / 2.0
        lo = max(0.0, config.zoneCenter - half)
        hi = min(1.0, config.zoneCenter + half)
        return lo, hi

    def _is_within_zone(
        self,
        coords: tuple[float, float, float, float],
        config: DashboardConfig,
    ) -> bool:
        lo, hi = self._zone_range(config)
        coord = _zone_axis_coord(coords, config.zoneDirection)
        return lo <= coord <= hi

    def find_in_zone_detections(
        self,
        detections: list[BBoxDetection],
        config: DashboardConfig,
    ) -> ZoneTrackingResult:
        """Track detections and classify them against the evaluation zone.

        Returns a :class:`ZoneTrackingResult` with:
        - in_zone: confirmed detections currently inside the zone.
        - in_zone_tracker_ids: parallel tracker IDs.
        - just_entered_indices: indices into ``in_zone`` for trackers whose
          state transitioned from outside-the-zone to inside this frame.
        - exited_tracker_ids: trackers that were inside the zone last frame
          and are now outside (or have expired as ghosts).
        - tracking_ids: parallel to the input ``detections`` list; ``None``
          when a detection is not yet confirmed.
        """
        existing_tracks = self._tracks.get(config.id, [])
        prev_state = self._prev_state.get(config.id, {})
        zone_lo, zone_hi = self._zone_range(config)
        direction = config.zoneDirection
        params = _params_from_config(config)

        # Build measurements from current detections
        measurements: list[np.ndarray] = []
        det_bboxes: list[tuple[float, float, float, float]] = []
        labels: list[int] = []
        in_zone_flags: list[bool] = []
        axis_coords: list[float] = []

        for det in detections:
            cx, cy = bbox_center(det.coords)
            w, h = bbox_dimensions(det.coords)
            measurements.append(np.array([cx, cy, w, h], dtype=np.float64))
            det_bboxes.append(det.coords)
            labels.append(det.label)
            in_zone_flags.append(self._is_within_zone(det.coords, config))
            axis_coords.append(_zone_axis_coord(det.coords, direction))

        # Associate detections to existing tracks
        matches, unmatched_tracks, unmatched_dets = associate_detections_to_tracks(
            existing_tracks,
            measurements,
            det_bboxes,
            labels,
            params=params,
            debounce_frames=config.debounceFrames,
            max_match_distance=config.maxMatchDistance,
        )

        debounce_frames = config.debounceFrames

        tracking_ids: list[int | None] = [None] * len(detections)
        display_ids: list[int | None] = [None] * len(detections)
        just_confirmed: list[tuple[int, int]] = []
        just_confirmed_tids: set[int] = set()

        # Matched: update track and inherit ID if confirmed
        for ti, di in matches:
            track = existing_tracks[ti]
            track.update(measurements[di])
            if _is_confirmed(track, debounce_frames):
                if track.display_id is None:
                    track.display_id = self._allocate_display_id(
                        config.id, track.label
                    )
                    just_confirmed.append((track.display_id, track.label))
                    just_confirmed_tids.add(track.tracking_id)
                tracking_ids[di] = track.tracking_id
                display_ids[di] = track.display_id

        # Unmatched detections: create new tracks
        new_tracks: list[KalmanBoxTracker] = []
        for di in unmatched_dets:
            tid = self._allocate_id(config.id)
            new_track = KalmanBoxTracker(measurements[di], tid, labels[di], params)
            new_tracks.append(new_track)
            if _is_confirmed(new_track, debounce_frames):
                new_track.display_id = self._allocate_display_id(
                    config.id, new_track.label
                )
                just_confirmed.append((new_track.display_id, new_track.label))
                tracking_ids[di] = tid
                display_ids[di] = new_track.display_id

        # Unmatched tracks: age them (ghost expiry)
        surviving_ghosts: list[KalmanBoxTracker] = []
        expired_ghosts: list[KalmanBoxTracker] = []
        for ti in unmatched_tracks:
            track = existing_tracks[ti]
            track.time_since_update += 1
            track.hit_streak = 0
            if track.time_since_update <= config.maxMissingFrames:
                surviving_ghosts.append(track)
            else:
                expired_ghosts.append(track)

        # Update track state for next frame
        matched_tracks = [existing_tracks[ti] for ti, _ in matches]
        self._tracks[config.id] = matched_tracks + new_tracks + surviving_ghosts

        # Compute current in-zone state for every tracker we still know about,
        # and derive just-entered / just-exited along with the side of the zone
        # crossed (used by the evaluator for direction filtering).
        curr_state: dict[int, tuple[bool, float]] = {}
        just_entered_tracker_ids: set[int] = set()
        exited_tracker_ids: list[int] = []
        entry_sides: dict[int, str] = {}
        exit_sides: dict[int, str] = {}
        expected_in_side = expected_entry_side(direction)

        # Matched tracks: use measurement
        for ti, di in matches:
            track = existing_tracks[ti]
            if track.tracking_id is None:
                continue
            tid = track.tracking_id
            now_in = in_zone_flags[di]
            curr_coord = axis_coords[di]
            curr_state[tid] = (now_in, curr_coord)
            prev = prev_state.get(tid)
            was_in = prev[0] if prev is not None else False
            if was_in and not now_in:
                exited_tracker_ids.append(tid)
                side = _side_for_coord(curr_coord, zone_lo, zone_hi)
                if side is not None:
                    exit_sides[tid] = side
            elif not was_in and now_in and _is_confirmed(track, debounce_frames):
                just_entered_tracker_ids.add(tid)
                if prev is not None:
                    side = _side_for_coord(prev[1], zone_lo, zone_hi)
                    if side is not None:
                        entry_sides[tid] = side
            elif was_in and now_in and tid in just_confirmed_tids:
                # Track confirmed this frame while already in-zone — it sat
                # unconfirmed inside the zone for ≥1 frame before clearing
                # the debounce gate, so the entry transition was never
                # observed. Presume the entry side was the configured
                # expected_in so the evaluator's direction filter accepts
                # the eventual clean exit; the exit-side gate still drops
                # mis-traversals.
                entry_sides[tid] = expected_in_side

        # Brand-new tracks: confirmed-this-frame in-zone tracks (typically
        # resurrected after a Kalman ghost expiry under crowding) get
        # expected_in as their presumed entry side, mirroring the matched-
        # track presumption above.
        for idx, di in enumerate(unmatched_dets):
            track = new_tracks[idx]
            if track.tracking_id is None:
                continue
            tid = track.tracking_id
            now_in = in_zone_flags[di]
            curr_state[tid] = (now_in, axis_coords[di])
            if now_in and _is_confirmed(track, debounce_frames):
                just_entered_tracker_ids.add(tid)
                entry_sides[tid] = expected_in_side

        # Surviving ghosts: carry over their last-known state (neither entry nor exit)
        for track in surviving_ghosts:
            tid = track.tracking_id
            if tid is None or tid in curr_state:
                continue
            prev = prev_state.get(tid)
            if prev is not None:
                curr_state[tid] = prev

        # Expired ghosts: if they were in the zone, treat as an exit. The
        # current axis coord is unknown (no detection this frame), so the exit
        # side stays absent — the evaluator will discard accumulated samples.
        for track in expired_ghosts:
            tid = track.tracking_id
            if tid is None:
                continue
            prev = prev_state.get(tid)
            if prev is not None and prev[0]:
                exited_tracker_ids.append(tid)

        self._prev_state[config.id] = curr_state

        # Build the in-zone detection list (confirmed + currently inside)
        in_zone: list[BBoxDetection] = []
        in_zone_tracker_ids: list[int] = []
        just_entered_indices: set[int] = set()
        for di, det in enumerate(detections):
            if not in_zone_flags[di]:
                continue
            tid = tracking_ids[di]
            if tid is None:
                continue
            idx = len(in_zone)
            in_zone.append(det)
            in_zone_tracker_ids.append(tid)
            if tid in just_entered_tracker_ids:
                just_entered_indices.add(idx)

        return ZoneTrackingResult(
            in_zone=in_zone,
            in_zone_tracker_ids=in_zone_tracker_ids,
            just_entered_indices=just_entered_indices,
            exited_tracker_ids=exited_tracker_ids,
            tracking_ids=tracking_ids,
            display_ids=display_ids,
            just_confirmed=just_confirmed,
            entry_sides=entry_sides,
            exit_sides=exit_sides,
        )

    def reset(self, config_id: int) -> None:
        """Clear tracking state for a config (e.g. on dashboard start)."""
        self._tracks.pop(config_id, None)
        self._next_id.pop(config_id, None)
        self._next_display_id.pop(config_id, None)
        self._prev_state.pop(config_id, None)
