import type { UserSettings } from "../types";

export function getUserSettings(): UserSettings {
  return window.DASHBOARD_CONFIG.userSettings;
}

export function saveUserSettings(next: UserSettings): void {
  window.DASHBOARD_CONFIG.userSettings = next;
  fetch(`${window.DASHBOARD_CONFIG.apiBase}/dashboard/user-settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(next),
  }).catch((err) => {
    console.error("Failed to save user settings", err);
  });
}

export function updateUserSettings(patch: Partial<UserSettings>): void {
  saveUserSettings({ ...getUserSettings(), ...patch });
}
