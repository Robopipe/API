import type { Label } from "./label";

export interface DashboardItem {
  id: number;
  name: string;
  severity: "ALERT" | "WARNING";
}

export interface DashboardConfig {
  apiBase: string;
  labels: Label[];
  dashboardItems: DashboardItem[];
}
