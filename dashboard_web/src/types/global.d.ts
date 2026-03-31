import type { DashboardConfig } from "./dashboard";

declare global {
  interface Window {
    DASHBOARD_CONFIG: DashboardConfig;
  }
}
