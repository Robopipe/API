import type { TestCase } from "../../types/dashboard";
import type { ThresholdStatus } from "../../types/detections";
import { DonutWidget } from "./DonutWidget";
import {
  GRID_OPTIONS,
  resizeSlots,
  saveWidgetSlots,
  type GridSize,
  type WidgetSlots,
} from "./widgetStorage";

export interface WidgetConfigProps {
  onClose: () => void;
  slots: WidgetSlots;
  onSlotsChange: (slots: WidgetSlots) => void;
  thresholdStatus: ThresholdStatus | null;
}

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
    newSlots[emptyIndex] = testCaseId;
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

  const changeGridSize = (size: GridSize) => {
    const updated = resizeSlots(slots, size);
    onSlotsChange(updated);
    saveWidgetSlots(updated);
  };

  const assignedIds = new Set(slots.slots.filter(Boolean));

  const getTestCase = (id: string): TestCase | undefined =>
    testCases.find((tc) => tc.id === id);

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
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm text-gray-400">Grid size:</span>
          {GRID_OPTIONS.map((size) => (
            <button
              key={size}
              onClick={() => changeGridSize(size)}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                slots.gridSize === size
                  ? "bg-gray-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {size}x{size}
            </button>
          ))}
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
            {slots.slots.map((slotId, index) => {
              if (slotId) {
                const tc = getTestCase(slotId);
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
                      status={thresholdStatus?.[slotId] ?? null}
                    />
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
