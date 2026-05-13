import { type RefObject, useEffect, useRef } from "react";
import { useCameraStream } from "../provider";
import type {
  DetectionDisplayMode,
  MultiLimitDisplayMode,
} from "../types/dashboard";
import type { DetectionViolation, NNDetection } from "../types/detections";
import { pickBlockSize } from "../utils/decodeTimestampBurnin";
import {
  isBBDetection,
  renderBBoxDetection,
  renderClassificationDetection,
  renderSegmentationMask,
  renderZone,
} from "../utils/renderDetections";

const VIOLATION_SNAPSHOT_QUALITY = 0.85;

const X_AXIS_DIRECTIONS = new Set(["LEFT_TO_RIGHT", "RIGHT_TO_LEFT"]);

/**
 * Signed distance of the bbox center from the configured zone center,
 * measured along the zone's axis. Returns null when the bbox center is
 * outside the zone — the caller treats that as "don't buffer this frame"
 * so post-exit sticky-violation frames don't get considered for the
 * picture.
 *
 * Used to pick the *closest-to-center* in-zone frame as the saved
 * picture: each new in-zone frame replaces the buffered blob only if its
 * absolute distance to zoneCenter is smaller than the buffered distance.
 */
function inZoneDistance(
  coords: [number, number, number, number],
  direction: string,
  center: number,
  thickness: number,
): number | null {
  const cx = (coords[0] + coords[2]) / 2;
  const cy = (coords[1] + coords[3]) / 2;
  const half = thickness / 2;
  const lo = Math.max(0, center - half);
  const hi = Math.min(1, center + half);
  const coord = X_AXIS_DIRECTIONS.has(direction) ? cx : cy;
  if (coord < lo || coord > hi) return null;
  return Math.abs(coord - center);
}

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
  const { subscribeSyncedFrames, setDisplayCanvas, bufferViolationFrame } =
    useCameraStream();

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

      // Snapshot the just-painted matched frame for any tracker the live
      // overlay is flagging as violating *and* whose bbox center is still
      // inside the configured zone. Each entry carries the tracker's
      // distance from zoneCenter so the provider can keep the
      // closest-to-center frame across the dwell — that's the moment the
      // object is best framed for the saved picture, while still also
      // implicitly excluding post-exit sticky-violation frames (the
      // distance is null once the bbox center crosses the zone boundary).
      const dashCfg = window.DASHBOARD_CONFIG;
      const violatingEntries: { trackerId: number; distance: number }[] = [];
      for (const detection of synced.detections.detections) {
        if (
          !isBBDetection(detection) ||
          detection.tracking_id === undefined ||
          !detection.violations ||
          detection.violations.length === 0
        ) {
          continue;
        }
        const distance = inZoneDistance(
          detection.coords,
          dashCfg.zoneDirection,
          dashCfg.zoneCenter,
          dashCfg.zoneThickness,
        );
        if (distance === null) continue;
        violatingEntries.push({
          trackerId: detection.tracking_id,
          distance,
        });
      }
      if (violatingEntries.length > 0) {
        canvas.toBlob(
          (blob) => {
            if (blob) bufferViolationFrame(violatingEntries, blob);
          },
          "image/jpeg",
          VIOLATION_SNAPSHOT_QUALITY,
        );
      }

      synced.bitmap.close();
      synced.detections.maskBitmap?.close?.();
    });

    return unsubscribe;
  }, [enabled, subscribeSyncedFrames, bufferViolationFrame]);

  return { canvasRef };
};
