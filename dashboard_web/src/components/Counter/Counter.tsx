import { useState } from "react";
import { useDetections } from "../../hooks/useDetections";
import { useAppState } from "../../provider";
import {
  collectViolations,
  countBySeverity,
} from "../../utils/collectViolations";

const labels = window.DASHBOARD_CONFIG.labels;

export const Counter = () => {
  const { running, testCaseMap, selectedLabelId } = useAppState();
  const [count, setCount] = useState(0);
  const [warnings, setWarnings] = useState(0);
  const [alerts, setAlerts] = useState(0);
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

  if (!running) return null;

  return (
    <div className="flex justify-evenly font-mono text-2xl">
      <span
        className="relative flex items-center gap-2"
        onMouseEnter={() => setPopoverVisible(true)}
        onMouseLeave={() => setPopoverVisible(false)}
      >
        <span>{count} PCS</span>
        {popoverVisible && (
          <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 whitespace-nowrap bg-gray-800 text-gray-200 text-sm px-3 py-2 rounded-lg border border-gray-700 shadow-lg z-50">
            Counting: {selectedLabel?.name ?? "Unknown"}
          </div>
        )}
      </span>
      <span className="text-pear-500/80">{warnings} WARNINGS</span>
      <span className="text-red-500/80">{alerts} ALERTS</span>
    </div>
  );
};
