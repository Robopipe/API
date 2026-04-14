import type {
  DetectionDisplayMode,
  MultiLimitDisplayMode,
} from "../../types";
import type { Label } from "../../types/label";
import { Sidebar } from "../../ui";

interface CounterSidebarProps {
  open: boolean;
  onClose: () => void;
  labels: Label[];
  selectedLabelId: number | null;
  onSelectLabel: (labelId: number) => void;
  displayMode: DetectionDisplayMode;
  onDisplayModeChange: (mode: DetectionDisplayMode) => void;
  multiLimitMode: MultiLimitDisplayMode;
  onMultiLimitModeChange: (mode: MultiLimitDisplayMode) => void;
}

const displayModeOptions: { value: DetectionDisplayMode; label: string }[] = [
  { value: "all", label: "All" },
  { value: "detections_only", label: "Detections only" },
  { value: "alerts", label: "Alerts" },
  { value: "alerts_and_warnings", label: "Alerts & Warnings" },
];

const multiLimitOptions: { value: MultiLimitDisplayMode; label: string }[] = [
  { value: "highest", label: "Highest severity" },
  { value: "show_all", label: "Show all" },
];

export const CounterSidebar = ({
  open,
  onClose,
  labels,
  selectedLabelId,
  onSelectLabel,
  displayMode,
  onDisplayModeChange,
  multiLimitMode,
  onMultiLimitModeChange,
}: CounterSidebarProps) => {
  return (
    <Sidebar open={open} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Count label
        </h3>
        {labels.map((label) => {
          const isActive = label.id === selectedLabelId;
          return (
            <button
              key={label.id}
              className={`w-full text-left px-4 py-3 rounded-xl transition-colors flex items-center gap-2 text-sm font-medium ${
                isActive
                  ? "bg-emerald-500/20 border border-emerald-500/50 cursor-default"
                  : "bg-gray-800 hover:bg-gray-700 border border-transparent cursor-pointer"
              }`}
              onClick={() => {
                onSelectLabel(label.id);
                onClose();
              }}
              disabled={isActive}
            >
              <span
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: label.color }}
              />
              <span>{label.name}</span>
            </button>
          );
        })}
        {labels.length === 0 && (
          <p className="text-gray-400 text-center py-4 text-sm">
            No labels available
          </p>
        )}
      </div>

      <div className="flex flex-col gap-2 mt-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Display mode
        </h3>
        {displayModeOptions.map((opt) => {
          const isActive = displayMode === opt.value;
          return (
            <button
              key={opt.value}
              className={`w-full text-left px-4 py-3 rounded-xl transition-colors text-sm font-medium ${
                isActive
                  ? "bg-emerald-500/20 border border-emerald-500/50 cursor-default"
                  : "bg-gray-800 hover:bg-gray-700 border border-transparent cursor-pointer"
              }`}
              onClick={() => onDisplayModeChange(opt.value)}
              disabled={isActive}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-2 mt-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Multiple limits
        </h3>
        {multiLimitOptions.map((opt) => {
          const isActive = multiLimitMode === opt.value;
          return (
            <button
              key={opt.value}
              className={`w-full text-left px-4 py-3 rounded-xl transition-colors text-sm font-medium ${
                isActive
                  ? "bg-emerald-500/20 border border-emerald-500/50 cursor-default"
                  : "bg-gray-800 hover:bg-gray-700 border border-transparent cursor-pointer"
              }`}
              onClick={() => onMultiLimitModeChange(opt.value)}
              disabled={isActive}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </Sidebar>
  );
};
