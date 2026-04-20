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
  hiddenLabelIds: Set<number>;
  onToggleLabelVisibility: (labelId: number) => void;
  zoneVisible: boolean;
  onZoneVisibleChange: (visible: boolean) => void;
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

const zoneVisibleOptions: { value: boolean; label: string }[] = [
  { value: true, label: "Visible" },
  { value: false, label: "Hidden" },
];

const EyeIcon = () => (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const EyeOffIcon = () => (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a19.77 19.77 0 0 1 5.06-5.94" />
    <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a19.77 19.77 0 0 1-3.17 4.19" />
    <path d="M9.88 9.88a3 3 0 0 0 4.24 4.24" />
    <line x1="1" y1="1" x2="23" y2="23" />
  </svg>
);

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
  hiddenLabelIds,
  onToggleLabelVisibility,
  zoneVisible,
  onZoneVisibleChange,
}: CounterSidebarProps) => {
  return (
    <Sidebar open={open} onClose={onClose}>
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Labels
        </h3>
        <p className="text-xs text-gray-500 mb-1">
          Eye: toggle visibility. Row: pick counted label.
        </p>
        {labels.map((label) => {
          const isVisible = !hiddenLabelIds.has(label.id);
          const isCounted = label.id === selectedLabelId;
          return (
            <div key={label.id} className="flex items-stretch gap-2">
              <button
                className="w-10 shrink-0 rounded-xl bg-gray-800 hover:bg-gray-700 border border-transparent text-gray-300 transition-colors cursor-pointer flex items-center justify-center"
                onClick={() => onToggleLabelVisibility(label.id)}
                title={isVisible ? "Hide label" : "Show label"}
                aria-label={isVisible ? "Hide label" : "Show label"}
              >
                {isVisible ? <EyeIcon /> : <EyeOffIcon />}
              </button>
              <button
                className={`flex-1 min-w-0 text-left px-3 py-3 rounded-xl transition-colors flex items-center gap-2 text-sm font-medium ${
                  isCounted
                    ? "bg-emerald-500/20 border border-emerald-500/50 cursor-default"
                    : "bg-gray-800 hover:bg-gray-700 border border-transparent cursor-pointer"
                } ${!isVisible ? "opacity-50" : ""}`}
                onClick={() => onSelectLabel(label.id)}
                disabled={isCounted}
              >
                <span
                  className="w-3 h-3 rounded-full shrink-0"
                  style={{ backgroundColor: label.color }}
                />
                <span className="truncate">{label.name}</span>
              </button>
            </div>
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

      <div className="flex flex-col gap-2 mt-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Evaluation zone
        </h3>
        {zoneVisibleOptions.map((opt) => {
          const isActive = zoneVisible === opt.value;
          return (
            <button
              key={String(opt.value)}
              className={`w-full text-left px-4 py-3 rounded-xl transition-colors text-sm font-medium ${
                isActive
                  ? "bg-emerald-500/20 border border-emerald-500/50 cursor-default"
                  : "bg-gray-800 hover:bg-gray-700 border border-transparent cursor-pointer"
              }`}
              onClick={() => onZoneVisibleChange(opt.value)}
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
