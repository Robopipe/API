export const MIN_GRID_SIZE = 1;
export const MAX_GRID_SIZE = 8;
const DEFAULT_GRID_SIZE = 3;

function storageKey(configId: number): string {
  return `robopipe_widget_config_${configId}`;
}

export type WidgetDisplayMode = "failures" | "pass_rate" | "failures_of_total";
export type MasterDisplayMode = "zone" | "grade";

export interface WidgetSlot {
  id: string;
  mode: WidgetDisplayMode;
}

export interface WidgetSlots {
  gridSize: number;
  slots: (WidgetSlot | null)[];
  masterVisible?: boolean;
  masterDisplayMode?: MasterDisplayMode;
}

function slotCount(gridSize: number): number {
  return gridSize * gridSize;
}

function clampGridSize(value: unknown): number {
  const n = typeof value === "number" ? value : DEFAULT_GRID_SIZE;
  return Math.min(MAX_GRID_SIZE, Math.max(MIN_GRID_SIZE, Math.round(n)));
}

function normalizeSlot(raw: unknown): WidgetSlot | null {
  if (raw === null || raw === undefined) return null;
  // Migrate from old format where slots were plain strings (test case IDs)
  if (typeof raw === "string") return { id: raw, mode: "failures" };
  if (typeof raw === "object" && raw !== null && "id" in raw) {
    return raw as WidgetSlot;
  }
  return null;
}

export function loadWidgetSlots(configId: number): WidgetSlots {
  try {
    const raw = localStorage.getItem(storageKey(configId));
    if (raw) {
      const parsed = JSON.parse(raw);
      const gs = clampGridSize(parsed.gridSize);
      const count = slotCount(gs);
      if (Array.isArray(parsed.slots)) {
        const slots = parsed.slots.slice(0, count).map(normalizeSlot);
        while (slots.length < count) slots.push(null);
        return {
          gridSize: gs,
          slots,
          masterVisible: parsed.masterVisible ?? true,
          masterDisplayMode: parsed.masterDisplayMode ?? "zone",
        };
      }
    }
  } catch {
    // ignore
  }
  return {
    gridSize: DEFAULT_GRID_SIZE,
    slots: Array(slotCount(DEFAULT_GRID_SIZE)).fill(null),
  };
}

export function resizeSlots(
  current: WidgetSlots,
  newSize: number,
): WidgetSlots {
  const gs = clampGridSize(newSize);
  const count = slotCount(gs);
  const slots = current.slots.slice(0, count);
  while (slots.length < count) slots.push(null);
  return {
    gridSize: gs,
    slots,
    masterVisible: current.masterVisible,
    masterDisplayMode: current.masterDisplayMode,
  };
}

export function saveWidgetSlots(configId: number, config: WidgetSlots) {
  localStorage.setItem(storageKey(configId), JSON.stringify(config));
}
