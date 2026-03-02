import { useEffect, useState } from "react";
import { useAppState } from "../../provider";

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

export type HeaderProps = object;

export const Header = () => {
  const { running, toggleRunning, runningSince } = useAppState();
  const [elapsed, setElapsed] = useState("00:00:00");

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
      <div className="py-3 px-6 bg-white/5 rounded-xl flex-1 flex gap-2 items-center justify-center">
        <span className="block">Runtime:</span>
        <span className="font-mono block pt-1">{elapsed}</span>
      </div>
    </header>
  );
};
