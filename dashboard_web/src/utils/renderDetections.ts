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
  scale?: number,
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

/**
 * Word-wrap `text` to `maxWidth` pixels using the current canvas font.
 * Splits on spaces first; hard-breaks any token that is still too wide.
 * Returns an array of lines.
 */
const wrapText = (
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string[] => {
  const lines: string[] = [];
  for (const paragraph of text.split("\n")) {
    const words = paragraph.split(" ");
    let current = "";
    for (const word of words) {
      const candidate = current ? `${current} ${word}` : word;
      if (ctx.measureText(candidate).width <= maxWidth) {
        current = candidate;
      } else {
        if (current) lines.push(current);
        // Hard-break a single word that is wider than maxWidth
        if (ctx.measureText(word).width > maxWidth) {
          let chunk = "";
          for (const ch of word) {
            if (ctx.measureText(chunk + ch).width > maxWidth) {
              lines.push(chunk);
              chunk = ch;
            } else {
              chunk += ch;
            }
          }
          current = chunk;
        } else {
          current = word;
        }
      }
    }
    if (current) lines.push(current);
  }
  return lines.length ? lines : [""];
};

export const renderBBoxDetection: DetectionRenderer = (
  ctx,
  labels,
  detection,
  scale = 1,
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
  const sev =
    detection.severity ??
    (violations?.some((v) => v.severity === "ALERT")
      ? "ALERT"
      : violations?.some((v) => v.severity === "WARNING")
        ? "WARNING"
        : undefined);
  const isAlert = sev === "ALERT";
  const isWarning = sev === "WARNING";
  const isHighlighted = isAlert || isWarning;
  // Parent-case child: inside a violating parent, carries no violations entry.
  // These keep their label color while the parent box shows the severity color.
  const isParentCaseChild = detection.role === "child" && !violations?.length;

  const borderColor =
    isParentCaseChild || !isHighlighted
      ? label.color
      : isAlert
        ? ALERT_BORDER
        : WARNING_BORDER;
  const fillColor =
    isParentCaseChild || !isHighlighted
      ? `${label.color}33`
      : isAlert
        ? ALERT_FILL
        : WARNING_FILL;
  const labelBg =
    isParentCaseChild || !isHighlighted
      ? label.color
      : isAlert
        ? ALERT_LABEL_BG
        : WARNING_LABEL_BG;
  const labelTextColor =
    !isParentCaseChild && isWarning ? "rgba(0,0,0,0.9)" : "#fff";

  // No ID prefix on highlighted boxes.
  const idPrefix =
    !isHighlighted && detection.display_id != null
      ? `#${detection.display_id} `
      : "";

  // Build label text by role:
  //   parent  → limit names (one per line, filtered by multiLimitMode upstream)
  //   child   → label name (no confidence)
  //   plain   → label name + confidence
  let rawText: string;
  if (detection.role === "parent" && violations?.length) {
    rawText = violations.map((v) => v.limit_name).join("\n");
  } else if (isHighlighted) {
    rawText = label.name;
  } else {
    rawText = `${idPrefix}${label.name} (${(detection.confidence * 100).toFixed(1)}%)`;
  }

  const font = isHighlighted
    ? `500 ${Math.round(12 * scale)}px 'Space Grotesk', Inter, sans-serif`
    : `${Math.round(14 * scale)}px Inter`;

  // Rectangle
  ctx.strokeStyle = borderColor;
  ctx.fillStyle = fillColor;
  ctx.lineWidth = scale;
  ctx.strokeRect(x, y, w, h);
  ctx.fillRect(x, y, w, h);

  // Text label above the bounding box.
  // Parent: one limit name per line, no word-wrap within a name.
  // Others: word-wrap to box width.
  ctx.font = font;
  const lineHeight = 16 * scale;
  const padding = (isHighlighted ? 8 : 2) * scale;
  const maxLineWidth = Math.max(w, 140 * scale);
  const textLines =
    detection.role === "parent"
      ? rawText.split("\n")
      : wrapText(ctx, rawText, maxLineWidth);
  const numLines = textLines.length;
  const labelWidth =
    Math.max(...textLines.map((l) => ctx.measureText(l).width)) + padding * 2;
  const labelHeight = lineHeight * numLines + (isHighlighted ? 4 * scale : 0);

  ctx.fillStyle = labelBg;
  ctx.fillRect(x - scale, y - labelHeight, labelWidth, labelHeight);
  ctx.fillStyle = labelTextColor;
  for (let i = 0; i < numLines; i++) {
    ctx.fillText(
      textLines[i],
      x - scale + padding,
      y - labelHeight + lineHeight * (i + 1) - (isHighlighted ? 5 * scale : 4 * scale),
    );
  }
};

export const renderClassificationDetection: DetectionRenderer = (
  ctx,
  labels,
  detection,
  scale = 1,
) => {
  if (!isClassificationDetection(detection)) return;
  const label = labels[detection.label];
  const text = `${label.name} (${(detection.confidence * 100).toFixed(1)}%)`;
  ctx.font = `${Math.round(16 * scale)}px Inter`;
  ctx.fillStyle = label.color;
  ctx.fillText(text, 10 * scale, 20 * scale);
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
  scale = 1,
) => {
  const { width, height } = ctx.canvas;
  const lo = Math.max(0, center - thickness / 2);
  const hi = Math.min(1, center + thickness / 2);

  ctx.save();
  ctx.strokeStyle = "#ff0000";
  ctx.lineWidth = 2 * scale;
  ctx.setLineDash([10 * scale, 5 * scale]);

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
