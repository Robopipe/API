function storageKey(configId: number): string {
  return `robopipe_counter_label_${configId}`;
}

export function loadSelectedLabel(configId: number): number | null {
  try {
    const raw = localStorage.getItem(storageKey(configId));
    if (raw === null) return null;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveSelectedLabel(configId: number, labelId: number): void {
  localStorage.setItem(storageKey(configId), String(labelId));
}
