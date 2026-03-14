import type { Label } from "./label";

export enum DashboardLineDirection {
  HORIZONTAL = "HORIZONTAL",
  VERTICAL = "VERTICAL",
}

export interface DashboardItem {
  id: number;
  name: string;
  severity: "ALERT" | "WARNING";
}

export interface DashboardConfig {
  apiBase: string;
  mxid: string;
  streamName: string;
  labels: Label[];
  dashboardItems: DashboardItem[];
  lineDirection: DashboardLineDirection;
  linePosition: number;
  remoteBackendUrl?: string;
}
