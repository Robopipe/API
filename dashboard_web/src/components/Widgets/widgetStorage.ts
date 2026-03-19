export const GRID_OPTIONS = [2, 3, 4] as const;
export type GridSize = (typeof GRID_OPTIONS)[number];

const DEFAULT_GRID_SIZE: GridSize = 3;
const STORAGE_KEY = "robopipe_widget_config";

export interface WidgetSlots {
  gridSize: GridSize;
  slots: (string | null)[];
}

function slotCount(gridSize: GridSize): number {
  return gridSize * gridSize;
}

export function loadWidgetSlots(): WidgetSlots {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      const gs: GridSize = GRID_OPTIONS.includes(parsed.gridSize)
        ? parsed.gridSize
        : DEFAULT_GRID_SIZE;
      const count = slotCount(gs);
      if (Array.isArray(parsed.slots)) {
        const slots = parsed.slots.slice(0, count);
        while (slots.length < count) slots.push(null);
        return { gridSize: gs, slots };
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
  newSize: GridSize,
): WidgetSlots {
  const count = slotCount(newSize);
  const slots = current.slots.slice(0, count);
  while (slots.length < count) slots.push(null);
  return { gridSize: newSize, slots };
}

export function saveWidgetSlots(config: WidgetSlots) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}
