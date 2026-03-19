import type { TestCase } from "../../types/dashboard";
import type { ThresholdStatus } from "../../types/detections";
import { DonutWidget } from "./DonutWidget";
import {
  MAX_GRID_SIZE,
  MIN_GRID_SIZE,
  resizeSlots,
  saveWidgetSlots,
  type WidgetDisplayMode,
  type WidgetSlots,
} from "./widgetStorage";

export interface WidgetConfigProps {
  onClose: () => void;
  slots: WidgetSlots;
  onSlotsChange: (slots: WidgetSlots) => void;
  thresholdStatus: ThresholdStatus | null;
}

const DISPLAY_MODES: { value: WidgetDisplayMode; label: string }[] = [
  { value: "failures", label: "Failures" },
  { value: "pass_rate", label: "Pass rate" },
  { value: "failures_of_total", label: "Failures / total" },
];

export const WidgetConfig = ({
  onClose,
  slots,
  onSlotsChange,
  thresholdStatus,
}: WidgetConfigProps) => {
  const testCases = window.DASHBOARD_CONFIG.testCases.filter(
    (tc) => tc.thresholds.length > 0,
  );

  const addToSlot = (testCaseId: string) => {
    const emptyIndex = slots.slots.indexOf(null);
    if (emptyIndex === -1) return;
    const newSlots = [...slots.slots];
    newSlots[emptyIndex] = { id: testCaseId, mode: "failures" };
    const updated: WidgetSlots = { gridSize: slots.gridSize, slots: newSlots };
    onSlotsChange(updated);
    saveWidgetSlots(updated);
  };

  const removeFromSlot = (index: number) => {
    const newSlots = [...slots.slots];
    newSlots[index] = null;
    const updated: WidgetSlots = { gridSize: slots.gridSize, slots: newSlots };
    onSlotsChange(updated);
    saveWidgetSlots(updated);
  };

  const setSlotMode = (index: number, mode: WidgetDisplayMode) => {
    const slot = slots.slots[index];
    if (!slot) return;
    const newSlots = [...slots.slots];
    newSlots[index] = { ...slot, mode };
    const updated: WidgetSlots = { gridSize: slots.gridSize, slots: newSlots };
    onSlotsChange(updated);
    saveWidgetSlots(updated);
  };

  const changeGridSize = (size: number) => {
    const updated = resizeSlots(slots, size);
    onSlotsChange(updated);
    saveWidgetSlots(updated);
  };

  const assignedIds = new Set(slots.slots.filter(Boolean).map((s) => s!.id));

  const getTestCase = (id: string): TestCase | undefined =>
    testCases.find((tc) => tc.id === id);

  const getThresholdDefaultColor = (tc: TestCase) => {
    if (!tc.thresholds?.length) return "#20a963";
    const sorted = [...tc.thresholds].sort((a, b) => a.value - b.value);
    return sorted[sorted.length - 1].color;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-900 rounded-2xl p-6 w-[800px] max-h-[90vh] overflow-auto">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-white">Configure Widgets</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Grid size selector */}
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm text-gray-400">Grid size:</span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => changeGridSize(slots.gridSize - 1)}
              disabled={slots.gridSize <= MIN_GRID_SIZE}
              className="w-7 h-7 rounded-lg bg-gray-800 text-gray-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-lg leading-none"
            >
              −
            </button>
            <span className="w-16 text-center text-sm text-white font-medium">
              {slots.gridSize}×{slots.gridSize}
            </span>
            <button
              onClick={() => changeGridSize(slots.gridSize + 1)}
              disabled={slots.gridSize >= MAX_GRID_SIZE}
              className="w-7 h-7 rounded-lg bg-gray-800 text-gray-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-lg leading-none"
            >
              +
            </button>
          </div>
        </div>

        <div className="flex gap-6">
          {/* Left sidebar: available test cases */}
          <div className="w-48 shrink-0 flex flex-col gap-3">
            {testCases.map((tc) => (
              <button
                key={tc.id}
                disabled={assignedIds.has(tc.id)}
                onClick={() => addToSlot(tc.id)}
                className={`flex flex-col items-center p-3 rounded-xl border transition-colors ${
                  assignedIds.has(tc.id)
                    ? "border-gray-700 opacity-40 cursor-not-allowed"
                    : "border-gray-700 hover:border-gray-500 cursor-pointer"
                }`}
              >
                <DonutWidget
                  name={tc.name}
                  status={thresholdStatus?.[tc.id] ?? null}
                  defaultColor={getThresholdDefaultColor(tc)}
                />
              </button>
            ))}
          </div>

          {/* Right: dynamic grid */}
          <div
            className="flex-1 grid gap-4"
            style={{
              gridTemplateColumns: `repeat(${slots.gridSize}, 1fr)`,
              gridTemplateRows: `repeat(${slots.gridSize}, 1fr)`,
            }}
          >
            {slots.slots.map((slot, index) => {
              if (slot) {
                const tc = getTestCase(slot.id);
                return (
                  <div
                    key={index}
                    className="relative flex flex-col items-center justify-center p-4 rounded-xl border border-gray-700 bg-gray-800/50"
                  >
                    <button
                      onClick={() => removeFromSlot(index)}
                      className="absolute top-2 right-2 text-gray-400 hover:text-white text-lg leading-none"
                    >
                      &times;
                    </button>
                    <DonutWidget
                      name={tc?.name ?? "Unknown"}
                      status={thresholdStatus?.[slot.id] ?? null}
                      displayMode={slot.mode}
                      defaultColor={tc ? getThresholdDefaultColor(tc) : undefined}
                    />
                    {/* Display mode selector */}
                    <div className="flex gap-1 mt-3">
                      {DISPLAY_MODES.map(({ value, label }) => (
                        <button
                          key={value}
                          onClick={() => setSlotMode(index, value)}
                          title={label}
                          className={`px-2 py-1 rounded text-xs transition-colors ${
                            slot.mode === value
                              ? "bg-blue-600 text-white"
                              : "bg-gray-700 text-gray-400 hover:text-white"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              }

              return (
                <div
                  key={index}
                  className="flex flex-col items-center justify-center p-4 rounded-xl border border-dashed border-gray-600 text-gray-500"
                >
                  <span className="text-3xl mb-1">+</span>
                  <span className="text-sm">Add chart</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
