from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geometry import bbox_center, bbox_dimensions
from .kalman_tracker import KalmanBoxTracker, associate_detections_to_tracks
from ..models.dashboard.dashboard_config import (
    DashboardConfig,
    DashboardZoneDirection,
)
from ..models.detection.bbox_detection import BBoxDetection


def _is_confirmed(track: KalmanBoxTracker, debounce_frames: int) -> bool:
    """A track is confirmed once it has been seen for at least *debounce_frames* frames."""
    return track.hit_streak + 1 >= debounce_frames


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


class ZoneTracker:
    """Tracks per-config detection presence within an evaluation zone across frames."""

    def __init__(self) -> None:
        self._tracks: dict[int, list[KalmanBoxTracker]] = {}
        self._next_id: dict[int, int] = {}
        # Per-label display-id counter per config: config_id -> label -> next value
        self._next_display_id: dict[int, dict[int, int]] = {}
        # Previous frame's in-zone state per (config_id, tracking_id)
        self._prev_in_zone: dict[int, dict[int, bool]] = {}

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
        cx, cy = bbox_center(coords)
        lo, hi = self._zone_range(config)

        if config.zoneDirection == DashboardZoneDirection.HORIZONTAL:
            return lo <= cy <= hi
        return lo <= cx <= hi

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
        detections.sort(
            key=lambda d: bbox_center(d.coords)[0], reverse=True
        )  # right-to-left for better matching of new detections
        existing_tracks = self._tracks.get(config.id, [])
        prev_in_zone = self._prev_in_zone.get(config.id, {})

        # Build measurements from current detections
        measurements: list[np.ndarray] = []
        labels: list[int] = []
        in_zone_flags: list[bool] = []

        for det in detections:
            cx, cy = bbox_center(det.coords)
            w, h = bbox_dimensions(det.coords)
            measurements.append(np.array([cx, cy, w, h], dtype=np.float64))
            labels.append(det.label)
            in_zone_flags.append(self._is_within_zone(det.coords, config))

        # Associate detections to existing tracks
        matches, unmatched_tracks, unmatched_dets = associate_detections_to_tracks(
            existing_tracks,
            measurements,
            labels,
            max_match_distance=config.maxMatchDistance,
        )

        debounce_frames = config.debounceFrames

        tracking_ids: list[int | None] = [None] * len(detections)
        display_ids: list[int | None] = [None] * len(detections)
        just_confirmed: list[tuple[int, int]] = []

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
                tracking_ids[di] = track.tracking_id
                display_ids[di] = track.display_id

        # Unmatched detections: create new tracks
        new_tracks: list[KalmanBoxTracker] = []
        for di in unmatched_dets:
            tid = self._allocate_id(config.id)
            new_track = KalmanBoxTracker(measurements[di], tid, labels[di])
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
        # and derive just-entered / just-exited.
        curr_in_zone: dict[int, bool] = {}
        just_entered_tracker_ids: set[int] = set()
        exited_tracker_ids: list[int] = []

        # Matched tracks: use measurement
        for ti, di in matches:
            track = existing_tracks[ti]
            if track.tracking_id is None:
                continue
            tid = track.tracking_id
            now_in = in_zone_flags[di]
            curr_in_zone[tid] = now_in
            was_in = prev_in_zone.get(tid, False)
            if was_in and not now_in:
                exited_tracker_ids.append(tid)
            elif not was_in and now_in and _is_confirmed(track, debounce_frames):
                just_entered_tracker_ids.add(tid)

        # Brand-new tracks: only consider entries if already confirmed this frame
        for idx, di in enumerate(unmatched_dets):
            track = new_tracks[idx]
            if track.tracking_id is None:
                continue
            tid = track.tracking_id
            now_in = in_zone_flags[di]
            curr_in_zone[tid] = now_in
            if now_in and _is_confirmed(track, debounce_frames):
                just_entered_tracker_ids.add(tid)

        # Surviving ghosts: carry over their last-known state (neither entry nor exit)
        for track in surviving_ghosts:
            tid = track.tracking_id
            if tid is None or tid in curr_in_zone:
                continue
            curr_in_zone[tid] = prev_in_zone.get(tid, False)

        # Expired ghosts: if they were in the zone, treat as an exit
        for track in expired_ghosts:
            tid = track.tracking_id
            if tid is None:
                continue
            if prev_in_zone.get(tid, False):
                exited_tracker_ids.append(tid)

        self._prev_in_zone[config.id] = curr_in_zone

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
        )

    def reset(self, config_id: int) -> None:
        """Clear tracking state for a config (e.g. on dashboard start)."""
        self._tracks.pop(config_id, None)
        self._next_id.pop(config_id, None)
        self._next_display_id.pop(config_id, None)
        self._prev_in_zone.pop(config_id, None)
