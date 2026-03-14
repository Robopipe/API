import { DashboardLineDirection, type Label } from "../types";
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

const isBBDetection = (detection: NNDetection): detection is BBDetection => {
  return (detection as BBDetection).coords !== undefined;
};

const isClassificationDetection = (
  detection: NNDetection,
): detection is ClassificationDetection => {
  return !("coords" in detection) && !("points" in detection);
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

  // render rectangle with semi-transparent fill
  ctx.strokeStyle = label.color;
  ctx.fillStyle = `${label.color}33`; // add alpha for transparency
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);
  ctx.fillRect(x, y, w, h);
  ctx.font = "14px Inter";
  ctx.fillStyle = label.color;
  const text = `${label.name} (${(detection.confidence * 100).toFixed(1)}%)`;
  const textWidth = ctx.measureText(text).width;
  const textHeight = 16; // approximate height
  ctx.fillRect(x, y - textHeight, textWidth + 4, textHeight);
  ctx.fillStyle = "#fff";
  ctx.fillText(text, x + 2, y - 4);
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

export const renderSegmentationMask = (
  ctx: CanvasRenderingContext2D,
  labels: Label[],
  detections: NNDetections,
) => {
  const masks = detections.masks;
  if (!masks) return;
  const maskHeight = masks.length;
  const maskWidth = masks[0]?.length ?? 0;
  if (maskWidth === 0 || maskHeight === 0) return;

  const { width: canvasWidth, height: canvasHeight } = ctx.canvas;

  // Draw mask at native resolution using ImageData to avoid overlap artifacts
  // from semi-transparent fillRect calls that cause visible grid lines
  const offscreen = document.createElement("canvas");
  offscreen.width = maskWidth;
  offscreen.height = maskHeight;
  const offCtx = offscreen.getContext("2d")!;
  const imageData = offCtx.createImageData(maskWidth, maskHeight);
  const data = imageData.data;

  for (let y = 0; y < maskHeight; y++) {
    for (let x = 0; x < maskWidth; x++) {
      const labelId = masks[y][x];
      if (labelId === -1) continue; // background
      const detLabel = detections.detections[labelId];
      const label = labels[detLabel.label];
      const color = label.color;
      const r = parseInt(color.slice(1, 3), 16);
      const g = parseInt(color.slice(3, 5), 16);
      const b = parseInt(color.slice(5, 7), 16);
      const idx = (y * maskWidth + x) * 4;
      data[idx] = r;
      data[idx + 1] = g;
      data[idx + 2] = b;
      data[idx + 3] = 0x88; // ~53% alpha for transparency
    }
  }

  offCtx.putImageData(imageData, 0, 0);

  // Scale up to canvas size with smooth edges
  const prevSmoothing = ctx.imageSmoothingEnabled;
  const prevQuality = ctx.imageSmoothingQuality;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(offscreen, 0, 0, canvasWidth, canvasHeight);
  ctx.imageSmoothingEnabled = prevSmoothing;
  ctx.imageSmoothingQuality = prevQuality;
};

export const renderLine = (
  ctx: CanvasRenderingContext2D,
  direction: DashboardLineDirection,
  position: number,
) => {
  const { width, height } = ctx.canvas;
  ctx.strokeStyle = "#ff0000";
  ctx.lineWidth = 2;
  ctx.setLineDash([10, 5]);
  ctx.beginPath();
  if (direction === DashboardLineDirection.HORIZONTAL) {
    const y = position * height;
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
  } else {
    const x = position * width;
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
  }
  ctx.stroke();
};
