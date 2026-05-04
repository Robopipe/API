import { useEffect, useState } from "react";
import { Container, type ContainerProps, GearIcon } from "../../ui";
import { useElementSize } from "../../hooks/useElementSize";
import { useAppState } from "../../provider";
import { getUserSettings, updateUserSettings } from "../../api/userSettings";
import type { MasterDisplayMode, WidgetConfig, WidgetDisplayMode } from "../../types";
import { DisplayModeSelector } from "./DisplayModeSelector";
import { DonutWidget } from "./DonutWidget";
import { GridSizeSelector } from "./GridSizeSelector";
import { MasterWidget } from "./MasterWidget";
import { useThresholdStatus } from "./useThresholdStatus";
import { WidgetSidebar } from "./WidgetSidebar";
import { MAX_GRID_SIZE, MIN_GRID_SIZE } from "./widgetStorage";

function resizeSlots(current: WidgetConfig, newSize: number): WidgetConfig {
  const gs = Math.min(MAX_GRID_SIZE, Math.max(MIN_GRID_SIZE, Math.round(newSize)));
  const count = gs * gs;
  const slots = current.slots.slice(0, count);
  while (slots.length < count) slots.push(null);
  return { ...current, gridSize: gs, slots };
}

const DISPLAY_MODES: { value: WidgetDisplayMode; label: string }[] = [
  { value: "failures", label: "Failures" },
  { value: "pass_rate", label: "Pass rate" },
  { value: "failures_of_total", label: "F / total" },
];

const GRID_GAP = 16; // gap-4
const MAX_DONUT_SIZE = 320;
const NAME_LABEL_THRESHOLD = 55;
const MASTER_MIN_SIZE = 140;
const MASTER_MAX_SIZE = 360;
const MASTER_OVER_GRID_RATIO = 1.25;
const MASTER_MAX_PANEL_RATIO = 0.45;
const PANEL_TOPBAR_H = 40;
const MASTER_FOOTER_H_VIEW = 52;
const MASTER_FOOTER_H_EDIT = 84;

interface ComputedSizes {
  donutSize: number;
  masterSize: number;
}

function labelReserveFor(d: number, editMode: boolean): number {
  if (editMode) return 64;
  if (d < NAME_LABEL_THRESHOLD) return 0;
  return 8 + Math.ceil(1.5 * Math.max(10, d * 0.095)) + 2;
}

function computeSizes(
  panelW: number,
  panelH: number,
  n: number,
  hasMaster: boolean,
  editMode: boolean,
): ComputedSizes {
  if (panelW <= 0 || panelH <= 0) return { donutSize: 0, masterSize: 0 };

  const cellWMax = Math.min(
    MAX_DONUT_SIZE,
    (panelW - GRID_GAP * (n - 1)) / n,
  );
  const gridVGap = GRID_GAP * (n - 1);
  const masterFooter = editMode ? MASTER_FOOTER_H_EDIT : MASTER_FOOTER_H_VIEW;
  // Account for the master's name label, which can extend up to 1.4 * size
  // (DonutWidget.tsx). Cap by panelW / 1.4 so the master + label fit horizontally.
  const widthCap = Math.max(0, panelW / 1.4);
  const masterCap = Math.min(
    MASTER_MAX_SIZE,
    panelH * MASTER_MAX_PANEL_RATIO,
    widthCap,
  );
  const masterBase = Math.min(
    MASTER_MAX_SIZE,
    Math.max(MASTER_MIN_SIZE, panelH * 0.25),
    widthCap,
  );
  const masterFloor = Math.min(MASTER_MIN_SIZE, masterCap);

  const solve = (labelReserve: number): ComputedSizes => {
    if (!hasMaster) {
      const cellH = (panelH - PANEL_TOPBAR_H - gridVGap) / n;
      let donutSize = Math.min(cellWMax, cellH - labelReserve);
      donutSize = donutSize < 24 ? 0 : Math.min(donutSize, MAX_DONUT_SIZE);
      return { donutSize: Math.round(donutSize), masterSize: 0 };
    }

    const heightBudget =
      panelH - PANEL_TOPBAR_H - masterFooter - gridVGap - n * labelReserve;
    const dEquality = heightBudget / (n + MASTER_OVER_GRID_RATIO);
    const mEquality = dEquality * MASTER_OVER_GRID_RATIO;

    let masterSize: number;
    let donutSize: number;

    if (mEquality >= masterCap) {
      masterSize = masterCap;
      const cellH =
        (panelH - PANEL_TOPBAR_H - masterSize - masterFooter - gridVGap) / n;
      donutSize = cellH - labelReserve;
    } else if (mEquality <= masterBase) {
      masterSize = masterBase;
      const cellH =
        (panelH - PANEL_TOPBAR_H - masterSize - masterFooter - gridVGap) / n;
      donutSize = cellH - labelReserve;
    } else {
      donutSize = dEquality;
      masterSize = mEquality;
    }

    if (donutSize > cellWMax) {
      donutSize = cellWMax;
      masterSize = Math.min(
        masterCap,
        Math.max(masterBase, donutSize * MASTER_OVER_GRID_RATIO),
      );
    }

    donutSize = donutSize < 24 ? 0 : Math.min(donutSize, MAX_DONUT_SIZE);
    masterSize = Math.max(masterFloor, Math.min(masterCap, masterSize));

    return {
      donutSize: Math.round(donutSize),
      masterSize: Math.round(masterSize),
    };
  };

  let reserve = editMode ? 64 : 26;
  let result = solve(reserve);
  for (let i = 0; i < 2; i++) {
    const next = labelReserveFor(result.donutSize, editMode);
    if (Math.abs(next - reserve) < 1) break;
    reserve = next;
    result = solve(reserve);
  }
  return result;
}

export type WidgetsProps = ContainerProps;

export const Widgets = ({ className, ...props }: WidgetsProps) => {
  const { running } = useAppState();
  const { thresholdStatus, masterStatus } = useThresholdStatus(running);
  const [widgetSlots, setWidgetSlots] = useState<WidgetConfig>(() => {
    const cfg = getUserSettings().widgetConfig;
    return resizeSlots(cfg, cfg.gridSize);
  });
  const [editMode, setEditMode] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedSlotIndex, setSelectedSlotIndex] = useState<number | null>(
    null,
  );
  const [panelRef, panelSize] = useElementSize<HTMLDivElement>();

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

  // --- Slot helpers ---

  const updateSlots = (updated: WidgetConfig) => {
    setWidgetSlots(updated);
    updateUserSettings({ widgetConfig: updated });
  };

  const showMaster = widgetSlots.masterVisible !== false;

  const toggleMasterVisible = () => {
    updateSlots({ ...widgetSlots, masterVisible: !showMaster });
  };

  const masterDisplayMode = widgetSlots.masterDisplayMode ?? "zone";
  const setMasterDisplayMode = (mode: MasterDisplayMode) => {
    updateSlots({ ...widgetSlots, masterDisplayMode: mode });
  };

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
    updateSlots({ ...widgetSlots, slots: newSlots });
    setSidebarOpen(false);
    setSelectedSlotIndex(null);
  };

  const removeFromSlot = (index: number) => {
    const newSlots = [...widgetSlots.slots];
    newSlots[index] = null;
    updateSlots({ ...widgetSlots, slots: newSlots });
  };

  const setSlotMode = (index: number, mode: WidgetDisplayMode) => {
    const slot = widgetSlots.slots[index];
    if (!slot) return;
    const newSlots = [...widgetSlots.slots];
    newSlots[index] = { ...slot, mode };
    updateSlots({ ...widgetSlots, slots: newSlots });
  };

  const changeGridSize = (size: number) => {
    const updated = resizeSlots(widgetSlots, size);
    updateSlots(updated);
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

  const hasMasterThresholds =
    (window.DASHBOARD_CONFIG.thresholds?.length ?? 0) > 0;
  const hasMaster = showMaster && hasMasterThresholds;
  const n = widgetSlots.gridSize;
  const { donutSize, masterSize } = computeSizes(
    panelSize.width,
    panelSize.height,
    n,
    hasMaster,
    editMode,
  );
  const showWidgetContent = donutSize > 0;
  const showNameLabel = donutSize >= NAME_LABEL_THRESHOLD;

  return (
    <Container
      className={`relative flex flex-col min-w-0 ${className || ""}`}
      {...props}
    >
      <div ref={panelRef} className="flex flex-col flex-1 min-w-0 min-h-0 overflow-hidden">
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

        {/* Master evaluation widget */}
        <MasterWidget
          status={masterStatus}
          visible={showMaster}
          editMode={editMode}
          displayMode={masterDisplayMode}
          onToggleVisible={toggleMasterVisible}
          onSetDisplayMode={setMasterDisplayMode}
          size={masterSize}
        />

        {/* Widget grid */}
        <div
          className="flex-1 min-w-0 min-h-0 overflow-hidden grid gap-4 place-items-center"
          style={{
            gridTemplateColumns: `repeat(${widgetSlots.gridSize}, minmax(0, 1fr))`,
            gridTemplateRows: `repeat(${widgetSlots.gridSize}, minmax(0, 1fr))`,
          }}
        >
          {widgetSlots.slots.map((slot, index) => {
            if (slot) {
              const tc = testCaseMap[slot.id];
              if (!tc) return <div key={index} />;

              return (
                <div
                  key={index}
                  className="relative flex flex-col items-center max-w-full max-h-full"
                >
                  {editMode && (
                    <button
                      onClick={() => removeFromSlot(index)}
                      className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-gray-700 hover:bg-red-600 text-gray-300 hover:text-white text-xs leading-none flex items-center justify-center transition-colors z-10"
                    >
                      &times;
                    </button>
                  )}
                  {showWidgetContent && (
                    <DonutWidget
                      name={tc.name}
                      status={thresholdStatus?.[slot.id] ?? null}
                      displayMode={slot.mode}
                      defaultColor={getThresholdDefaultColor(tc)}
                      size={donutSize}
                      showName={showNameLabel}
                    />
                  )}
                  {editMode && (
                    <DisplayModeSelector
                      modes={DISPLAY_MODES}
                      selected={slot.mode}
                      onChange={(mode) => setSlotMode(index, mode)}
                    />
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
