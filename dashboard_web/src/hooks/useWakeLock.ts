import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

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

  return { enabled, toggle };
};
