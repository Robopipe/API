import type { SettingsField } from "./SettingsModal";

// Bounds mirror the pydantic validation on DashboardConfigUpdate.
export const PRODUCT_CHECK_FIELDS: SettingsField[] = [
  {
    key: "productCheckAlarmSeconds",
    label: "Alarm Countdown",
    description: "Seconds before a mismatch alarm auto-stops the run",
    min: 3,
    max: 600,
    step: 1,
  },
  {
    key: "productCheckCalibrationCount",
    label: "Calibration Count",
    description: "Commits used to learn the run's detection baseline",
    min: 5,
    max: 500,
    step: 1,
    integer: true,
  },
  {
    key: "productCheckWindowSize",
    label: "Window Size",
    description: "Recent commits scored against the baseline",
    min: 5,
    max: 200,
    step: 1,
    integer: true,
  },
  {
    key: "productCheckDivergenceThreshold",
    label: "Divergence Threshold",
    description: "Score at which the mismatch alarm fires (0–1)",
    min: 0.01,
    max: 1,
    step: 0.01,
  },
  {
    key: "productCheckSnoozeCommits",
    label: "Snooze Commits",
    description: "Commits the alarm stays suppressed after Cancel",
    min: 1,
    max: 1000,
    step: 1,
    integer: true,
  },
  {
    key: "productCheckSnoozeSeconds",
    label: "Snooze Seconds",
    description: "Seconds the alarm stays suppressed after Cancel",
    min: 1,
    max: 3600,
    step: 1,
  },
  {
    key: "productCheckStarvationMultiplier",
    label: "Starvation Multiplier",
    description: "× typical product interval with no commit → starved banner",
    min: 1.1,
    max: 100,
    step: 0.1,
  },
  {
    key: "productCheckIdleTimeoutSeconds",
    label: "Idle Timeout",
    description:
      "Seconds without a commit before the idle warning shows; also the minimum for the learned timeout",
    min: 3,
    max: 600,
    step: 1,
  },
];
