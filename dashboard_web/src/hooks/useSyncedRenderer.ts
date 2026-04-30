import { type RefObject, useEffect, useRef } from "react";
import { useCameraStream } from "../provider";
import type {
  DetectionDisplayMode,
  MultiLimitDisplayMode,
} from "../types/dashboard";
import type { DetectionViolation, NNDetection } from "../types/detections";
import {
  isBBDetection,
  renderBBoxDetection,
  renderClassificationDetection,
  renderSegmentationMask,
  renderZone,
} from "../utils/renderDetections";

export interface UseSyncedRendererOptions {
  enabled?: boolean;
  displayMode?: DetectionDisplayMode;
  multiLimitMode?: MultiLimitDisplayMode;
  hiddenLabelIds?: Set<number>;
  zoneVisible?: boolean;
}

export interface UseSyncedRendererReturn {
  canvasRef: RefObject<HTMLCanvasElement | null>;
}

function prepareDetectionForRender(
  detection: NNDetection,
  displayMode: DetectionDisplayMode,
  multiLimitMode: MultiLimitDisplayMode,
): NNDetection | null {
  if (displayMode === "all") return detection;

  if (displayMode === "detections_only") {
    if (isBBDetection(detection) && detection.violations?.length)
      return { ...detection, violations: [] };
    return detection;
  }

  if (!isBBDetection(detection) || !detection.violations?.length) return null;

  let violations: DetectionViolation[];
  if (displayMode === "alerts") {
    violations = detection.violations.filter((v) => v.severity === "ALERT");
    if (violations.length === 0) return null;
  } else {
    violations = detection.violations;
  }

  if (multiLimitMode === "highest") {
    const highest =
      violations.find((v) => v.severity === "ALERT") ?? violations[0];
    violations = [highest];
  }

  return { ...detection, violations };
}

/**
 * Subscribes to matched (video frame, detections) pairs from the
 * provider's frame matcher and paints them into a single canvas.
 * Replaces the legacy <video> + transparent overlay split: the canvas
 * owns the displayed surface, so on-screen pixels and overlays always
 * come from the same source frame. Displayed FPS = inference FPS.
 */
export const useSyncedRenderer = ({
  enabled = true,
  displayMode = "all",
  multiLimitMode = "highest",
  hiddenLabelIds,
  zoneVisible = true,
}: UseSyncedRendererOptions): UseSyncedRendererReturn => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const offscreenRef = useRef<HTMLCanvasElement | null>(null);
  const { subscribeSyncedFrames, setDisplayCanvas } = useCameraStream();

  // Keep latest options in a ref so the subscriber callback always sees
  // current values without resubscribing every render.
  const optsRef = useRef({
    displayMode,
    multiLimitMode,
    hiddenLabelIds,
    zoneVisible,
  });
  optsRef.current = {
    displayMode,
    multiLimitMode,
    hiddenLabelIds,
    zoneVisible,
  };

  // Expose the canvas to the provider so it can snapshot it for
  // violation pictures.
  useEffect(() => {
    setDisplayCanvas(canvasRef.current);
    return () => setDisplayCanvas(null);
  }, [setDisplayCanvas]);

  useEffect(() => {
    if (!enabled) return;

    const unsubscribe = subscribeSyncedFrames((synced) => {
      const canvas = canvasRef.current;
      if (!canvas) {
        synced.bitmap.close();
        synced.detections.maskBitmap?.close?.();
        return;
      }

      const w = synced.bitmap.width;
      const h = synced.bitmap.height;
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) {
        synced.bitmap.close();
        synced.detections.maskBitmap?.close?.();
        return;
      }

      if (!offscreenRef.current) {
        offscreenRef.current = document.createElement("canvas");
      }
      const offscreen = offscreenRef.current;
      if (offscreen.width !== w || offscreen.height !== h) {
        offscreen.width = w;
        offscreen.height = h;
      }
      const offCtx = offscreen.getContext("2d");
      if (!offCtx) {
        synced.bitmap.close();
        synced.detections.maskBitmap?.close?.();
        return;
      }

      const labels = window.DASHBOARD_CONFIG.labels || [];
      const opts = optsRef.current;

      offCtx.drawImage(synced.bitmap, 0, 0);

      if (opts.displayMode === "all") {
        renderSegmentationMask(
          offCtx,
          labels,
          synced.detections,
          opts.hiddenLabelIds,
        );
      }

      for (const detection of synced.detections.detections) {
        if (
          detection.confidence < window.DASHBOARD_CONFIG.confidenceThreshold
        )
          continue;
        const detectionLabel = labels[detection.label];
        if (detectionLabel && opts.hiddenLabelIds?.has(detectionLabel.id))
          continue;
        const prepared = prepareDetectionForRender(
          detection,
          opts.displayMode,
          opts.multiLimitMode,
        );
        if (!prepared) continue;
        renderBBoxDetection(offCtx, labels, prepared);
        renderClassificationDetection(offCtx, labels, prepared);
      }

      if (opts.zoneVisible) {
        renderZone(
          offCtx,
          window.DASHBOARD_CONFIG.zoneDirection,
          window.DASHBOARD_CONFIG.zoneCenter,
          window.DASHBOARD_CONFIG.zoneThickness,
        );
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(offscreen, 0, 0);

      synced.bitmap.close();
      synced.detections.maskBitmap?.close?.();
    });

    return unsubscribe;
  }, [enabled, subscribeSyncedFrames]);

  return { canvasRef };
};
