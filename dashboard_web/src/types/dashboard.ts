import type { Label } from "./label";

export enum DashboardLineDirection {
  HORIZONTAL = "HORIZONTAL",
  VERTICAL = "VERTICAL",
}

export enum DashboardLineFlow {
  POSITIVE = "POSITIVE",
  NEGATIVE = "NEGATIVE",
}

export interface EvalThreshold {
  id: string;
  name: string;
  value: number;
  color: string;
  testCaseId: string;
}

export interface TestCase {
  id: string;
  name: string;
  severity: "ALERT" | "WARNING";
  thresholds: EvalThreshold[];
}

export interface DashboardConfig {
  configId: number;
  apiBase: string;
  mxid: string;
  streamName: string;
  labels: Label[];
  testCases: TestCase[];
  lineDirection: DashboardLineDirection;
  linePosition: number;
  lineFlow: DashboardLineFlow;
  remoteBackendUrl?: string;
  running: boolean;
  hasMultipleConfigs: boolean;
}

export interface StoredConfigSummary {
  config_id: number;
  config_name: string;
}

export interface DashboardConfigsResponse {
  active_config_id: number | null;
  configs: StoredConfigSummary[];
}
