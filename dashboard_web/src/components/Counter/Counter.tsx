import { useState } from "react";
import { useDetections } from "../../hooks/useDetections";
import { useAppState } from "../../provider";

export const Counter = () => {
  const { running, dashboardItemMap } = useAppState();
  const [count, setCount] = useState(0);
  const [warnings, setWarnings] = useState(0);
  const [alerts, setAlerts] = useState(0);
  useDetections({
    onDetections: (detections) => {
      setCount(detections.detections.length);
      const { warnings, alerts } = detections.dashboard_detections?.reduce(
        (acc, d) => {
          if (dashboardItemMap[d.item_id]?.severity === "WARNING")
            acc.warnings += 1;
          if (dashboardItemMap[d.item_id]?.severity === "ALERT")
            acc.alerts += 1;
          return acc;
        },
        { warnings: 0, alerts: 0 },
      ) || { warnings: 0, alerts: 0 };
      setWarnings(warnings);
      setAlerts(alerts);
    },
    enabled: running,
  });

  if (!running) return null;

  return (
    <div className="flex justify-evenly font-mono text-2xl">
      <span>{count} PCS</span>
      <span className="text-pear-500/80">{warnings} WARNINGS</span>
      <span className="text-red-500/80">{alerts} ALERTS</span>
    </div>
  );
};
