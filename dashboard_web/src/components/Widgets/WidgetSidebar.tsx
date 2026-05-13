import type { ThresholdStatus } from "../../types/detections";
import { Sidebar } from "../../ui";
import { DonutWidget } from "./DonutWidget";

export interface WidgetSidebarProps {
  open: boolean;
  onClose: () => void;
  onSelectTestCase: (testCaseId: string) => void;
  thresholdStatus: ThresholdStatus | null;
}

export const WidgetSidebar = ({
  open,
  onClose,
  onSelectTestCase,
  thresholdStatus,
}: WidgetSidebarProps) => {
  const testCases = window.DASHBOARD_CONFIG.testCases.filter(
    (tc) => tc.thresholds.length > 0,
  );

  const getThresholdDefaultColor = (tc: (typeof testCases)[number]) => {
    if (!tc.thresholds?.length) return "#20a963";
    const sorted = [...tc.thresholds].sort((a, b) => a.value - b.value);
    return sorted[sorted.length - 1].color;
  };

  return (
    <Sidebar open={open} onClose={onClose}>
      <div className="flex flex-col items-center gap-6">
        {testCases.map((tc) => (
          <button
            key={tc.id}
            onClick={() => onSelectTestCase(tc.id)}
            className="flex flex-col items-center cursor-pointer hover:opacity-80 transition-opacity"
          >
            <DonutWidget
              name={tc.name}
              status={thresholdStatus?.[tc.id] ?? null}
              defaultColor={getThresholdDefaultColor(tc)}
              disabled={!tc.enabled}
            />
          </button>
        ))}
      </div>
    </Sidebar>
  );
};
