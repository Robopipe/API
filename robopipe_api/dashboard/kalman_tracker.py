from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

# Chi-squared threshold for 4 DOF at 95% confidence
_MAHALANOBIS_GATE = 9.4877


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

    def __init__(self, measurement: np.ndarray, tracking_id: int, label: int) -> None:
        self.tracking_id = tracking_id
        self.label = label
        self.time_since_update = 0
        self.hit_streak = 0

        # State: [cx, cy, w, h, vx, vy]
        self._x = np.zeros(6, dtype=np.float64)
        self._x[:4] = measurement

        # Covariance — moderate uncertainty on unobserved velocity
        self._P = np.diag([1e-2, 1e-2, 1e-2, 1e-2, 1e-1, 1e-1])

        # Process noise
        self._Q = np.diag([1e-2, 1e-2, 1e-3, 1e-3, 1e-4, 1e-4])

        # Measurement noise
        self._R = np.diag([1e-2, 1e-2, 1e-2, 1e-2])

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


def associate_detections_to_tracks(
    tracks: list[KalmanBoxTracker],
    measurements: list[np.ndarray],
    labels: list[int],
    gate_threshold: float = _MAHALANOBIS_GATE,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Associate detections to existing tracks using the Hungarian algorithm.

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

    # Predict all tracks and cache results
    predictions: list[tuple[np.ndarray, np.ndarray]] = []
    for track in tracks:
        predictions.append(track.predict())

    # Build cost matrix
    INF = 1e9
    cost = np.full((n_tracks, n_dets), INF, dtype=np.float64)
    for ti, (z_pred, S) in enumerate(predictions):
        for di in range(n_dets):
            # Gate: labels must match
            if tracks[ti].label != labels[di]:
                continue
            dist = _mahalanobis_sq(z_pred, S, measurements[di])
            if dist <= gate_threshold:
                cost[ti, di] = dist

    # Hungarian assignment
    row_ind, col_ind = linear_sum_assignment(cost)

    matches: list[tuple[int, int]] = []
    matched_tracks: set[int] = set()
    matched_dets: set[int] = set()

    for ti, di in zip(row_ind, col_ind):
        if cost[ti, di] >= INF:
            continue
        matches.append((ti, di))
        matched_tracks.add(ti)
        matched_dets.add(di)

    unmatched_tracks = [i for i in range(n_tracks) if i not in matched_tracks]
    unmatched_dets = [i for i in range(n_dets) if i not in matched_dets]

    return matches, unmatched_tracks, unmatched_dets
