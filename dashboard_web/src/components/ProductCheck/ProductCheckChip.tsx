import { useProductMatch } from "../../hooks/useProductMatch";
import { useAppState } from "../../provider";

const formatSnooze = (s: number): string => {
  const total = Math.max(0, Math.round(s));
  const minutes = Math.floor(total / 60);
  const seconds = String(total % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
};

/**
 * Header status chip for the product-switch monitor: shows calibration
 * progress after run start and the snooze countdown after a cancelled alarm.
 * Quiet (renders nothing) while armed and matching.
 */
export const ProductCheckChip = () => {
  const { running } = useAppState();
  const status = useProductMatch();

  if (!window.DASHBOARD_CONFIG.productCheckEnabled || !running || !status) {
    return null;
  }

  if (status.state === "calibrating") {
    return (
      <span
        className="py-3 px-4 rounded-xl bg-blue-500/10 text-blue-400 text-sm whitespace-nowrap"
        title="Learning the detection profile of the current product"
      >
        Calibrating {status.calibrated ?? 0}/{status.calibration_target ?? "?"}
      </span>
    );
  }

  if (status.state === "snoozed") {
    return (
      <span
        className="py-3 px-4 rounded-xl bg-pear-500/10 text-pear-400 text-sm whitespace-nowrap font-mono"
        title="Product-switch alarm snoozed; it re-arms when the countdown ends"
      >
        Snoozed {formatSnooze(status.snooze_remaining_s ?? 0)}
      </span>
    );
  }

  return null;
};
