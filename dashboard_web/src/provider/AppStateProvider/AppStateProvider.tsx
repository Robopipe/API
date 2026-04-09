import { createContext, useCallback, useState } from "react";
import type {
  DetectionDisplayMode,
  MultiLimitDisplayMode,
  TestCase,
} from "../../types";
import {
  loadDisplayMode,
  loadMultiLimitMode,
  saveDisplayMode,
  saveMultiLimitMode,
} from "../../components/Counter/displaySettingsStorage";

export interface AppState {
  running: boolean;
  runningSince: Date | null;
  toggleRunning?: () => void;
  testCaseMap: Record<string, TestCase>;
  displayMode: DetectionDisplayMode;
  setDisplayMode: (mode: DetectionDisplayMode) => void;
  multiLimitMode: MultiLimitDisplayMode;
  setMultiLimitMode: (mode: MultiLimitDisplayMode) => void;
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
});
export const AppStateContext = appState;

export const AppStateProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const configId = window.DASHBOARD_CONFIG.configId;
  const testCaseMap = window.DASHBOARD_CONFIG.testCases.reduce(
    (acc, tc) => {
      acc[tc.id] = tc;
      return acc;
    },
    {} as Record<string, TestCase>,
  );
  const [state, setState] = useState<AppState>(() => {
    const { running, runningSince } = window.DASHBOARD_CONFIG;
    return {
      running,
      runningSince:
        running && runningSince ? new Date(runningSince + "Z") : null,
      testCaseMap,
      displayMode: loadDisplayMode(configId),
      setDisplayMode: noop,
      multiLimitMode: loadMultiLimitMode(configId),
      setMultiLimitMode: noop,
    };
  });

  const setDisplayMode = useCallback(
    (mode: DetectionDisplayMode) => {
      saveDisplayMode(configId, mode);
      setState((prev) => ({ ...prev, displayMode: mode }));
    },
    [configId],
  );

  const setMultiLimitMode = useCallback(
    (mode: MultiLimitDisplayMode) => {
      saveMultiLimitMode(configId, mode);
      setState((prev) => ({ ...prev, multiLimitMode: mode }));
    },
    [configId],
  );

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
      }}
    >
      {children}
    </AppStateContext.Provider>
  );
};
