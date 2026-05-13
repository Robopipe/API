import { useContext } from "react";
import { SettingsLockContext } from "./SettingsLockProvider";

export const useSettingsUnlocked = (): boolean =>
  useContext(SettingsLockContext);
