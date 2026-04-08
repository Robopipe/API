export type TimerLabelDisplay = "project_name" | "dashboard_name" | "nothing";

const STORAGE_KEY = "robopipe_timer_label_display";
const DEFAULT_DISPLAY: TimerLabelDisplay = "project_name";
const VALID_VALUES: TimerLabelDisplay[] = [
  "project_name",
  "dashboard_name",
  "nothing",
];

export function loadTimerLabelDisplay(): TimerLabelDisplay {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw && VALID_VALUES.includes(raw as TimerLabelDisplay)) {
      return raw as TimerLabelDisplay;
    }
    return DEFAULT_DISPLAY;
  } catch {
    return DEFAULT_DISPLAY;
  }
}

export function saveTimerLabelDisplay(value: TimerLabelDisplay): void {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // silently fail
  }
}
