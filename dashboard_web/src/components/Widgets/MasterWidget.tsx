import type { ThresholdTestCaseStatus } from "../../types/detections";
import type { MasterDisplayMode } from "./widgetStorage";
import { computeGrade } from "./computeGrade";
import { DisplayModeSelector } from "./DisplayModeSelector";
import { DonutWidget } from "./DonutWidget";

const MASTER_DISPLAY_MODES: { value: MasterDisplayMode; label: string }[] = [
  { value: "zone", label: "Zone" },
  { value: "grade", label: "Grade" },
];

function getMasterDefaultColor(): string {
  const t = window.DASHBOARD_CONFIG.thresholds;
  if (!t?.length) return "#20a963";
  const sorted = [...t].sort((a, b) => a.value - b.value);
  return sorted[sorted.length - 1].color;
}

export interface MasterWidgetProps {
  status: ThresholdTestCaseStatus | null;
  visible: boolean;
  editMode: boolean;
  displayMode: MasterDisplayMode;
  onToggleVisible: () => void;
  onSetDisplayMode: (mode: MasterDisplayMode) => void;
}

export const MasterWidget = ({
  status,
  visible,
  editMode,
  displayMode,
  onToggleVisible,
  onSetDisplayMode,
}: MasterWidgetProps) => {
  const hasMasterThresholds =
    (window.DASHBOARD_CONFIG.thresholds?.length ?? 0) > 0;

  if (!hasMasterThresholds) return null;

  const primaryLabel =
    displayMode === "grade" && status
      ? computeGrade(
          status.pass_rate,
          window.DASHBOARD_CONFIG.thresholds,
        ).toFixed(2)
      : undefined;

  if (!visible) {
    if (!editMode) return null;
    return (
      <button
        onClick={onToggleVisible}
        className="mb-3 px-3 py-1.5 rounded-lg border border-dashed border-gray-600 text-gray-500 hover:border-gray-400 hover:text-gray-300 text-sm transition-colors shrink-0"
      >
        + Show Master Evaluation
      </button>
    );
  }

  return (
    <div className="relative flex flex-col items-center mb-4 shrink-0">
      {editMode && (
        <button
          onClick={onToggleVisible}
          className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-gray-700 hover:bg-red-600 text-gray-300 hover:text-white text-xs leading-none flex items-center justify-center transition-colors z-10"
        >
          &times;
        </button>
      )}
      <DonutWidget
        name="Master Evaluation"
        status={status}
        displayMode="pass_rate"
        defaultColor={getMasterDefaultColor()}
        size={200}
        strokeWidth={16}
        primaryLabel={primaryLabel}
      />
      {editMode && (
        <DisplayModeSelector
          modes={MASTER_DISPLAY_MODES}
          selected={displayMode}
          onChange={onSetDisplayMode}
        />
      )}
    </div>
  );
};
