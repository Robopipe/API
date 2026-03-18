import type { Label } from "./label";

export enum DashboardLineDirection {
  HORIZONTAL = "HORIZONTAL",
  VERTICAL = "VERTICAL",
}

export enum DashboardLineFlow {
  POSITIVE = "POSITIVE",
  NEGATIVE = "NEGATIVE",
}

export interface TestCase {
  id: string;
  name: string;
  severity: "ALERT" | "WARNING";
}

export interface DashboardConfig {
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
}
