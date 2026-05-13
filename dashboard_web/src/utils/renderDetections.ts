import { DashboardZoneDirection, type Label } from "../types";
import type {
  BBDetection,
  ClassificationDetection,
  NNDetection,
  NNDetections,
} from "../types/detections";

export type DetectionRenderer = (
  ctx: CanvasRenderingContext2D,
  labels: Label[],
  detection: NNDetection,
) => void;

export const isBBDetection = (
  detection: NNDetection,
): detection is BBDetection => {
  return (detection as BBDetection).coords !== undefined;
};

const isClassificationDetection = (
  detection: NNDetection,
): detection is ClassificationDetection => {
  return !("coords" in detection) && !("points" in detection);
};

// Violation rendering colors (from Figma design)
const ALERT_BORDER = "#98193b";
const ALERT_FILL = "rgba(244,120,137,0.15)";
const ALERT_LABEL_BG = "#98193b";

const WARNING_BORDER = "#d6da18";
const WARNING_FILL = "rgba(244,120,137,0.15)";
const WARNING_LABEL_BG = "#dce91d";

const drawAlertTriangle = (
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
) => {
  ctx.save();

  // Circular semi-transparent background
  ctx.fillStyle = "rgba(215,39,77,0.32)";
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.fill();

  // Triangle
  const triSize = radius * 0.9;
  const triHeight = triSize * 0.866;
  const triCy = cy + triSize * 0.08;
  ctx.fillStyle = "#d7274d";
  ctx.beginPath();
  ctx.moveTo(cx, triCy - triHeight * 0.6);
  ctx.lineTo(cx + triSize * 0.5, triCy + triHeight * 0.4);
  ctx.lineTo(cx - triSize * 0.5, triCy + triHeight * 0.4);
  ctx.closePath();
  ctx.fill();

  // Exclamation mark
  ctx.fillStyle = "#fff";
  ctx.font = `bold ${triSize * 0.55}px Inter`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("!", cx, triCy + triHeight * 0.02);

  ctx.restore();
};

export const renderBBoxDetection: DetectionRenderer = (
  ctx,
  labels,
  detection,
) => {
  if (!isBBDetection(detection)) return;
  const label = labels[detection.label];
  const [xmin, ymin, xmax, ymax] = detection.coords;
  const { width, height } = ctx.canvas;
  const [x, y, w, h] = [
    xmin * width,
    ymin * height,
    (xmax - xmin) * width,
    (ymax - ymin) * height,
  ];

  const violations = detection.violations;
  const isAlert = violations?.some((v) => v.severity === "ALERT");
  const isWarning =
    !isAlert && violations?.some((v) => v.severity === "WARNING");

  const borderColor = isAlert
    ? ALERT_BORDER
    : isWarning
      ? WARNING_BORDER
      : label.color;
  const fillColor = isAlert
    ? ALERT_FILL
    : isWarning
      ? WARNING_FILL
      : `${label.color}33`;
  const labelBg = isAlert
    ? ALERT_LABEL_BG
    : isWarning
      ? WARNING_LABEL_BG
      : label.color;
  const labelTextColor = isWarning ? "rgba(0,0,0,0.9)" : "#fff";
  const idPrefix =
    isBBDetection(detection) && detection.display_id != null
      ? `#${detection.display_id} `
      : "";
  const text = violations?.length
    ? `${idPrefix}${violations.map((v) => v.limit_name).join(", ")}`
    : `${idPrefix}${label.name} (${(detection.confidence * 100).toFixed(1)}%)`;
  const font = violations?.length
    ? "500 12px 'Space Grotesk', Inter, sans-serif"
    : "14px Inter";

  // Rectangle
  ctx.strokeStyle = borderColor;
  ctx.fillStyle = fillColor;
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);
  ctx.fillRect(x, y, w, h);

  // Text label above the bounding box
  ctx.font = font;
  const textWidth = ctx.measureText(text).width;
  const textHeight = 16;
  const padding = violations?.length ? 8 : 2;
  ctx.fillStyle = labelBg;
  ctx.fillRect(
    x - 1,
    y - textHeight - (violations?.length ? 5 : 0),
    textWidth + padding * 2,
    textHeight + (violations?.length ? 4 : 0),
  );
  ctx.fillStyle = labelTextColor;
  ctx.fillText(text, x - 1 + padding, y - (violations?.length ? 7 : 4));

  // Alert triangle
  if (isAlert) {
    const triangleRadius = Math.min(24, h * 0.25);
    drawAlertTriangle(ctx, x - triangleRadius - 8, y + h / 2, triangleRadius);
  }
};

export const renderClassificationDetection: DetectionRenderer = (
  ctx,
  labels,
  detection,
) => {
  if (!isClassificationDetection(detection)) return;
  const label = labels[detection.label];
  const text = `${label.name} (${(detection.confidence * 100).toFixed(1)}%)`;
  ctx.font = "16px Inter";
  ctx.fillStyle = label.color;
  ctx.fillText(text, 10, 20);
};

/**
 * Recolor a label-index buffer in place: pixel value 0 = background
 * (alpha 0), pixel value N = detections[N - 1]'s label color at ~53%
 * alpha. Unifies the PNG ImageBitmap and legacy nested-int paths.
 */
const recolorMask = (
  data: Uint8ClampedArray,
  indexAt: (px: number) => number,
  pixels: number,
  labels: Label[],
  detections: NNDetections,
  hiddenLabelIds: Set<number> | undefined,
) => {
  for (let p = 0; p < pixels; p++) {
    const labelIdx = indexAt(p);
    if (labelIdx < 0) continue; // background
    const detLabel = detections.detections[labelIdx];
    if (!detLabel) continue;
    const label = labels[detLabel.label];
    if (!label) continue;
    if (hiddenLabelIds?.has(label.id)) continue;
    const color = label.color;
    const r = parseInt(color.slice(1, 3), 16);
    const g = parseInt(color.slice(3, 5), 16);
    const b = parseInt(color.slice(5, 7), 16);
    const idx = p * 4;
    data[idx] = r;
    data[idx + 1] = g;
    data[idx + 2] = b;
    data[idx + 3] = 0x88;
  }
};

const drawScaled = (
  ctx: CanvasRenderingContext2D,
  source: HTMLCanvasElement,
) => {
  const prevSmoothing = ctx.imageSmoothingEnabled;
  const prevQuality = ctx.imageSmoothingQuality;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, 0, 0, ctx.canvas.width, ctx.canvas.height);
  ctx.imageSmoothingEnabled = prevSmoothing;
  ctx.imageSmoothingQuality = prevQuality;
};

export const renderSegmentationMask = (
  ctx: CanvasRenderingContext2D,
  labels: Label[],
  detections: NNDetections,
  hiddenLabelIds?: Set<number>,
) => {
  // Preferred path: PNG-encoded mask decoded to an ImageBitmap by the
  // detections manager. Pixel value 0 = background, N = detections[N - 1].
  const bmp = detections.maskBitmap;
  if (bmp) {
    const w = bmp.width;
    const h = bmp.height;
    const offscreen = document.createElement("canvas");
    offscreen.width = w;
    offscreen.height = h;
    const offCtx = offscreen.getContext("2d");
    if (!offCtx) return;

    // Read mask indices from the bitmap. drawImage paints background
    // pixels as opaque (R=G=B=0, A=255) — so we must NOT reuse this
    // buffer as the output, or background regions cover the video with
    // opaque black.
    offCtx.drawImage(bmp, 0, 0);
    const indexData = offCtx.getImageData(0, 0, w, h).data;

    const out = offCtx.createImageData(w, h);
    recolorMask(
      out.data,
      (p) => indexData[p * 4] - 1,
      w * h,
      labels,
      detections,
      hiddenLabelIds,
    );
    offCtx.putImageData(out, 0, 0);
    drawScaled(ctx, offscreen);
    return;
  }

  // Legacy fallback for older API builds that still emit nested int arrays.
  const masks = detections.masks;
  if (!masks) return;
  const maskHeight = masks.length;
  const maskWidth = masks[0]?.length ?? 0;
  if (maskWidth === 0 || maskHeight === 0) return;

  const offscreen = document.createElement("canvas");
  offscreen.width = maskWidth;
  offscreen.height = maskHeight;
  const offCtx = offscreen.getContext("2d");
  if (!offCtx) return;
  const imageData = offCtx.createImageData(maskWidth, maskHeight);
  recolorMask(
    imageData.data,
    (p) => masks[(p / maskWidth) | 0][p % maskWidth],
    maskWidth * maskHeight,
    labels,
    detections,
    hiddenLabelIds,
  );
  offCtx.putImageData(imageData, 0, 0);
  drawScaled(ctx, offscreen);
};

export const renderZone = (
  ctx: CanvasRenderingContext2D,
  direction: DashboardZoneDirection,
  center: number,
  thickness: number,
) => {
  const { width, height } = ctx.canvas;
  const lo = Math.max(0, center - thickness / 2);
  const hi = Math.min(1, center + thickness / 2);

  ctx.save();
  ctx.strokeStyle = "#ff0000";
  ctx.lineWidth = 2;
  ctx.setLineDash([10, 5]);

  const isXAxis =
    direction === DashboardZoneDirection.LeftToRight ||
    direction === DashboardZoneDirection.RightToLeft;

  if (isXAxis) {
    const xLo = lo * width;
    const xHi = hi * width;
    ctx.beginPath();
    ctx.moveTo(xLo, 0);
    ctx.lineTo(xLo, height);
    ctx.moveTo(xHi, 0);
    ctx.lineTo(xHi, height);
    ctx.stroke();
  } else {
    const yLo = lo * height;
    const yHi = hi * height;
    ctx.beginPath();
    ctx.moveTo(0, yLo);
    ctx.lineTo(width, yLo);
    ctx.moveTo(0, yHi);
    ctx.lineTo(width, yHi);
    ctx.stroke();
  }
  ctx.restore();
};
