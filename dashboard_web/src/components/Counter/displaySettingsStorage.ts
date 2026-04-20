import type { DetectionDisplayMode, MultiLimitDisplayMode } from "../../types";

function displayModeKey(configId: number): string {
  return `robopipe_display_mode_${configId}`;
}

function multiLimitKey(configId: number): string {
  return `robopipe_multi_limit_${configId}`;
}

function hiddenLabelsKey(configId: number): string {
  return `robopipe_hidden_labels_${configId}`;
}

function zoneVisibleKey(configId: number): string {
  return `robopipe_zone_visible_${configId}`;
}

const VALID_DISPLAY_MODES: DetectionDisplayMode[] = [
  "all",
  "detections_only",
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

export function loadHiddenLabelIds(configId: number): Set<number> {
  try {
    const raw = localStorage.getItem(hiddenLabelsKey(configId));
    if (raw === null) return new Set();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    const ids = parsed.filter((v): v is number => typeof v === "number");
    return new Set(ids);
  } catch {
    return new Set();
  }
}

export function saveHiddenLabelIds(
  configId: number,
  ids: Set<number>,
): void {
  localStorage.setItem(hiddenLabelsKey(configId), JSON.stringify([...ids]));
}

export function loadZoneVisible(configId: number): boolean {
  try {
    const raw = localStorage.getItem(zoneVisibleKey(configId));
    if (raw === "true") return true;
    if (raw === "false") return false;
  } catch {
    // fall through to default
  }
  return true;
}

export function saveZoneVisible(configId: number, visible: boolean): void {
  localStorage.setItem(zoneVisibleKey(configId), String(visible));
}
