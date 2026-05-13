import { createContext } from "react";

export const SettingsLockContext = createContext<boolean>(false);

const readUnlockedFromUrl = (): boolean => {
  const expected = window.DASHBOARD_CONFIG?.settingsUnlock;
  if (!expected) return false;
  const provided = new URLSearchParams(window.location.search).get("s");
  return provided === expected;
};

export const SettingsLockProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const unlocked = readUnlockedFromUrl();
  return (
    <SettingsLockContext.Provider value={unlocked}>
      {children}
    </SettingsLockContext.Provider>
  );
};
