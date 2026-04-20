import type { Label } from "./label";

export enum DashboardZoneDirection {
  HORIZONTAL = "HORIZONTAL",
  VERTICAL = "VERTICAL",
}

export interface EvalThreshold {
  id: string;
  name: string;
  value: number;
  color: string;
  testCaseId?: string;
}

export interface TestCase {
  id: string;
  name: string;
  severity: "ALERT" | "WARNING" | null;
  thresholds: EvalThreshold[];
}

export type DetectionDisplayMode = "all" | "alerts" | "alerts_and_warnings" | "detections_only";

export type MultiLimitDisplayMode = "highest" | "show_all";

export interface DashboardConfig {
  configId: number;
  name: string;
  projectName: string;
  apiBase: string;
  mxid: string;
  streamName: string;
  labels: Label[];
  testCases: TestCase[];
  thresholds: EvalThreshold[];
  zoneDirection: DashboardZoneDirection;
  zoneCenter: number;
  zoneThickness: number;
  optimistic: boolean;
  remoteBackendUrl?: string;
  confidenceThreshold: number;
  debounceFrames: number;
  maxMissingFrames: number;
  maxMatchDistance: number;
  running: boolean;
  runningSince: string | null;
  hasMultipleConfigs: boolean;
}

export interface StoredConfigSummary {
  config_id: number;
  config_name: string;
  project_name: string;
}

export interface DashboardConfigsResponse {
  active_config_id: number | null;
  configs: StoredConfigSummary[];
}
