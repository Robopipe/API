import { useCallback, useState } from "react";
import { useAppState } from "../provider";
import type { NNDetections, ProductMatchStatus } from "../types/detections";
import { useDetections } from "./useDetections";

/**
 * Latest product-switch monitor status from the detections stream, or null
 * while no run is active.
 *
 * The mismatch countdown is translated into local wall-clock time exactly
 * once per alarm (`deadlineAtMs`): the first message of an alarm anchors
 * `Date.now() + deadline_in_s`, and subsequent messages of the same alarm
 * (same backend `deadline_epoch_ms`) reuse that anchor. Re-anchoring every
 * message would make the rendered seconds flip-flop with network jitter and
 * the server's 0.1 s rounding.
 *
 * Also syncs the backend-reported `running` flag into the app state, which
 * is how every client learns about a backend-initiated auto-stop.
 */
export function useProductMatch(): ProductMatchStatus | null {
  const { running, setRunning } = useAppState();
  const [status, setStatus] = useState<ProductMatchStatus | null>(null);

  const onDetections = useCallback(
    (detections: NNDetections) => {
      const pm = detections.product_match;
      if (pm) {
        setStatus((prev) => {
          if (pm.state !== "mismatch") return pm;
          const sameAlarm =
            prev?.state === "mismatch" &&
            prev.deadline_epoch_ms === pm.deadline_epoch_ms &&
            prev.deadlineAtMs !== undefined;
          const deadlineAtMs = sameAlarm
            ? prev.deadlineAtMs
            : typeof pm.deadline_in_s === "number"
              ? Date.now() + pm.deadline_in_s * 1000
              : pm.deadline_epoch_ms;
          return { ...pm, deadlineAtMs };
        });
      }
      if (detections.running === false) {
        setRunning(false); // no-op when already stopped
      }
    },
    [setRunning],
  );

  useDetections({ onDetections, enabled: running });

  // Derived rather than reset-in-effect: a stopped run reports no status.
  return running ? status : null;
}
