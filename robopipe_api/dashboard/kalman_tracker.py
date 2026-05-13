from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from .geometry import bbox_iou


@dataclass(frozen=True)
class KalmanParams:
    """Tunables for the Kalman tracker and its data-association step.

    Defaults match `DashboardConfig`'s default values.
    """

    iou_floor: float = 0.1
    iou_cost_weight: float = 9.4877
    mahalanobis_gate: float = 9.4877
    ghost_gate_growth: float = 0.5
    process_noise_pos: float = 0.01
    process_noise_size: float = 0.001
    process_noise_vel: float = 0.001
    measurement_noise_pos: float = 0.02
    measurement_noise_size: float = 0.01
    initial_var_pos: float = 0.01
    initial_var_vel: float = 1.0

    def initial_covariance(self) -> np.ndarray:
        p = self.initial_var_pos
        v = self.initial_var_vel
        return np.diag([p, p, p, p, v, v]).astype(np.float64)

    def process_noise(self) -> np.ndarray:
        p = self.process_noise_pos
        s = self.process_noise_size
        v = self.process_noise_vel
        return np.diag([p, p, s, s, v, v]).astype(np.float64)

    def measurement_noise(self) -> np.ndarray:
        p = self.measurement_noise_pos
        s = self.measurement_noise_size
        return np.diag([p, p, s, s]).astype(np.float64)


_DEFAULT_PARAMS = KalmanParams()


class KalmanBoxTracker:
    """Per-object Kalman filter using a constant-velocity model.

    State vector (6): [cx, cy, w, h, vx, vy]
    Measurement vector (4): [cx, cy, w, h]
    """

    # Transition matrix (constant velocity, dt=1)
    _F = np.array(
        [
            [1, 0, 0, 0, 1, 0],
            [0, 1, 0, 0, 0, 1],
            [0, 0, 1, 0, 0, 0],
            [0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 1],
        ],
        dtype=np.float64,
    )

    # Measurement matrix
    _H = np.array(
        [
            [1, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0],
            [0, 0, 0, 1, 0, 0],
        ],
        dtype=np.float64,
    )

    def __init__(
        self,
        measurement: np.ndarray,
        tracking_id: int,
        label: int,
        params: KalmanParams = _DEFAULT_PARAMS,
    ) -> None:
        self.tracking_id = tracking_id
        self.label = label
        self.display_id: int | None = None
        self.time_since_update = 0
        self.hit_streak = 0

        # State: [cx, cy, w, h, vx, vy]
        self._x = np.zeros(6, dtype=np.float64)
        self._x[:4] = measurement

        self._P = params.initial_covariance()
        self._Q = params.process_noise()
        self._R = params.measurement_noise()

    def predict(self) -> tuple[np.ndarray, np.ndarray]:
        """Predict next state.

        Returns (predicted_measurement, innovation_covariance S).
        """
        self._x = self._F @ self._x
        self._P = self._F @ self._P @ self._F.T + self._Q

        # Predicted measurement and innovation covariance
        z_pred = self._H @ self._x
        S = self._H @ self._P @ self._H.T + self._R
        return z_pred, S

    def update(self, measurement: np.ndarray) -> None:
        """Kalman update with a new measurement."""
        z_pred = self._H @ self._x
        y = measurement - z_pred  # innovation
        S = self._H @ self._P @ self._H.T + self._R

        # Kalman gain via solve (numerically stable)
        K = np.linalg.solve(S.T, (self._P @ self._H.T).T).T

        self._x = self._x + K @ y

        # Joseph form for numerical stability
        I_KH = np.eye(6) - K @ self._H
        self._P = I_KH @ self._P @ I_KH.T + K @ self._R @ K.T
        # Symmetrise
        self._P = (self._P + self._P.T) / 2

        self.time_since_update = 0
        self.hit_streak += 1

    def get_state(self) -> np.ndarray:
        """Return current [cx, cy, w, h] from state."""
        return self._x[:4].copy()


def _mahalanobis_sq(
    z_pred: np.ndarray,
    S: np.ndarray,
    measurement: np.ndarray,
) -> float:
    """Squared Mahalanobis distance."""
    d = measurement - z_pred
    return float(d @ np.linalg.solve(S, d))


def _center_to_corners(
    cx: float, cy: float, w: float, h: float
) -> tuple[float, float, float, float]:
    half_w = w / 2.0
    half_h = h / 2.0
    return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)


_INF = 1e9


def _pairwise_cost(
    z_pred: np.ndarray,
    S: np.ndarray,
    pred_bbox: tuple[float, float, float, float],
    measurement: np.ndarray,
    det_bbox: tuple[float, float, float, float],
    mahalanobis_gate: float,
    iou_floor: float,
    iou_cost_weight: float,
    max_match_distance: float | None,
) -> float:
    """Combined cost for a single (track, detection) candidate.

    Returns ``_INF`` for hard rejects (label gate handled by the caller).
    """
    if max_match_distance is not None:
        dx = z_pred[0] - measurement[0]
        dy = z_pred[1] - measurement[1]
        if dx * dx + dy * dy > max_match_distance * max_match_distance:
            return _INF
    iou = bbox_iou(pred_bbox, det_bbox)
    if iou < iou_floor:
        return _INF
    mhd = _mahalanobis_sq(z_pred, S, measurement)
    if mhd > mahalanobis_gate:
        return _INF
    return mhd + iou_cost_weight * (1.0 - iou)


@dataclass
class _Prediction:
    """Cached prediction and gating context for one track."""

    z_pred: np.ndarray
    S: np.ndarray
    pred_bbox: tuple[float, float, float, float]
    effective_gate: float


def _predict_all(
    tracks: list[KalmanBoxTracker],
    base_gate: float,
    ghost_gate_growth: float,
) -> list[_Prediction]:
    out: list[_Prediction] = []
    for track in tracks:
        z_pred, S = track.predict()
        gate_scale = 1.0 + ghost_gate_growth * track.time_since_update
        out.append(
            _Prediction(
                z_pred=z_pred,
                S=S,
                pred_bbox=_center_to_corners(
                    z_pred[0], z_pred[1], z_pred[2], z_pred[3]
                ),
                effective_gate=base_gate * gate_scale,
            )
        )
    return out


def _solve_stage(
    track_indices: list[int],
    detection_indices: list[int],
    predictions: list[_Prediction],
    measurements: list[np.ndarray],
    det_bboxes: list[tuple[float, float, float, float]],
    labels: list[int],
    tracks: list[KalmanBoxTracker],
    iou_floor: float,
    iou_cost_weight: float,
    max_match_distance: float | None,
) -> list[tuple[int, int]]:
    """Build a cost matrix for the given track/detection subset and run Hungarian.

    Returns the list of accepted (track_idx, detection_idx) matches in the
    *original* index space.
    """
    if not track_indices or not detection_indices:
        return []

    cost = np.full(
        (len(track_indices), len(detection_indices)), _INF, dtype=np.float64
    )
    for row, ti in enumerate(track_indices):
        pred = predictions[ti]
        track_label = tracks[ti].label
        for col, di in enumerate(detection_indices):
            if track_label != labels[di]:
                continue
            cost[row, col] = _pairwise_cost(
                pred.z_pred,
                pred.S,
                pred.pred_bbox,
                measurements[di],
                det_bboxes[di],
                pred.effective_gate,
                iou_floor,
                iou_cost_weight,
                max_match_distance,
            )

    row_ind, col_ind = linear_sum_assignment(cost)
    matches: list[tuple[int, int]] = []
    for row, col in zip(row_ind, col_ind):
        if cost[row, col] >= _INF:
            continue
        matches.append((track_indices[row], detection_indices[col]))
    return matches


def associate_detections_to_tracks(
    tracks: list[KalmanBoxTracker],
    measurements: list[np.ndarray],
    det_bboxes: list[tuple[float, float, float, float]],
    labels: list[int],
    params: KalmanParams = _DEFAULT_PARAMS,
    debounce_frames: int = 1,
    max_match_distance: float | None = None,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Associate detections to existing tracks via two-stage cascade.

    Stage 1: confirmed-and-fresh tracks (``time_since_update == 0`` and
    ``hit_streak >= debounce_frames``) get first pick of detections under the
    base IoU floor.

    Stage 2: every remaining track (unconfirmed or aged ghost) competes for
    leftover detections under a relaxed IoU floor; ghosts also benefit from
    the per-track ``effective_gate`` already scaled by ``time_since_update``
    in :func:`_predict_all`.

    Returns:
        matches: list of (track_idx, detection_idx) pairs
        unmatched_tracks: list of track indices
        unmatched_detections: list of detection indices
    """
    n_tracks = len(tracks)
    n_dets = len(measurements)

    if n_tracks == 0:
        return [], [], list(range(n_dets))
    if n_dets == 0:
        return [], list(range(n_tracks)), []

    predictions = _predict_all(tracks, params.mahalanobis_gate, params.ghost_gate_growth)

    stage1_tracks: list[int] = []
    stage2_tracks: list[int] = []
    for ti, track in enumerate(tracks):
        if track.time_since_update == 0 and track.hit_streak >= debounce_frames:
            stage1_tracks.append(ti)
        else:
            stage2_tracks.append(ti)

    all_dets = list(range(n_dets))

    stage1_matches = _solve_stage(
        stage1_tracks,
        all_dets,
        predictions,
        measurements,
        det_bboxes,
        labels,
        tracks,
        iou_floor=params.iou_floor,
        iou_cost_weight=params.iou_cost_weight,
        max_match_distance=max_match_distance,
    )

    matched_tracks: set[int] = {ti for ti, _ in stage1_matches}
    matched_dets: set[int] = {di for _, di in stage1_matches}

    stage2_dets = [di for di in all_dets if di not in matched_dets]

    stage2_matches = _solve_stage(
        stage2_tracks,
        stage2_dets,
        predictions,
        measurements,
        det_bboxes,
        labels,
        tracks,
        iou_floor=params.iou_floor * 0.5,
        iou_cost_weight=params.iou_cost_weight,
        max_match_distance=max_match_distance,
    )

    matches = stage1_matches + stage2_matches
    matched_tracks.update(ti for ti, _ in stage2_matches)
    matched_dets.update(di for _, di in stage2_matches)

    unmatched_tracks = [i for i in range(n_tracks) if i not in matched_tracks]
    unmatched_dets = [i for i in range(n_dets) if i not in matched_dets]

    return matches, unmatched_tracks, unmatched_dets
