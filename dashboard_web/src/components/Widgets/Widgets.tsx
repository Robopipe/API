import { useCallback, useEffect, useState } from "react";
import { Container, type ContainerProps, GearIcon } from "../../ui";
import { useDetections } from "../../hooks/useDetections";
import { useAppState } from "../../provider";
import type { ThresholdStatus } from "../../types/detections";
import { DonutWidget } from "./DonutWidget";
import { GridSizeSelector } from "./GridSizeSelector";
import { WidgetSidebar } from "./WidgetSidebar";
import {
  loadWidgetSlots,
  resizeSlots,
  saveWidgetSlots,
  type WidgetDisplayMode,
  type WidgetSlots,
} from "./widgetStorage";

const DISPLAY_MODES: { value: WidgetDisplayMode; label: string }[] = [
  { value: "failures", label: "Failures" },
  { value: "pass_rate", label: "Pass rate" },
  { value: "failures_of_total", label: "F / total" },
];

const configId = window.DASHBOARD_CONFIG.configId;

export type WidgetsProps = ContainerProps;

export const Widgets = ({ className, ...props }: WidgetsProps) => {
  const { running } = useAppState();
  const [thresholdStatus, setThresholdStatus] =
    useState<ThresholdStatus | null>(null);
  const [widgetSlots, setWidgetSlots] = useState<WidgetSlots>(() =>
    loadWidgetSlots(configId),
  );
  const [editMode, setEditMode] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedSlotIndex, setSelectedSlotIndex] = useState<number | null>(
    null,
  );

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
        if (
          data &&
          data.threshold_status &&
          Object.keys(data.threshold_status).length > 0
        ) {
          setThresholdStatus(data.threshold_status);
        }
      })
      .catch(() => {});
  }, [running]);

  // Escape key: close sidebar first, then exit edit mode
  useEffect(() => {
    if (!editMode) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (sidebarOpen) {
          setSidebarOpen(false);
          setSelectedSlotIndex(null);
        } else {
          setEditMode(false);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [editMode, sidebarOpen]);

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

  const toggleEditMode = () => {
    if (editMode) {
      // Exiting edit mode: close sidebar too
      setSidebarOpen(false);
      setSelectedSlotIndex(null);
    }
    setEditMode((prev) => !prev);
  };

  const handleAddChartClick = (slotIndex: number) => {
    setSelectedSlotIndex(slotIndex);
    setSidebarOpen(true);
  };

  const handleSelectTestCase = (testCaseId: string) => {
    const targetIndex =
      selectedSlotIndex !== null
        ? selectedSlotIndex
        : widgetSlots.slots.indexOf(null);
    if (targetIndex === -1 || targetIndex >= widgetSlots.slots.length) return;

    const newSlots = [...widgetSlots.slots];
    newSlots[targetIndex] = { id: testCaseId, mode: "failures" };
    const updated: WidgetSlots = {
      gridSize: widgetSlots.gridSize,
      slots: newSlots,
    };
    setWidgetSlots(updated);
    saveWidgetSlots(configId, updated);
    setSidebarOpen(false);
    setSelectedSlotIndex(null);
  };

  const removeFromSlot = (index: number) => {
    const newSlots = [...widgetSlots.slots];
    newSlots[index] = null;
    const updated: WidgetSlots = {
      gridSize: widgetSlots.gridSize,
      slots: newSlots,
    };
    setWidgetSlots(updated);
    saveWidgetSlots(configId, updated);
  };

  const setSlotMode = (index: number, mode: WidgetDisplayMode) => {
    const slot = widgetSlots.slots[index];
    if (!slot) return;
    const newSlots = [...widgetSlots.slots];
    newSlots[index] = { ...slot, mode };
    const updated: WidgetSlots = {
      gridSize: widgetSlots.gridSize,
      slots: newSlots,
    };
    setWidgetSlots(updated);
    saveWidgetSlots(configId, updated);
  };

  const changeGridSize = (size: number) => {
    const updated = resizeSlots(widgetSlots, size);
    setWidgetSlots(updated);
    saveWidgetSlots(configId, updated);
    // Reset selected slot if it's out of bounds
    if (
      selectedSlotIndex !== null &&
      selectedSlotIndex >= updated.slots.length
    ) {
      setSelectedSlotIndex(null);
    }
  };

  const closeSidebar = () => {
    setSidebarOpen(false);
    setSelectedSlotIndex(null);
  };

  return (
    <Container
      className={`relative flex flex-col ${className || ""}`}
      {...props}
    >
      {/* Top bar */}
      <div className="flex items-center justify-between mb-3 shrink-0">
        <div>
          {editMode && (
            <GridSizeSelector
              gridSize={widgetSlots.gridSize}
              onChange={changeGridSize}
            />
          )}
        </div>
        <button
          onClick={toggleEditMode}
          className={`text-gray-400 hover:text-white transition-colors ${editMode ? "text-white" : ""}`}
          title="Configure widgets"
        >
          <GearIcon />
        </button>
      </div>

      {/* Widget grid */}
      <div
        className="flex-1 grid gap-4 place-items-center"
        style={{
          gridTemplateColumns: `repeat(${widgetSlots.gridSize}, 1fr)`,
          gridTemplateRows: `repeat(${widgetSlots.gridSize}, 1fr)`,
        }}
      >
        {widgetSlots.slots.map((slot, index) => {
          if (slot) {
            const tc = testCaseMap[slot.id];
            if (!tc) return <div key={index} />;

            return (
              <div key={index} className="relative flex flex-col items-center">
                {editMode && (
                  <button
                    onClick={() => removeFromSlot(index)}
                    className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-gray-700 hover:bg-red-600 text-gray-300 hover:text-white text-xs leading-none flex items-center justify-center transition-colors z-10"
                  >
                    &times;
                  </button>
                )}
                <DonutWidget
                  name={tc.name}
                  status={thresholdStatus?.[slot.id] ?? null}
                  displayMode={slot.mode}
                  defaultColor={getThresholdDefaultColor(tc)}
                />
                {editMode && (
                  <div className="flex gap-1 mt-2">
                    {DISPLAY_MODES.map(({ value, label }) => (
                      <button
                        key={value}
                        onClick={() => setSlotMode(index, value)}
                        title={label}
                        className={`px-2 py-0.5 rounded text-xs transition-colors ${
                          slot.mode === value
                            ? "bg-blue-600 text-white"
                            : "bg-gray-700 text-gray-400 hover:text-white"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          }

          // Empty slot
          if (editMode) {
            return (
              <button
                key={index}
                onClick={() => handleAddChartClick(index)}
                className={`flex flex-col items-center justify-center w-full h-full rounded-xl border border-dashed transition-colors ${
                  selectedSlotIndex === index
                    ? "border-blue-500 bg-blue-500/10 text-blue-400"
                    : "border-gray-600 text-gray-500 hover:border-gray-400 hover:text-gray-300"
                }`}
              >
                <span className="text-3xl mb-1">+</span>
                <span className="text-sm">Add chart</span>
              </button>
            );
          }

          return <div key={index} />;
        })}
      </div>

      {/* Sidebar */}
      <WidgetSidebar
        open={sidebarOpen}
        onClose={closeSidebar}
        onSelectTestCase={handleSelectTestCase}
        thresholdStatus={thresholdStatus}
      />
    </Container>
  );
};
