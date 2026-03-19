import { useCallback, useEffect, useState } from "react";
import { Container, type ContainerProps } from "../../ui";
import { useDetections } from "../../hooks/useDetections";
import { useAppState } from "../../provider";
import type { ThresholdStatus } from "../../types/detections";
import { DonutWidget } from "./DonutWidget";
import { WidgetConfig } from "./WidgetConfig";
import { loadWidgetSlots, type WidgetSlots } from "./widgetStorage";

export type WidgetsProps = ContainerProps;

export const Widgets = ({ className, ...props }: WidgetsProps) => {
  const { running } = useAppState();
  const [thresholdStatus, setThresholdStatus] =
    useState<ThresholdStatus | null>(null);
  const [widgetSlots, setWidgetSlots] = useState<WidgetSlots>(loadWidgetSlots);
  const [configOpen, setConfigOpen] = useState(false);

  const onDetections = useCallback(
    (detections: { threshold_status?: ThresholdStatus }) => {
      if (detections.threshold_status) {
        setThresholdStatus(detections.threshold_status);
      }
    },
    [],
  );

  useDetections({ onDetections, enabled: running });

  useEffect(() => {
    if (!running) return;
    fetch(`${window.DASHBOARD_CONFIG.apiBase}/dashboard/metrics`)
      .then((r) => r.json())
      .then((data) => {
        if (data && Object.keys(data).length > 0) {
          setThresholdStatus(data);
        }
      })
      .catch(() => {});
  }, [running]);

  const testCaseMap = window.DASHBOARD_CONFIG.testCases.reduce(
    (acc, tc) => {
      acc[tc.id] = tc;
      return acc;
    },
    {} as Record<string, (typeof window.DASHBOARD_CONFIG.testCases)[number]>,
  );

  const getThresholdDefaultColor = (
    tc: (typeof window.DASHBOARD_CONFIG.testCases)[number],
  ) => {
    if (!tc.thresholds?.length) return "#20a963";
    const sorted = [...tc.thresholds].sort((a, b) => a.value - b.value);
    return sorted[sorted.length - 1].color;
  };

  return (
    <Container className={`relative flex flex-col ${className || ""}`} {...props}>
      {/* Gear icon */}
      <button
        onClick={() => setConfigOpen(true)}
        className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors z-10"
        title="Configure widgets"
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </button>

      {/* Widget grid */}
      <div
        className="flex-1 grid gap-4 place-items-center"
        style={{
          gridTemplateColumns: `repeat(${widgetSlots.gridSize}, 1fr)`,
          gridTemplateRows: `repeat(${widgetSlots.gridSize}, 1fr)`,
        }}
      >
        {widgetSlots.slots.map((slot, index) => {
          if (!slot) return <div key={index} />;

          const tc = testCaseMap[slot.id];
          if (!tc) return <div key={index} />;

          return (
            <DonutWidget
              key={index}
              name={tc.name}
              status={thresholdStatus?.[slot.id] ?? null}
              displayMode={slot.mode}
              defaultColor={getThresholdDefaultColor(tc)}
            />
          );
        })}
      </div>

      {/* Config overlay */}
      {configOpen && (
        <WidgetConfig
          onClose={() => setConfigOpen(false)}
          slots={widgetSlots}
          onSlotsChange={setWidgetSlots}
          thresholdStatus={thresholdStatus}
        />
      )}
    </Container>
  );
};
