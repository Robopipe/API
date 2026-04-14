import { type RefObject, useCallback, useEffect, useRef } from "react";
import type {
  DetectionDisplayMode,
  MultiLimitDisplayMode,
} from "../types/dashboard";
import type {
  DetectionViolation,
  NNDetection,
  NNDetections,
} from "../types/detections";
import {
  isBBDetection,
  renderBBoxDetection,
  renderClassificationDetection,
  renderLine,
  renderSegmentationMask,
} from "../utils/renderDetections";

export interface UseDetectionsRendererOptions {
  videoRef: RefObject<HTMLVideoElement | null>;
  enabled?: boolean;
  displayMode?: DetectionDisplayMode;
  multiLimitMode?: MultiLimitDisplayMode;
}

export interface UseDetectionsRendererReturn {
  canvasRef: RefObject<HTMLCanvasElement | null>;
  renderDetections: (detections: NNDetections) => void;
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

  // Filtered modes: only show detections with matching violations
  if (!isBBDetection(detection) || !detection.violations?.length) return null;

  let violations: DetectionViolation[];
  if (displayMode === "alerts") {
    violations = detection.violations.filter((v) => v.severity === "ALERT");
    if (violations.length === 0) return null;
  } else {
    violations = detection.violations;
  }

  // Apply multi-limit mode
  if (multiLimitMode === "highest") {
    const highest =
      violations.find((v) => v.severity === "ALERT") ?? violations[0];
    violations = [highest];
  }

  // Return detection copy with filtered violations
  return { ...detection, violations };
}

export const useDetectionsRenderer = ({
  videoRef,
  enabled = true,
  displayMode = "all",
  multiLimitMode = "highest",
}: UseDetectionsRendererOptions): UseDetectionsRendererReturn => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const offscreenRef = useRef<HTMLCanvasElement | null>(null);

  const getOffscreenCanvas = useCallback(
    (width: number, height: number): HTMLCanvasElement => {
      if (!offscreenRef.current) {
        offscreenRef.current = document.createElement("canvas");
      }
      const offscreen = offscreenRef.current;
      if (offscreen.width !== width || offscreen.height !== height) {
        offscreen.width = width;
        offscreen.height = height;
      }
      return offscreen;
    },
    [],
  );

  const renderDetections = useCallback(
    async (detections: NNDetections) => {
      await new Promise((resolve) => setTimeout(resolve, 150)); // Yield to ensure latest video frame is rendered
      if (!canvasRef.current || !videoRef.current || !enabled) return;
      const canvas = canvasRef.current;
      if (canvas.width === 0 || canvas.height === 0) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      // Double-buffer: draw to offscreen canvas first, then swap in one draw call to avoid flickering
      const offscreen = getOffscreenCanvas(canvas.width, canvas.height);
      const offCtx = offscreen.getContext("2d");
      if (!offCtx) return;

      const labels = window.DASHBOARD_CONFIG.labels || [];
      offCtx.clearRect(0, 0, offscreen.width, offscreen.height);

      if (displayMode === "all") {
        renderSegmentationMask(offCtx, labels, detections);
      }

      for (const detection of detections.detections) {
        if (detection.confidence < 0.5) continue;
        const prepared = prepareDetectionForRender(
          detection,
          displayMode,
          multiLimitMode,
        );
        if (!prepared) continue;
        renderBBoxDetection(offCtx, labels, prepared);
        renderClassificationDetection(offCtx, labels, prepared);
      }

      // Single
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      renderLine(
        offCtx,
        window.DASHBOARD_CONFIG.lineDirection,
        window.DASHBOARD_CONFIG.linePosition,
      );
      ctx.drawImage(offscreen, 0, 0);
    },
    [videoRef, enabled, getOffscreenCanvas, displayMode, multiLimitMode],
  );

  useEffect(() => {
    if (!videoRef.current || !canvasRef.current || !enabled) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const syncCanvasSize = () => {
      const [elW, elH] = [video.clientWidth, video.clientHeight];
      const [mediaW, mediaH] = [video.videoWidth, video.videoHeight];
      const mediaAR = mediaW / mediaH;
      const elAR = elW / elH;
      let renderW, renderH;

      if (mediaAR > elAR) {
        renderW = elW;
        renderH = elW / mediaAR;
      } else {
        renderH = elH;
        renderW = elH * mediaAR;
      }
      canvas.width = renderW;
      canvas.height = renderH;
    };
    syncCanvasSize();
    window.addEventListener("resize", syncCanvasSize);
    video.addEventListener("loadedmetadata", syncCanvasSize);

    return () => {
      window.removeEventListener("resize", syncCanvasSize);
      video.removeEventListener("loadedmetadata", syncCanvasSize);
    };
  }, [enabled, videoRef]);

  return { canvasRef, renderDetections };
};
