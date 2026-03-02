import type { NNDetections } from "../types/detections";

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
