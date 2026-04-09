import type { DashboardDetection, NNDetections } from "../types/detections";

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

type Listener = () => void;

export interface DetectionsSnapshot {
  detections: NNDetections;
  isConnected: boolean;
  error: string | null;
}

export const EMPTY_SNAPSHOT: DetectionsSnapshot = {
  detections: { detections: [] },
  isConnected: false,
  error: null,
};

class DetectionsManager {
  // --- subscribers (useSyncExternalStore) ---
  private listeners = new Set<Listener>();
  private snapshot: DetectionsSnapshot = EMPTY_SNAPSHOT;

  // --- per-instance onDetections callbacks ---
  private callbacks = new Set<(d: NNDetections) => void>();

  // --- ws internals ---
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  // --- frame capture for violation pictures ---
  private videoElement: HTMLVideoElement | null = null;
  private canvasElement: HTMLCanvasElement | null = null;
  private lastCaptureTime = 0;
  private static CAPTURE_COOLDOWN_MS = 5000;

  // ---- external-store contract ----

  subscribe = (listener: Listener): (() => void) => {
    const needsConnect = this.listeners.size === 0;
    this.listeners.add(listener);
    if (needsConnect) this.connect();
    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0) this.disconnect();
    };
  };

  getSnapshot = (): DetectionsSnapshot => this.snapshot;

  // ---- callback registration (for onDetections) ----

  addCallback(cb: (d: NNDetections) => void) {
    this.callbacks.add(cb);
  }

  removeCallback(cb: (d: NNDetections) => void) {
    this.callbacks.delete(cb);
  }

  // ---- frame capture refs ----

  setVideoRef(el: HTMLVideoElement | null) {
    this.videoElement = el;
  }

  setCanvasRef(el: HTMLCanvasElement | null) {
    this.canvasElement = el;
  }

  // ---- private ----

  private emit() {
    for (const l of this.listeners) l();
  }

  private setSnapshot(patch: Partial<DetectionsSnapshot>) {
    this.snapshot = { ...this.snapshot, ...patch };
    this.emit();
  }

  private connect = () => {
    const wsUrl = window.DASHBOARD_CONFIG.apiBase
      .replace(/^https:\/\//, "wss://")
      .replace(/^http:\/\//, "ws://");

    const endpoint = `${wsUrl}/nn`;

    try {
      const ws = new WebSocket(endpoint);
      this.ws = ws;

      ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.setSnapshot({ isConnected: true, error: null });
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const parsed: NNDetections = Array.isArray(data)
            ? { detections: data }
            : data;
          if (parsed.dashboard_detections?.length) {
            void this.reportDashboardDetections(parsed.dashboard_detections);
          }
          if (parsed.violation_event_ids?.length) {
            void this.captureAndUploadViolationPicture(
              parsed.violation_event_ids,
            );
          }
          this.setSnapshot({ detections: parsed });
          for (const cb of this.callbacks) cb(parsed);
        } catch {
          // noop
        }
      };

      ws.onerror = () => {
        this.setSnapshot({ error: "WebSocket connection error" });
      };

      ws.onclose = () => {
        this.ws = null;
        this.setSnapshot({ isConnected: false });

        // Only reconnect if there are still active subscribers
        if (this.listeners.size === 0) return;

        if (this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          this.reconnectAttempts += 1;
          this.reconnectTimeout = setTimeout(this.connect, RECONNECT_DELAY_MS);
        } else {
          this.setSnapshot({
            error: "Connection lost. Max reconnect attempts reached.",
          });
        }
      };
    } catch (err) {
      this.setSnapshot({
        error:
          err instanceof Error ? err.message : "Failed to connect to NN stream",
      });
    }
  };

  private async reportDashboardDetections(detections: DashboardDetection[]) {
    const { remoteBackendUrl, apiBase } = window.DASHBOARD_CONFIG;
    if (!remoteBackendUrl) return;

    const timestamp = new Date().toISOString();
    const events = detections.map((d) => ({
      id: crypto.randomUUID(),
      test_case_id: d.test_case_id,
      type: d.type,
      timestamp,
    }));

    try {
      const resp = await fetch(remoteBackendUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(events),
        signal: AbortSignal.timeout(5000),
      });
      if (resp.ok) return;
    } catch {
      // fall through to camera API cache
    }

    try {
      await fetch(`${apiBase}/dashboard/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(events),
        signal: AbortSignal.timeout(5000),
      });
    } catch {
      // nothing we can do
    }
  }

  private captureCompositeFrame(): Blob | null {
    const video = this.videoElement;
    const overlay = this.canvasElement;
    if (!video || !overlay || !overlay.width || !overlay.height) return null;

    const canvas = document.createElement("canvas");
    canvas.width = overlay.width;
    canvas.height = overlay.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    ctx.drawImage(overlay, 0, 0);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    const byteString = atob(dataUrl.split(",")[1]);
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: "image/jpeg" });
  }

  private async captureAndUploadViolationPicture(eventIds: number[]) {
    const now = Date.now();
    if (now - this.lastCaptureTime < DetectionsManager.CAPTURE_COOLDOWN_MS) return;

    const blob = this.captureCompositeFrame();
    if (!blob) return;

    this.lastCaptureTime = now;

    const formData = new FormData();
    formData.append("picture", blob, "violation.jpg");
    formData.append("event_ids", JSON.stringify(eventIds));

    try {
      await fetch(
        `${window.DASHBOARD_CONFIG.apiBase}/dashboard/events/picture`,
        {
          method: "POST",
          body: formData,
          signal: AbortSignal.timeout(10000),
        },
      );
    } catch {
      // Best effort — don't block the detection pipeline
    }
  }

  private disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.reconnectAttempts = 0;
    this.snapshot = EMPTY_SNAPSHOT;
  }
}

export const detectionsManager = new DetectionsManager();
