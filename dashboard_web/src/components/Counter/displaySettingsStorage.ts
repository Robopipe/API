import type { DetectionDisplayMode, MultiLimitDisplayMode } from "../../types";

function displayModeKey(configId: number): string {
  return `robopipe_display_mode_${configId}`;
}

function multiLimitKey(configId: number): string {
  return `robopipe_multi_limit_${configId}`;
}

const VALID_DISPLAY_MODES: DetectionDisplayMode[] = [
  "all",
  "alerts",
  "alerts_and_warnings",
];
const VALID_MULTI_LIMIT_MODES: MultiLimitDisplayMode[] = ["highest", "show_all"];

export function loadDisplayMode(configId: number): DetectionDisplayMode {
  try {
    const raw = localStorage.getItem(displayModeKey(configId));
    if (raw !== null && VALID_DISPLAY_MODES.includes(raw as DetectionDisplayMode))
      return raw as DetectionDisplayMode;
  } catch {}
  return "all";
}

export function saveDisplayMode(
  configId: number,
  mode: DetectionDisplayMode,
): void {
  localStorage.setItem(displayModeKey(configId), mode);
}

export function loadMultiLimitMode(configId: number): MultiLimitDisplayMode {
  try {
    const raw = localStorage.getItem(multiLimitKey(configId));
    if (
      raw !== null &&
      VALID_MULTI_LIMIT_MODES.includes(raw as MultiLimitDisplayMode)
    )
      return raw as MultiLimitDisplayMode;
  } catch {}
  return "highest";
}

export function saveMultiLimitMode(
  configId: number,
  mode: MultiLimitDisplayMode,
): void {
  localStorage.setItem(multiLimitKey(configId), mode);
}
