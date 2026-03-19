export interface Detection {
  label: number;
  confidence: number;
}

export type ClassificationDetection = Detection;

export interface BBDetection extends Detection {
  /* Bounding box coordinates: [xmin, ymin, xmax, ymax] */
  coords: [number, number, number, number];
}

export type SegmentationDetection = BBDetection;

export type NNDetection =
  | ClassificationDetection
  | BBDetection
  | SegmentationDetection;

export interface DashboardDetection {
  test_case_id: string;
  type: string;
}

export interface ThresholdTestCaseStatus {
  total: number;
  failures: number;
  pass_rate: number;
  zone_name: string;
  zone_color: string;
}

export type ThresholdStatus = Record<string, ThresholdTestCaseStatus>;

export type NNDetections = {
  detections: NNDetection[];
  masks?: number[][];
  dashboard_detections?: DashboardDetection[];
  threshold_status?: ThresholdStatus;
};
