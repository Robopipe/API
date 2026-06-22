import { type RefObject, useEffect, useRef } from "react";
import { useCameraStream } from "../provider";
import type {
  DetectionDisplayMode,
  MultiLimitDisplayMode,
} from "../types/dashboard";
import type { NNDetection } from "../types/detections";
import { pickBlockSize } from "../utils/decodeTimestampBurnin";
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
  overlayScale?: number;
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

  const effectiveSev =
    isBBDetection(detection)
      ? (detection.severity ??
        (detection.violations?.some((v) => v.severity === "ALERT")
          ? "ALERT"
          : detection.violations?.some((v) => v.severity === "WARNING")
            ? "WARNING"
            : undefined))
      : undefined;

  if (displayMode === "detections_only") {
    if (effectiveSev)
      return { ...detection, violations: [], role: undefined, severity: undefined };
    return detection;
  }

  // "violations_only" and "alerts": only pass highlighted detections.
  if (!isBBDetection(detection) || !effectiveSev) return null;

  if (displayMode === "alerts" && effectiveSev !== "ALERT") return null;

  // multiLimitMode "highest": collapse the parent's violations list to the
  // single highest-severity entry. No-op for children (no violations).
  if (multiLimitMode === "highest" && detection.violations?.length) {
    const violations = detection.violations;
    const highest =
      violations.find((v) => v.severity === "ALERT") ?? violations[0];
    return { ...detection, violations: [highest] };
  }

  return detection;
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
  overlayScale = 1,
}: UseSyncedRendererOptions): UseSyncedRendererReturn => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const offscreenRef = useRef<HTMLCanvasElement | null>(null);
  const { subscribeSyncedFrames } = useCameraStream();

  // Keep latest options in a ref so the subscriber callback always sees
  // current values without resubscribing every render.
  const optsRef = useRef({
    displayMode,
    multiLimitMode,
    hiddenLabelIds,
    zoneVisible,
    overlayScale,
  });
  optsRef.current = {
    displayMode,
    multiLimitMode,
    hiddenLabelIds,
    zoneVisible,
    overlayScale,
  };

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
        // Shift the canvas up by the burned-in timestamp stripe height
        // so the parent's overflow:hidden clips it. Pixels are kept in
        // the drawing buffer for snapshot/timestamp decoding. The extra
        // 1px on top/height absorbs sub-pixel rounding during scaling
        // so the stripe never bleeds back in.
        const block = pickBlockSize(w);
        const s = block / h;
        canvas.style.top = `calc(${(-s / (1 - s)) * 100}% - 1px)`;
        canvas.style.height = `calc(${(1 / (1 - s)) * 100}% + 1px)`;
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
      const cssWidth = canvas.clientWidth || canvas.width;
      const scale = (canvas.width / cssWidth) * (opts.overlayScale ?? 1);

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
        const detectionLabel = labels[detection.label];
        const threshold =
          (detectionLabel &&
            window.DASHBOARD_CONFIG.labelConfidenceThresholds?.[
              detectionLabel.id
            ]) ??
          window.DASHBOARD_CONFIG.confidenceThreshold;
        if (detection.confidence < threshold) continue;
        if (detectionLabel && opts.hiddenLabelIds?.has(detectionLabel.id))
          continue;
        const prepared = prepareDetectionForRender(
          detection,
          opts.displayMode,
          opts.multiLimitMode,
        );
        if (!prepared) continue;
        renderBBoxDetection(offCtx, labels, prepared, scale);
        renderClassificationDetection(offCtx, labels, prepared, scale);
      }

      if (opts.zoneVisible) {
        renderZone(
          offCtx,
          window.DASHBOARD_CONFIG.zoneDirection,
          window.DASHBOARD_CONFIG.zoneCenter,
          window.DASHBOARD_CONFIG.zoneThickness,
          scale,
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
