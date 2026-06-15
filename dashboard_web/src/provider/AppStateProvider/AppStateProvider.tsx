import { createContext, useCallback, useState } from "react";
import type {
  DetectionDisplayMode,
  MultiLimitDisplayMode,
  TestCase,
} from "../../types";
import { getUserSettings, updateUserSettings } from "../../api/userSettings";

export interface AppState {
  running: boolean;
  runningSince: Date | null;
  toggleRunning?: () => void;
  testCaseMap: Record<string, TestCase>;
  displayMode: DetectionDisplayMode;
  setDisplayMode: (mode: DetectionDisplayMode) => void;
  multiLimitMode: MultiLimitDisplayMode;
  setMultiLimitMode: (mode: MultiLimitDisplayMode) => void;
  hiddenLabelIds: Set<number>;
  toggleLabelVisibility: (labelId: number) => void;
  zoneVisible: boolean;
  setZoneVisible: (visible: boolean) => void;
  selectedLabelId: number | null;
  setSelectedLabelId: (labelId: number) => void;
  overlayScale: number;
  setOverlayScale: (scale: number) => void;
}

const noop = () => {};

const appState = createContext<AppState>({
  running: false,
  runningSince: null,
  testCaseMap: {},
  displayMode: "all",
  setDisplayMode: noop,
  multiLimitMode: "highest",
  setMultiLimitMode: noop,
  hiddenLabelIds: new Set(),
  toggleLabelVisibility: noop,
  zoneVisible: false,
  setZoneVisible: noop,
  selectedLabelId: null,
  setSelectedLabelId: noop,
  overlayScale: 1,
  setOverlayScale: noop,
});
export const AppStateContext = appState;

export const AppStateProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const labels = window.DASHBOARD_CONFIG.labels;
  const testCaseMap = window.DASHBOARD_CONFIG.testCases.reduce(
    (acc, tc) => {
      acc[tc.id] = tc;
      return acc;
    },
    {} as Record<string, TestCase>,
  );
  const [state, setState] = useState<AppState>(() => {
    const { running, runningSince } = window.DASHBOARD_CONFIG;
    const settings = getUserSettings();
    const initialLabelId =
      settings.selectedLabelId !== null &&
      labels.some((l) => l.id === settings.selectedLabelId)
        ? settings.selectedLabelId
        : (labels[0]?.id ?? null);
    return {
      running,
      runningSince:
        running && runningSince ? new Date(runningSince + "Z") : null,
      testCaseMap,
      displayMode: settings.displayMode,
      setDisplayMode: noop,
      multiLimitMode: settings.multiLimitMode,
      setMultiLimitMode: noop,
      hiddenLabelIds: new Set(settings.hiddenLabelIds),
      toggleLabelVisibility: noop,
      zoneVisible: settings.zoneVisible,
      setZoneVisible: noop,
      selectedLabelId: initialLabelId,
      setSelectedLabelId: noop,
      overlayScale: settings.overlayScale ?? 1,
      setOverlayScale: noop,
    };
  });

  const setDisplayMode = useCallback((mode: DetectionDisplayMode) => {
    updateUserSettings({ displayMode: mode });
    setState((prev) => ({ ...prev, displayMode: mode }));
  }, []);

  const setMultiLimitMode = useCallback((mode: MultiLimitDisplayMode) => {
    updateUserSettings({ multiLimitMode: mode });
    setState((prev) => ({ ...prev, multiLimitMode: mode }));
  }, []);

  const toggleLabelVisibility = useCallback((labelId: number) => {
    setState((prev) => {
      const next = new Set(prev.hiddenLabelIds);
      if (next.has(labelId)) next.delete(labelId);
      else next.add(labelId);
      updateUserSettings({ hiddenLabelIds: [...next] });
      return { ...prev, hiddenLabelIds: next };
    });
  }, []);

  const setZoneVisible = useCallback((visible: boolean) => {
    updateUserSettings({ zoneVisible: visible });
    setState((prev) => ({ ...prev, zoneVisible: visible }));
  }, []);

  const setSelectedLabelId = useCallback((labelId: number) => {
    updateUserSettings({ selectedLabelId: labelId });
    setState((prev) => ({ ...prev, selectedLabelId: labelId }));
  }, []);

  const setOverlayScale = useCallback((scale: number) => {
    updateUserSettings({ overlayScale: scale });
    setState((prev) => ({ ...prev, overlayScale: scale }));
  }, []);

  const toggleRunning = async () => {
    const nextRunning = !state.running;
    const endpoint = nextRunning ? "start" : "stop";

    try {
      const resp = await fetch(
        `${window.DASHBOARD_CONFIG.apiBase}/dashboard/${endpoint}`,
        { method: "POST" },
      );
      if (!resp.ok) return;
    } catch {
      return;
    }

    setState((prev) => ({
      ...prev,
      running: nextRunning,
      runningSince: nextRunning ? new Date() : null,
    }));
  };

  return (
    <AppStateContext.Provider
      value={{
        ...state,
        toggleRunning,
        setDisplayMode,
        setMultiLimitMode,
        toggleLabelVisibility,
        setZoneVisible,
        setSelectedLabelId,
        setOverlayScale,
      }}
    >
      {children}
    </AppStateContext.Provider>
  );
};
