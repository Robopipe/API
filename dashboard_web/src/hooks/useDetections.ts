import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { NNDetections } from "../types/detections";
import {
  detectionsManager,
  EMPTY_SNAPSHOT,
  type DetectionsSnapshot,
} from "../utils/detectionsManager";

export interface UseDetectionsOptions {
  onDetections?: (detections: NNDetections) => void;
  enabled?: boolean;
}

export interface UseDetectionsReturn {
  detections: NNDetections;
  isConnected: boolean;
  error: string | null;
}

export const useDetections = ({
  onDetections,
  enabled = true,
}: UseDetectionsOptions): UseDetectionsReturn => {
  // Keep a stable ref so the manager always calls the latest callback
  const callbackRef = useRef(onDetections);
  useEffect(() => {
    callbackRef.current = onDetections;
  });

  // Stable wrapper that delegates to the latest callback ref
  const [stableCallback] = useState(() => (d: NNDetections) => {
    callbackRef.current?.(d);
  });

  const { detections, isConnected, error } = useSyncExternalStore(
    enabled ? detectionsManager.subscribe : emptySubscribe,
    enabled ? detectionsManager.getSnapshot : getEmptySnapshot,
  );

  // Register / unregister the per-instance onDetections callback
  useEffect(() => {
    if (!enabled) return;
    detectionsManager.addCallback(stableCallback);
    return () => {
      detectionsManager.removeCallback(stableCallback);
    };
  }, [enabled, stableCallback]);

  return { detections, isConnected, error };
};

// Helpers for the disabled case
const EMPTY: DetectionsSnapshot = EMPTY_SNAPSHOT;
const emptySubscribe = () => () => {};
const getEmptySnapshot = () => EMPTY;
