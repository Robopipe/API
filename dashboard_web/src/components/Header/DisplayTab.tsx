import { useState } from "react";
import { useAppState } from "../../provider";
import type {
  DetectionDisplayMode,
  MultiLimitDisplayMode,
} from "../../types";

const labels = window.DASHBOARD_CONFIG.labels;

const initialLabelThresholdDrafts = (): Record<number, string> => {
  const stored = window.DASHBOARD_CONFIG.labelConfidenceThresholds || {};
  const drafts: Record<number, string> = {};
  for (const [key, value] of Object.entries(stored)) {
    drafts[Number(key)] = String(value);
  }
  return drafts;
};

const buildThresholdMap = (
  drafts: Record<number, string>,
): Record<number, number> => {
  const next: Record<number, number> = {};
  for (const [key, raw] of Object.entries(drafts)) {
    const trimmed = raw.trim();
    if (trimmed === "") continue;
    const parsed = Number(trimmed);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > 1) continue;
    next[Number(key)] = parsed;
  }
  return next;
};

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

export const DisplayTab = () => {
  const {
    selectedLabelId,
    setSelectedLabelId,
    displayMode,
    setDisplayMode,
    multiLimitMode,
    setMultiLimitMode,
    hiddenLabelIds,
    toggleLabelVisibility,
    zoneVisible,
    setZoneVisible,
  } = useAppState();

  const [labelThresholdDrafts, setLabelThresholdDrafts] = useState<
    Record<number, string>
  >(initialLabelThresholdDrafts);

  const setLabelThresholdDraft = (labelId: number, raw: string) => {
    setLabelThresholdDrafts((prev) => ({ ...prev, [labelId]: raw }));
  };

  const commitLabelThreshold = async (labelId: number) => {
    const raw = (labelThresholdDrafts[labelId] ?? "").trim();
    if (raw !== "") {
      const parsed = Number(raw);
      if (Number.isNaN(parsed) || parsed < 0 || parsed > 1) {
        const stored = window.DASHBOARD_CONFIG.labelConfidenceThresholds || {};
        const fallback = stored[labelId];
        setLabelThresholdDrafts((prev) => ({
          ...prev,
          [labelId]: fallback !== undefined ? String(fallback) : "",
        }));
        return;
      }
    }

    const next = buildThresholdMap({
      ...labelThresholdDrafts,
      [labelId]: raw,
    });
    const current = window.DASHBOARD_CONFIG.labelConfidenceThresholds || {};
    if (JSON.stringify(current) === JSON.stringify(next)) return;

    try {
      const response = await fetch(
        `${window.DASHBOARD_CONFIG.apiBase}/dashboard/config`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ labelConfidenceThresholds: next }),
        },
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const body = await response.json();
      window.DASHBOARD_CONFIG.labelConfidenceThresholds =
        body.labelConfidenceThresholds ?? next;
    } catch (err) {
      console.error("Failed to save per-label confidence threshold", err);
    }
  };

  const globalThresholdPlaceholder = String(
    window.DASHBOARD_CONFIG.confidenceThreshold,
  );

  return (
    <div className="flex flex-col">
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Labels
        </h3>
        <p className="text-xs text-gray-500 mb-1">
          Eye: toggle visibility. Row: pick counted label. Number: per-label
          confidence threshold (blank uses global).
        </p>
        {labels.map((label) => {
          const isVisible = !hiddenLabelIds.has(label.id);
          const isCounted = label.id === selectedLabelId;
          return (
            <div key={label.id} className="flex items-stretch gap-2">
              <button
                className="w-10 shrink-0 rounded-xl bg-gray-800 hover:bg-gray-700 border border-transparent text-gray-300 transition-colors cursor-pointer flex items-center justify-center"
                onClick={() => toggleLabelVisibility(label.id)}
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
                onClick={() => setSelectedLabelId(label.id)}
                disabled={isCounted}
              >
                <span
                  className="w-3 h-3 rounded-full shrink-0"
                  style={{ backgroundColor: label.color }}
                />
                <span className="truncate">{label.name}</span>
              </button>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                placeholder={globalThresholdPlaceholder}
                value={labelThresholdDrafts[label.id] ?? ""}
                onChange={(e) =>
                  setLabelThresholdDraft(label.id, e.target.value)
                }
                onBlur={() => commitLabelThreshold(label.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    (e.target as HTMLInputElement).blur();
                  }
                }}
                className="w-20 shrink-0 px-2 py-2 bg-gray-800 border border-gray-600 rounded-xl text-white text-sm focus:outline-none focus:border-emerald-500"
                title="Per-label confidence threshold (blank = use global)"
              />
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
              onClick={() => setDisplayMode(opt.value)}
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
              onClick={() => setMultiLimitMode(opt.value)}
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
              onClick={() => setZoneVisible(opt.value)}
              disabled={isActive}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};
