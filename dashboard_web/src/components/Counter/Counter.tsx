import { useState } from "react";
import { useDetections } from "../../hooks/useDetections";
import { useAppState } from "../../provider";
import { GearIcon } from "../../ui";
import {
  collectViolations,
  countBySeverity,
} from "../../utils/collectViolations";
import { loadSelectedLabel, saveSelectedLabel } from "./counterStorage";
import { CounterSidebar } from "./CounterSidebar";

const labels = window.DASHBOARD_CONFIG.labels;
const configId = window.DASHBOARD_CONFIG.configId;

function getInitialLabelId(): number | null {
  const saved = loadSelectedLabel(configId);
  if (saved !== null && labels.some((l) => l.id === saved)) return saved;
  return labels.length > 0 ? labels[0].id : null;
}

export const Counter = () => {
  const {
    running,
    testCaseMap,
    displayMode,
    setDisplayMode,
    multiLimitMode,
    setMultiLimitMode,
  } = useAppState();
  const [count, setCount] = useState(0);
  const [warnings, setWarnings] = useState(0);
  const [alerts, setAlerts] = useState(0);
  const [selectedLabelId, setSelectedLabelId] = useState<number | null>(
    getInitialLabelId,
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [popoverVisible, setPopoverVisible] = useState(false);

  useDetections({
    onDetections: (detections) => {
      if (detections.counters && selectedLabelId !== null) {
        setCount(detections.counters[String(selectedLabelId)] ?? 0);
      } else {
        setCount(0);
      }

      const { alerts, warnings } = countBySeverity(
        collectViolations(detections, testCaseMap),
      );
      setWarnings(warnings);
      setAlerts(alerts);
    },
    enabled: running,
  });

  const selectedLabel = labels.find((l) => l.id === selectedLabelId);

  const handleSelectLabel = (labelId: number) => {
    setSelectedLabelId(labelId);
    saveSelectedLabel(configId, labelId);
  };

  if (!running) return null;

  return (
    <>
      <div className="flex justify-evenly font-mono text-2xl">
        <span
          className="relative flex items-center gap-2"
          onMouseEnter={() => setPopoverVisible(true)}
          onMouseLeave={() => setPopoverVisible(false)}
        >
          <span>{count} PCS</span>
          <button
            className="text-gray-400 hover:text-white transition-colors"
            onClick={() => setSidebarOpen((prev) => !prev)}
          >
            <GearIcon size={16} />
          </button>
          {popoverVisible && (
            <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 whitespace-nowrap bg-gray-800 text-gray-200 text-sm px-3 py-2 rounded-lg border border-gray-700 shadow-lg z-50">
              Counting: {selectedLabel?.name ?? "Unknown"}
            </div>
          )}
        </span>
        <span className="text-pear-500/80">{warnings} WARNINGS</span>
        <span className="text-red-500/80">{alerts} ALERTS</span>
      </div>

      <CounterSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        labels={labels}
        selectedLabelId={selectedLabelId}
        onSelectLabel={handleSelectLabel}
        displayMode={displayMode}
        onDisplayModeChange={setDisplayMode}
        multiLimitMode={multiLimitMode}
        onMultiLimitModeChange={setMultiLimitMode}
      />
    </>
  );
};
