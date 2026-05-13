import { useEffect, useRef } from "react";
import { useCameraStream } from "../provider";
import type { NNDetections } from "../types/detections";

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
  const {
    detections,
    isDetectionsConnected,
    detectionsError,
    subscribeDetections,
  } = useCameraStream();

  const onDetectionsRef = useRef(onDetections);
  onDetectionsRef.current = onDetections;

  useEffect(() => {
    if (!enabled || !onDetectionsRef.current) return;
    const unsubscribe = subscribeDetections((d) => {
      onDetectionsRef.current?.(d);
    });
    return unsubscribe;
  }, [enabled, subscribeDetections]);

  return {
    detections,
    isConnected: isDetectionsConnected,
    error: detectionsError,
  };
};
