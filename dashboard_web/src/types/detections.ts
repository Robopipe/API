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
  /**
   * Violations committed at zone-exit on this frame. Each entry pairs the
   * persisted event id with the tracker id whose dwell produced it, so the
   * client can attach an in-zone snapshot captured during dwell rather than
   * the post-exit frame the WS message was paired with.
   */
  violation_events?: { event_id: number; tracker_id: number }[];
  threshold_status?: ThresholdStatus;
  master_threshold_status?: ThresholdTestCaseStatus;
  counters?: Record<string, number>;
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
