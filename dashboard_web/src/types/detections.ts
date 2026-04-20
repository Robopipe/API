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
  masks?: number[][];
  dashboard_detections?: DashboardDetection[];
  violation_event_ids?: number[];
  threshold_status?: ThresholdStatus;
  master_threshold_status?: ThresholdTestCaseStatus;
  counters?: Record<string, number>;
  seq?: number;
};
