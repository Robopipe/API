import { useEffect, useState } from "react";
import { useProductMatch } from "../../hooks/useProductMatch";
import { useAppState } from "../../provider";
import type { ProductMatchStatus } from "../../types/detections";

const WarningIcon = () => (
  <svg
    width="22"
    height="22"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

/**
 * Blocking modal shown while the product-switch alarm is active. The
 * countdown is owned by the backend — it stops the run itself when the
 * deadline passes; this component only mirrors the remaining time (re-synced
 * from every WS message, so client clock skew never accumulates).
 *
 * Non-dismissible by design: the operator must either Stop (same effect as
 * the dashboard Stop button) or Cancel (snoozes the alarm, evaluation
 * resumes). If neither happens, the backend auto-stop flips `running` to
 * false and the modal closes itself.
 */
export const ProductSwitchModal = () => {
  const { running, setRunning } = useAppState();
  const status = useProductMatch();

  if (!running || status?.state !== "mismatch") return null;

  return <AlarmDialog status={status} onStopped={() => setRunning(false)} />;
};

const AlarmDialog = ({
  status,
  onStopped,
}: {
  status: ProductMatchStatus;
  onStopped: () => void;
}) => {
  const [busy, setBusy] = useState<"stop" | "cancel" | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 250);
    return () => clearInterval(id);
  }, []);

  // deadlineAtMs is anchored once per alarm by useProductMatch (stable
  // across messages), so the countdown ticks down monotonically.
  const deadlineAt = status.deadlineAtMs ?? status.deadline_epoch_ms ?? null;
  const remainingMs = deadlineAt === null ? null : deadlineAt - nowMs;
  const secondsLeft = Math.max(0, Math.ceil((remainingMs ?? 0) / 1000));
  const expired = remainingMs !== null && remainingMs <= 0;
  const apiBase = window.DASHBOARD_CONFIG.apiBase;

  // One visual state for "stop in progress", whether the operator clicked
  // Stop or the countdown ran out: bar full, label "Stopping…".
  const stopping = busy === "stop" || expired;
  const totalMs =
    typeof status.total_in_s === "number" && status.total_in_s > 0
      ? status.total_in_s * 1000
      : null;
  // Without a total (older backend) the bar stays empty; the label still
  // counts down.
  const fillFraction = stopping
    ? 1
    : totalMs !== null && remainingMs !== null
      ? Math.min(1, Math.max(0, 1 - remainingMs / totalMs))
      : 0;

  const handleStop = async () => {
    if (busy) return;
    setBusy("stop");
    try {
      const resp = await fetch(
        `${apiBase}/dashboard/stop?reason=product_switch_confirmed`,
        { method: "POST" },
      );
      if (resp.ok) {
        onStopped();
        return;
      }
    } catch {
      /* backend auto-stop will close the modal regardless */
    }
    setBusy(null);
  };

  const handleCancel = async () => {
    if (busy) return;
    setBusy("cancel");
    try {
      // 409 means the auto-stop already won the race; `running` flips false
      // on the next WS tick and the modal closes itself either way.
      await fetch(`${apiBase}/dashboard/product-check/cancel`, {
        method: "POST",
      });
      // Stay disabled until the WS state leaves "mismatch" and unmounts us.
    } catch {
      setBusy(null);
    }
  };

  return (
    /* Backdrop — intentionally not clickable to close (blocking modal) */
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="w-md max-w-[92vw] bg-gray-900 border border-red-500/40 rounded-xl shadow-xl overflow-hidden">
        <div className="flex items-start gap-3 px-6 py-4 border-b border-gray-700">
          <span className="text-red-400 mt-0.5 shrink-0">
            <WarningIcon />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-white">
              Product change suspected
            </h2>
            <p className="text-sm text-gray-400 mt-0.5">
              The detections no longer match the product this model was deployed
              for. Evaluation is paused — the run stops automatically unless
              you cancel.
            </p>
          </div>
        </div>

        <div className="px-6 py-5">
          <div className="flex gap-2 justify-end">
            <button
              className="py-2.5 px-5 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-default"
              onClick={handleCancel}
              disabled={busy !== null || expired}
            >
              {busy === "cancel" ? "Resuming…" : "Cancel"}
            </button>
            {/* Loading button: the fill grows toward 100%, at which point the
                backend auto-stop fires — clicking it just stops now. */}
            <button
              className="relative overflow-hidden py-2.5 px-5 rounded-xl bg-red-500/30 hover:bg-red-500/40 text-white cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-default"
              onClick={handleStop}
              disabled={busy !== null || expired}
            >
              <span
                aria-hidden
                className="absolute inset-y-0 left-0 bg-red-500/80 transition-[width] duration-300 ease-linear"
                style={{ width: `${fillFraction * 100}%` }}
              />
              <span className="relative">
                {stopping ? (
                  "Stopping…"
                ) : (
                  <>
                    Stop run ·{" "}
                    <span className="tabular-nums">{secondsLeft}s</span>
                  </>
                )}
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
