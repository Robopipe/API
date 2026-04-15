from __future__ import annotations

import numpy as np

from .geometry import bbox_center, bbox_dimensions
from .kalman_tracker import KalmanBoxTracker, associate_detections_to_tracks
from ..models.dashboard.dashboard_config import (
    DashboardConfig,
    DashboardLineDirection,
    DashboardLineFlow,
)
from ..models.detection.bbox_detection import BBoxDetection


def _is_confirmed(track: KalmanBoxTracker, debounce_frames: int) -> bool:
    """A track is confirmed once it has been seen for at least *debounce_frames* frames."""
    return track.hit_streak + 1 >= debounce_frames


class LineCrossingTracker:
    """Tracks per-config detection line crossings across frames."""

    def __init__(self) -> None:
        self._tracks: dict[int, list[KalmanBoxTracker]] = {}
        # self._max_missing_frames = max_missing_frames
        # self._max_match_distance = max_match_distance
        self._next_id: dict[int, int] = {}
        # Previous frame's is_past_line per (config_id, tracking_id)
        self._prev_past_line: dict[int, dict[int, bool]] = {}

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
        existing_tracks = self._tracks.get(config.id, [])
        prev_past = self._prev_past_line.get(config.id, {})

        # Build measurements from current detections
        measurements: list[np.ndarray] = []
        labels: list[int] = []
        past_line_flags: list[bool] = []

        for det in detections:
            cx, cy = bbox_center(det.coords)
            w, h = bbox_dimensions(det.coords)
            measurements.append(np.array([cx, cy, w, h], dtype=np.float64))
            labels.append(det.label)
            past_line_flags.append(self._is_past_line(det.coords, config))

        # Associate detections to existing tracks
        matches, unmatched_tracks, unmatched_dets = associate_detections_to_tracks(
            existing_tracks, measurements, labels
        )

        debounce_frames = config.debounceFrames

        # Process results
        tracking_ids: list[int | None] = [None] * len(detections)
        has_crossed: list[bool] = [False] * len(detections)

        # Matched: update track, inherit ID and check crossing only if confirmed
        for ti, di in matches:
            track = existing_tracks[ti]
            track.update(measurements[di])

            if _is_confirmed(track, debounce_frames):
                tracking_ids[di] = track.tracking_id
                was_past = prev_past.get(track.tracking_id, False)
                if not was_past and past_line_flags[di]:
                    has_crossed[di] = True

        # Unmatched detections: create new tracks
        new_tracks: list[KalmanBoxTracker] = []
        for di in unmatched_dets:
            tid = self._allocate_id(config.id)
            new_track = KalmanBoxTracker(measurements[di], tid, labels[di])
            new_tracks.append(new_track)
            if _is_confirmed(new_track, debounce_frames):
                tracking_ids[di] = tid

        # Unmatched tracks: age them (ghost expiry)
        surviving_ghosts: list[KalmanBoxTracker] = []
        for ti in unmatched_tracks:
            track = existing_tracks[ti]
            track.time_since_update += 1
            track.hit_streak = 0
            if track.time_since_update <= config.maxMissingFrames:
                surviving_ghosts.append(track)

        # Update state: matched tracks + new tracks + ghosts
        matched_tracks = [existing_tracks[ti] for ti, _ in matches]
        self._tracks[config.id] = matched_tracks + new_tracks + surviving_ghosts

        # Update prev_past_line for ALL tracks (including unconfirmed) so that
        # position history is available when a track becomes confirmed.
        curr_past: dict[int, bool] = {}
        for ti, di in matches:
            curr_past[existing_tracks[ti].tracking_id] = past_line_flags[di]
        for idx, di in enumerate(unmatched_dets):
            curr_past[new_tracks[idx].tracking_id] = past_line_flags[di]
        # Carry over ghost classifications unchanged
        for track in surviving_ghosts:
            if track.tracking_id not in curr_past:
                curr_past[track.tracking_id] = prev_past.get(track.tracking_id, False)
        self._prev_past_line[config.id] = curr_past

        # Build set of confirmed detection indices
        confirmed: set[int] = set()
        for ti, di in matches:
            if _is_confirmed(existing_tracks[ti], debounce_frames):
                confirmed.add(di)
        for idx, di in enumerate(unmatched_dets):
            if _is_confirmed(new_tracks[idx], debounce_frames):
                confirmed.add(di)

        # Build return values — only confirmed detections appear in crossed
        ret_past: list[BBoxDetection] = []
        ret_past_det_indices: list[int] = []
        for di, det in enumerate(detections):
            if past_line_flags[di] and di in confirmed:
                ret_past_det_indices.append(di)
                ret_past.append(det)

        just_crossed: set[int] = set()
        for rpi, di in enumerate(ret_past_det_indices):
            if has_crossed[di]:
                just_crossed.add(rpi)

        return ret_past, just_crossed, tracking_ids  # type: ignore[return-value]

    def reset(self, config_id: int) -> None:
        """Clear crossing state for a config (e.g. on dashboard start)."""
        self._tracks.pop(config_id, None)
        self._next_id.pop(config_id, None)
        self._prev_past_line.pop(config_id, None)
