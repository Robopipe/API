import type { NNDetections } from "../types/detections";

export interface SyncedFrame {
  /** Lower-32 bits of the source-frame device timestamp (microseconds). */
  ts: number;
  /**
   * Decoded video frame. Ownership transfers to the subscriber on emit —
   * the subscriber must call `bitmap.close()` after rendering.
   */
  bitmap: ImageBitmap;
  /**
   * Detections for this exact source frame. The subscriber owns
   * `detections.maskBitmap` if present and must close it after rendering.
   */
  detections: NNDetections;
}

interface PendingFrame {
  bitmap: ImageBitmap;
  capturedAt: number;
}

interface PendingDetection {
  detections: NNDetections;
  receivedAt: number;
}

/**
 * Sized to cover slow segmentation models whose end-to-end inference
 * latency can run 0.5-1.5 s. Frame-side cap (60) bounds GPU memory at
 * roughly two seconds of buffered video at 30 fps. Detection-side cap
 * (60) prevents unbounded growth if inference somehow outruns video.
 */
const MAX_PENDING_FRAMES = 60;
const MAX_PENDING_DETECTIONS = 60;
const MAX_FRAME_AGE_MS = 2000;
const MAX_DETECTION_AGE_MS = 2000;

/**
 * Joins WebRTC video frames (keyed by burned-in ts) with inference
 * detections (keyed by `ts_us`) and emits matched pairs. Either side can
 * arrive first. Stale entries on either side are evicted with their
 * associated GPU resources (ImageBitmap / maskBitmap) closed.
 *
 * Designed for a single subscriber (the synced renderer); ownership of
 * emitted bitmaps transfers to that subscriber.
 */
export class FrameMatcher {
  private pendingFrames = new Map<number, PendingFrame>();
  private pendingDetections = new Map<number, PendingDetection>();
  private subscribers = new Set<(synced: SyncedFrame) => void>();

  private matched = 0;
  private droppedFrames = 0;
  private droppedDetections = 0;

  pushFrame(ts: number, bitmap: ImageBitmap, capturedAt: number): void {
    const det = this.pendingDetections.get(ts);
    if (det) {
      this.pendingDetections.delete(ts);
      this.matched++;
      this.emit({ ts, bitmap, detections: det.detections });
      return;
    }
    this.pendingFrames.set(ts, { bitmap, capturedAt });
    this.evict(capturedAt);
  }

  pushDetections(
    ts: number,
    detections: NNDetections,
    receivedAt: number,
  ): void {
    const frame = this.pendingFrames.get(ts);
    if (frame) {
      this.pendingFrames.delete(ts);
      this.matched++;
      this.emit({ ts, bitmap: frame.bitmap, detections });
      return;
    }
    this.pendingDetections.set(ts, { detections, receivedAt });
    this.evict(receivedAt);
  }

  onMatch(cb: (synced: SyncedFrame) => void): () => void {
    this.subscribers.add(cb);
    return () => {
      this.subscribers.delete(cb);
    };
  }

  stats() {
    return {
      matched: this.matched,
      droppedFrames: this.droppedFrames,
      droppedDetections: this.droppedDetections,
      bufferedFrames: this.pendingFrames.size,
      bufferedDetections: this.pendingDetections.size,
    };
  }

  dispose(): void {
    for (const f of this.pendingFrames.values()) f.bitmap.close();
    for (const d of this.pendingDetections.values()) {
      d.detections.maskBitmap?.close?.();
    }
    this.pendingFrames.clear();
    this.pendingDetections.clear();
    this.subscribers.clear();
  }

  private emit(synced: SyncedFrame): void {
    for (const cb of this.subscribers) {
      try {
        cb(synced);
      } catch (e) {
        console.error("FrameMatcher subscriber threw:", e);
      }
    }
  }

  private evict(now: number): void {
    while (this.pendingFrames.size > MAX_PENDING_FRAMES) {
      const oldest = this.pendingFrames.entries().next().value;
      if (!oldest) break;
      const [ts, entry] = oldest;
      this.pendingFrames.delete(ts);
      entry.bitmap.close();
      this.droppedFrames++;
    }
    while (this.pendingDetections.size > MAX_PENDING_DETECTIONS) {
      const oldest = this.pendingDetections.entries().next().value;
      if (!oldest) break;
      const [ts, entry] = oldest;
      entry.detections.maskBitmap?.close?.();
      this.pendingDetections.delete(ts);
      this.droppedDetections++;
    }
    for (const [ts, entry] of this.pendingFrames) {
      if (now - entry.capturedAt > MAX_FRAME_AGE_MS) {
        this.pendingFrames.delete(ts);
        entry.bitmap.close();
        this.droppedFrames++;
      } else {
        break;
      }
    }
    for (const [ts, entry] of this.pendingDetections) {
      if (now - entry.receivedAt > MAX_DETECTION_AGE_MS) {
        entry.detections.maskBitmap?.close?.();
        this.pendingDetections.delete(ts);
        this.droppedDetections++;
      } else {
        break;
      }
    }
  }
}
