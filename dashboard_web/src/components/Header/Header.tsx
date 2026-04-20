import { useEffect, useRef, useState } from "react";
import { useWakeLock } from "../../hooks/useWakeLock";
import { useAppState } from "../../provider";
import { GearIcon, WakeLockIcon } from "../../ui";
import { ModelSwitcher } from "./ModelSwitcher";
import { SettingsModal } from "./SettingsModal";
import {
  loadTimerLabelDisplay,
  saveTimerLabelDisplay,
  type TimerLabelDisplay,
} from "./timerLabelStorage";

const formatElapsed = (ms: number): string => {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(
    2,
    "0",
  );
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
};

const TIMER_LABEL_OPTIONS: { value: TimerLabelDisplay; label: string }[] = [
  { value: "project_name", label: "Project name" },
  { value: "dashboard_name", label: "Dashboard name" },
  { value: "nothing", label: "Timer only" },
];

export type HeaderProps = object;

export const Header = () => {
  const { running, toggleRunning, runningSince } = useAppState();
  const wakeLock = useWakeLock();
  const [elapsed, setElapsed] = useState("00:00:00");
  const [labelDisplay, setLabelDisplay] = useState<TimerLabelDisplay>(
    loadTimerLabelDisplay,
  );
  const [menuOpen, setMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runningSince) {
      setElapsed("00:00:00");
      return;
    }

    const tick = () =>
      setElapsed(formatElapsed(Date.now() - runningSince.getTime()));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [runningSince]);

  useEffect(() => {
    if (!menuOpen) return;
    const handleOutside = (e: Event) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("touchstart", handleOutside);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("touchstart", handleOutside);
    };
  }, [menuOpen]);

  const labelText =
    labelDisplay === "project_name"
      ? window.DASHBOARD_CONFIG.projectName
      : labelDisplay === "dashboard_name"
        ? window.DASHBOARD_CONFIG.name
        : null;

  const handleLabelChange = (value: TimerLabelDisplay) => {
    setLabelDisplay(value);
    saveTimerLabelDisplay(value);
    setMenuOpen(false);
  };

  return (
    <header className="flex justify-stretch items-center mb-4 gap-2">
      <button
        className={
          "py-3 px-6 rounded-xl" +
          (running ? " bg-red-500/80" : " bg-emerald-500/80")
        }
        onClick={toggleRunning}
      >
        {running ? "Stop" : "Start"}
      </button>
      <div
        ref={menuRef}
        className={`py-3 px-4 sm:px-6 bg-white/5 hover:bg-white/10 rounded-xl flex-1 min-w-0 flex items-center gap-3 relative select-none cursor-pointer transition-colors ${labelText ? "justify-between" : "justify-center"}`}
        onClick={() => setMenuOpen((prev) => !prev)}
      >
        {labelText && (
          <span className="min-w-0 flex-1 truncate text-base">{labelText}</span>
        )}
        <span className="font-mono shrink-0 text-base">{elapsed}</span>

        {menuOpen && (
          <div
            className="absolute top-full left-1/2 -translate-x-1/2 mt-2 bg-gray-800 border border-gray-700 rounded-xl p-2 z-50 min-w-40 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            {TIMER_LABEL_OPTIONS.map((option) => (
              <button
                key={option.value}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                  labelDisplay === option.value
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-gray-300 hover:bg-gray-700"
                }`}
                onClick={() => handleLabelChange(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>
      <ModelSwitcher />
      <button
        className="p-3 rounded-xl transition-colors bg-white/5 text-gray-400 hover:text-white"
        onClick={() => setSettingsOpen(true)}
        title="Dashboard Settings"
      >
        <GearIcon size={20} />
      </button>
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
      {wakeLock.supported && (
        <button
          className={
            "p-3 rounded-xl transition-colors bg-white/5" +
            (wakeLock.enabled
              ? " text-emerald-400 hover:text-emerald-300"
              : " text-gray-400 hover:text-white")
          }
          onClick={wakeLock.toggle}
          title="Wake Lock"
        >
          <WakeLockIcon size={20} />
        </button>
      )}
    </header>
  );
};
