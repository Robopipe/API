import { createContext } from "react";
import type { NNDetections } from "../../types/detections";
import type { SyncedFrame } from "../../utils/frameMatcher";

export interface CameraStreamSnapshot {
  mediaStream: MediaStream | null;
  isStreaming: boolean;
  /**
   * True while a previously working video connection is down and the
   * provider is auto-renegotiating. Detections may still be flowing —
   * the two transports fail independently.
   */
  isReconnecting: boolean;
  streamError: string | null;
  replayEnded: boolean;
  detections: NNDetections;
  isDetectionsConnected: boolean;
  detectionsError: string | null;
}

export interface CameraStreamContextValue extends CameraStreamSnapshot {
  /**
   * Register a callback invoked on every detections WS message. Returns
   * an unsubscribe function. Avoids forcing callback-only consumers
   * (renderers, violation handlers) to re-render on every message.
   */
  subscribeDetections: (cb: (detections: NNDetections) => void) => () => void;
  /**
   * Register a callback invoked when a video frame and its matching
   * inference detections have both arrived. Subscriber takes ownership of
   * `synced.bitmap` and `synced.detections.maskBitmap` and must close
   * them after rendering.
   */
  subscribeSyncedFrames: (cb: (synced: SyncedFrame) => void) => () => void;
}

export const CameraStreamContext =
  createContext<CameraStreamContextValue | null>(null);
