export interface Detection {
  label: number;
  confidence: number;
}

export type ClassificationDetection = Detection;

export interface DetectionViolation {
  limit_name: string;
  severity: "ALERT" | "WARNING";
}

export interface BBDetection extends Detection {
  /* Bounding box coordinates: [xmin, ymin, xmax, ymax] */
  coords: [number, number, number, number];
  violations?: DetectionViolation[];
  tracking_id?: number;
  display_id?: number;
  /** "parent" = violation subject (shows limit names); "child" = highlighted target (shows label name). */
  role?: "parent" | "child";
  /** Max severity across all violations touching this box. Drives highlight color. */
  severity?: "ALERT" | "WARNING";
}

export type SegmentationDetection = BBDetection;

export type NNDetection =
  | ClassificationDetection
  | BBDetection
  | SegmentationDetection;

export interface DashboardDetection {
  test_case_id: string;
  type: "ALERT" | "WARNING";
}

export interface ThresholdTestCaseStatus {
  total: number;
  failures: number;
  pass_rate: number;
  zone_name: string;
  zone_color: string;
  is_best_zone: boolean;
}

export type ThresholdStatus = Record<string, ThresholdTestCaseStatus>;

export type ProductMatchState =
  | "calibrating"
  | "ok"
  | "starved"
  | "mismatch"
  | "snoozed";

/** Product-switch monitor status; present only when the feature is enabled
 * and a run is active. */
export interface ProductMatchStatus {
  state: ProductMatchState;
  /** calibrating only */
  calibrated?: number;
  calibration_target?: number;
  /** post-calibration; null until the judgment window is full */
  score?: number | null;
  threshold?: number;
  /** mismatch only — absolute wall-clock deadline of the auto-stop */
  deadline_epoch_ms?: number;
  /** mismatch only — server-computed remaining seconds (skew-free) */
  deadline_in_s?: number;
  /** mismatch only — full alarm duration stamped at alarm time; the 100%
   * reference for the auto-stop progress fill */
  total_in_s?: number;
  /**
   * Client-side only (not on the wire): skew-corrected deadline in local
   * epoch ms, anchored once per alarm by useProductMatch so the rendered
   * countdown never jitters with per-message network latency.
   */
  deadlineAtMs?: number;
  /** snoozed only */
  snooze_remaining_commits?: number;
  snooze_remaining_s?: number;
}

export type NNDetections = {
  detections: NNDetection[];
  /**
   * Legacy nested-int representation of the segmentation mask. Kept for
   * backward compatibility; new builds emit masks_png instead.
   */
  masks?: number[][];
  /**
   * Compact PNG-encoded segmentation mask, base64. Single-channel uint8
   * where pixel value 0 means background and N means detections[N - 1].
   * Decoded to maskBitmap by the detections manager before being
   * dispatched to subscribers.
   */
  masks_png?: string;
  mask_width?: number;
  mask_height?: number;
  dashboard_detections?: DashboardDetection[];
  threshold_status?: ThresholdStatus;
  master_threshold_status?: ThresholdTestCaseStatus;
  counters?: Record<string, number>;
  product_match?: ProductMatchStatus;
  /**
   * Whether a dashboard run is active on the backend. Flipping to false
   * mid-stream signals a backend-initiated stop (product-switch auto-stop).
   */
  running?: boolean;
  /**
   * DepthAI sequence number. Stable per session, but parser nodes may
   * renumber — prefer `ts_us` for matching.
   */
  seq?: number;
  /**
   * Source-frame device timestamp (microseconds since device boot).
   * Used as the join key against the timestamp burned into the WebRTC
   * video stream.
   */
  ts_us?: number;
  /**
   * Transient client-side cache of the decoded PNG. Not on the wire.
   * Lifetime is owned by whichever consumer received it; closed after
   * rendering.
   */
  maskBitmap?: ImageBitmap;
};
