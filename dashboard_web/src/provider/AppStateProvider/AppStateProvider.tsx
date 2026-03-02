import { createContext, useState } from "react";
import type { DashboardItem } from "../../types";

export interface AppState {
  running: boolean;
  runningSince: Date | null;
  toggleRunning?: () => void;
  dashboardItemMap: Record<number, DashboardItem>;
}

const appState = createContext<AppState>({
  running: false,
  runningSince: null,
  dashboardItemMap: {},
});
export const AppStateContext = appState;

export const AppStateProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const dashboardItemMap = window.DASHBOARD_CONFIG.dashboardItems.reduce(
    (acc, item) => {
      acc[item.id] = item;
      return acc;
    },
    {} as Record<number, DashboardItem>,
  );
  const [state, setState] = useState<AppState>({
    running: false,
    runningSince: null,
    dashboardItemMap,
  });

  return (
    <AppStateContext.Provider
      value={{
        ...state,
        toggleRunning: () => {
          setState((prev) => ({
            ...prev,
            running: !prev.running,
            runningSince: !prev.running ? new Date() : null,
          }));
        },
      }}
    >
      {children}
    </AppStateContext.Provider>
  );
};
