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
  item_id: number;
  type: string;
}

export type NNDetections = {
  detections: NNDetection[];
  masks?: number[][];
  dashboard_detections?: DashboardDetection[];
};
