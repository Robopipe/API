import type { Label } from "./label";

export enum DashboardZoneDirection {
  LeftToRight = "LEFT_TO_RIGHT",
  RightToLeft = "RIGHT_TO_LEFT",
  TopToBottom = "TOP_TO_BOTTOM",
  BottomToTop = "BOTTOM_TO_TOP",
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
  enabled: boolean;
  thresholds: EvalThreshold[];
}

export type DetectionDisplayMode = "all" | "alerts" | "alerts_and_warnings" | "detections_only";

export type MultiLimitDisplayMode = "highest" | "show_all";

export type WidgetDisplayMode = "failures" | "pass_rate" | "failures_of_total";

export type MasterDisplayMode = "zone" | "grade";

export type TimerLabelDisplay = "project_name" | "dashboard_name" | "nothing";

export interface WidgetSlot {
  id: string;
  mode: WidgetDisplayMode;
}

export interface WidgetConfig {
  gridSize: number;
  slots: (WidgetSlot | null)[];
  masterVisible: boolean;
  masterDisplayMode: MasterDisplayMode;
}

export interface UserSettings {
  displayMode: DetectionDisplayMode;
  multiLimitMode: MultiLimitDisplayMode;
  hiddenLabelIds: number[];
  zoneVisible: boolean;
  selectedLabelId: number | null;
  widgetConfig: WidgetConfig | null;
  timerLabelDisplay: TimerLabelDisplay;
  videoPanelWidthPct?: number;
  overlayScale?: number;
}

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
  labelConfidenceThresholds: Record<number, number>;
  debounceFrames: number;
  maxMissingFrames: number;
  maxMatchDistance: number;
  running: boolean;
  runningSince: string | null;
  /** Per-dashboard product-switch monitoring opt-in. */
  productCheckEnabled: boolean;
  productCheckAlarmSeconds: number;
  productCheckCalibrationCount: number;
  productCheckWindowSize: number;
  productCheckDivergenceThreshold: number;
  productCheckSnoozeCommits: number;
  productCheckSnoozeSeconds: number;
  productCheckStarvationMultiplier: number;
  productCheckIdleTimeoutSeconds: number;
  hasMultipleConfigs: boolean;
  awaitingModel: boolean;
  userSettings: UserSettings;
  settingsUnlock: string;
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
