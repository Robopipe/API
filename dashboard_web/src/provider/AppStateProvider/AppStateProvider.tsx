import { createContext, useState } from "react";
import type { TestCase } from "../../types";

export interface AppState {
  running: boolean;
  runningSince: Date | null;
  toggleRunning?: () => void;
  testCaseMap: Record<string, TestCase>;
}

const appState = createContext<AppState>({
  running: false,
  runningSince: null,
  testCaseMap: {},
});
export const AppStateContext = appState;

export const AppStateProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
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
    };
  });

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
      }}
    >
      {children}
    </AppStateContext.Provider>
  );
};
