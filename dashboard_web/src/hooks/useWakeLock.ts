import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

// `document.featurePolicy` is deprecated but still implemented in Chromium and
// is the only runtime way to detect a missing `screen-wake-lock` Permissions
// Policy allowance (e.g. cross-origin iframe without `allow="screen-wake-lock"`).
// Absent in other browsers — fall back to true so we don't over-hide the icon.
interface LegacyFeaturePolicy {
  allowsFeature(feature: string): boolean;
}
const featurePolicy: LegacyFeaturePolicy | undefined =
  typeof document !== "undefined"
    ? (document as unknown as { featurePolicy?: LegacyFeaturePolicy })
        .featurePolicy
    : undefined;

const supported =
  typeof window !== "undefined" &&
  window.isSecureContext &&
  "wakeLock" in navigator &&
  (featurePolicy?.allowsFeature("screen-wake-lock") ?? true);

export const useWakeLock = () => {
  const [enabled, setEnabled] = useState(false);
  const wantedRef = useRef(false);
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);

  const request = useCallback(async () => {
    try {
      wakeLockRef.current = await navigator.wakeLock.request("screen");
      wakeLockRef.current.addEventListener("release", () => {
        wakeLockRef.current = null;
      });
      setEnabled(true);
      toast.success("Wake lock enabled");
    } catch (err) {
      setEnabled(false);
      wantedRef.current = false;
      toast.error(
        `Wake lock failed: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    }
  }, []);

  const release = useCallback(async () => {
    if (wakeLockRef.current) {
      await wakeLockRef.current.release();
      wakeLockRef.current = null;
    }
    setEnabled(false);
    toast("Wake lock disabled");
  }, []);

  const toggle = useCallback(() => {
    if (wantedRef.current) {
      wantedRef.current = false;
      release();
    } else {
      wantedRef.current = true;
      request();
    }
  }, [request, release]);

  useEffect(() => {
    if (!wantedRef.current) return;

    const onVisibilityChange = () => {
      if (document.visibilityState === "visible" && !wakeLockRef.current) {
        request();
      }
    };

    document.addEventListener("visibilitychange", onVisibilityChange);
    return () =>
      document.removeEventListener("visibilitychange", onVisibilityChange);
  }, [enabled, request]);

  useEffect(() => {
    return () => {
      wakeLockRef.current?.release();
    };
  }, []);

  return { enabled, toggle, supported };
};
