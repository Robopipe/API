import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { DashboardDetection, NNDetections } from "../../types/detections";
import {
  decodeTimestampBurnin,
  stripDimensions,
} from "../../utils/decodeTimestampBurnin";
import { FrameMatcher, type SyncedFrame } from "../../utils/frameMatcher";
import { CameraStreamContext } from "./cameraStreamContext";
import type { CameraStreamContextValue } from "./cameraStreamContext";

const ICE_SERVERS: RTCIceServer[] = [
  { urls: ["stun:stun.l.google.com:19302"] },
  ...(import.meta.env.VITE_TURN_SERVER_URL
    ? [
        {
          urls: [import.meta.env.VITE_TURN_SERVER_URL],
          username: import.meta.env.VITE_TURN_SERVER_USERNAME ?? "",
          credential: import.meta.env.VITE_TURN_SERVER_CREDENTIAL ?? "",
        },
      ]
    : []),
];

const ICE_GATHERING_TIMEOUT_MS = 5000;
// Shared reconnect policy for both the WebRTC video and the detections WS:
// retry forever with capped exponential backoff. Dashboards run unattended,
// so both transports must self-heal after outages of any length.
const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 15000;
// ICE "disconnected" is often transient and recovers on its own; only
// renegotiate if it doesn't return to "connected" within the grace period.
const DISCONNECTED_GRACE_MS = 4000;
// No new decoded video frame for this long while the peer connection still
// reports "connected" → treat as a silent stall and renegotiate.
const VIDEO_STARVATION_TIMEOUT_MS = 5000;

const reconnectDelayMs = (attempt: number) =>
  Math.min(RECONNECT_BASE_DELAY_MS * 2 ** attempt, RECONNECT_MAX_DELAY_MS);

export interface CameraStreamProviderProps {
  children: ReactNode;
}

/**
 * Owns the WebRTC peer connection, detections WebSocket, frame matcher,
 * and frame capture loop for the single camera/stream this dashboard
 * targets (from window.DASHBOARD_CONFIG). Mirrors Studio's
 * CameraStreamProvider one-to-one.
 */
export const CameraStreamProvider = ({
  children,
}: CameraStreamProviderProps) => {
  const { apiBase } = window.DASHBOARD_CONFIG;

  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [replayEnded, setReplayEnded] = useState(false);

  const [detections, setDetections] = useState<NNDetections>({
    detections: [],
  });
  const [isDetectionsConnected, setIsDetectionsConnected] = useState(false);
  const [detectionsError, setDetectionsError] = useState<string | null>(null);

  const subscribersRef = useRef<Set<(d: NNDetections) => void>>(new Set());
  const syncedSubscribersRef = useRef<Set<(s: SyncedFrame) => void>>(new Set());
  const matcherRef = useRef<FrameMatcher | null>(null);
  // Mirror of `replayEnded` readable from timers/handlers in the WebRTC
  // effect without stale-closure issues. A finished replay must gate every
  // reconnect path: the backend closes the pc after EOF, and renegotiating
  // would restart the replay in a loop.
  const replayEndedRef = useRef(false);
  // Stamped by the capture loop on every decoded frame; read by the
  // starvation watchdog in the WebRTC effect.
  const lastFrameAtRef = useRef(0);

  const subscribeDetections = useCallback((cb: (d: NNDetections) => void) => {
    subscribersRef.current.add(cb);
    return () => {
      subscribersRef.current.delete(cb);
    };
  }, []);

  const subscribeSyncedFrames = useCallback((cb: (s: SyncedFrame) => void) => {
    syncedSubscribersRef.current.add(cb);
    return () => {
      syncedSubscribersRef.current.delete(cb);
    };
  }, []);

  // --- WebRTC ---------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    let peer: RTCPeerConnection | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
    let graceTimeout: ReturnType<typeof setTimeout> | null = null;
    let attempts = 0;
    // Distinguishes the initial "Connecting..." state from a lost
    // connection ("reconnecting", dimmed last frame) in the UI.
    let hasConnectedOnce = false;

    replayEndedRef.current = false;
    setReplayEnded(false);

    const clearGraceTimer = () => {
      if (graceTimeout) {
        clearTimeout(graceTimeout);
        graceTimeout = null;
      }
    };

    const teardownPeer = () => {
      clearGraceTimer();
      if (peer) {
        peer.close();
        peer = null;
      }
      setMediaStream(null);
      setIsStreaming(false);
    };

    const scheduleReconnect = () => {
      if (cancelled || replayEndedRef.current || reconnectTimeout) return;
      teardownPeer();
      if (hasConnectedOnce) setIsReconnecting(true);
      const delay = reconnectDelayMs(attempts);
      attempts += 1;
      reconnectTimeout = setTimeout(() => {
        reconnectTimeout = null;
        void connect();
      }, delay);
    };

    const connect = async () => {
      if (cancelled || replayEndedRef.current) return;
      try {
        setStreamError(null);
        const pc = new RTCPeerConnection({
          iceServers: ICE_SERVERS,
          iceTransportPolicy: "all",
        });
        peer = pc;
        pc.addTransceiver("video", { direction: "recvonly" });

        const eventsChannel = pc.createDataChannel("events");
        eventsChannel.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data as string);
            if (msg.event === "eof") {
              replayEndedRef.current = true;
              setReplayEnded(true);
            }
          } catch {
            // ignore malformed messages
          }
        };

        pc.addEventListener("track", (event) => {
          if (cancelled || peer !== pc) return;
          const incoming = event.streams[0] ?? null;
          setMediaStream(incoming);
          setIsStreaming(true);
          setIsReconnecting(false);
          hasConnectedOnce = true;
          lastFrameAtRef.current = performance.now();
        });

        const iceCandidates: RTCIceCandidate[] = [];
        pc.addEventListener("icecandidate", (event) => {
          if (event.candidate) iceCandidates.push(event.candidate);
        });

        pc.addEventListener("connectionstatechange", () => {
          if (cancelled || peer !== pc) return;
          if (pc.connectionState === "connected") {
            attempts = 0;
            hasConnectedOnce = true;
            clearGraceTimer();
            setIsStreaming(true);
            setIsReconnecting(false);
            setStreamError(null);
            lastFrameAtRef.current = performance.now();
          } else if (
            pc.connectionState === "failed" ||
            pc.connectionState === "closed"
          ) {
            setStreamError("Connection lost");
            scheduleReconnect();
          } else if (pc.connectionState === "disconnected") {
            if (!graceTimeout) {
              graceTimeout = setTimeout(() => {
                graceTimeout = null;
                if (peer === pc && pc.connectionState === "disconnected") {
                  setStreamError("Connection lost");
                  scheduleReconnect();
                }
              }, DISCONNECTED_GRACE_MS);
            }
          }
        });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        await new Promise<void>((resolve) => {
          const timeout = setTimeout(resolve, ICE_GATHERING_TIMEOUT_MS);
          const check = () => {
            if (pc.iceGatheringState === "complete") {
              clearTimeout(timeout);
              resolve();
            } else {
              setTimeout(check, 100);
            }
          };
          check();
        });

        if (cancelled || peer !== pc) return;

        const offerUrl = `${apiBase}/video`;
        const response = await fetch(offerUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sdp: offer.sdp,
            type: offer.type,
            candidates: iceCandidates.map((c) => ({
              candidate: c.candidate,
              sdpMLineIndex: c.sdpMLineIndex,
              sdpMid: c.sdpMid,
            })),
          }),
        });
        if (!response.ok) {
          throw new Error(
            `Failed to get answer from server: ${response.statusText}`,
          );
        }
        const answerData = await response.json();
        if (cancelled || peer !== pc) return;
        await pc.setRemoteDescription(new RTCSessionDescription(answerData));

        if (Array.isArray(answerData.candidates)) {
          for (const candidate of answerData.candidates) {
            try {
              await pc.addIceCandidate(new RTCIceCandidate(candidate));
            } catch (err) {
              console.warn("Failed to add ICE candidate:", err);
            }
          }
        }
      } catch (err) {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : "Unknown error";
        setStreamError(message);
        setIsStreaming(false);
        console.error("WebRTC error:", err);
        scheduleReconnect();
      }
    };

    // Catches streams that freeze while the peer connection still reports
    // "connected" (encoder death, backend video queue stall) — no
    // connection state event fires for those.
    const watchdog = setInterval(() => {
      if (cancelled || replayEndedRef.current) return;
      if (document.hidden) {
        // rVFC throttles in background tabs; keep the stamp fresh so
        // returning to the tab doesn't look like starvation.
        lastFrameAtRef.current = performance.now();
        return;
      }
      if (!peer || peer.connectionState !== "connected") return;
      if (
        performance.now() - lastFrameAtRef.current >
        VIDEO_STARVATION_TIMEOUT_MS
      ) {
        setStreamError("Video stalled");
        scheduleReconnect();
      }
    }, 1000);

    void connect();

    return () => {
      cancelled = true;
      clearInterval(watchdog);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      clearGraceTimer();
      if (peer) peer.close();
      setMediaStream(null);
      setIsStreaming(false);
      setIsReconnecting(false);
    };
  }, [apiBase]);

  // --- Matcher lifecycle ---------------------------------------------
  useEffect(() => {
    const matcher = new FrameMatcher();
    matcher.onMatch((synced) => {
      if (syncedSubscribersRef.current.size === 0) {
        synced.bitmap.close();
        synced.detections.maskBitmap?.close?.();
        return;
      }
      for (const cb of syncedSubscribersRef.current) {
        try {
          cb(synced);
        } catch (e) {
          console.error("Synced frame subscriber threw:", e);
        }
      }
    });
    matcherRef.current = matcher;

    // TODO: remove. Periodic stats so we can see if detection rate is
    // outrunning the video rate (high droppedDetections) or vice versa
    // (high droppedFrames).
    let prevPushedFrames = 0;
    let prevPushedDetections = 0;
    let prevMatched = 0;
    const statsInterval = setInterval(() => {
      const s = matcher.stats();
      const pushedF = s.matched + s.droppedFrames + s.bufferedFrames;
      const pushedD = s.matched + s.droppedDetections + s.bufferedDetections;
      const dF = pushedF - prevPushedFrames;
      const dD = pushedD - prevPushedDetections;
      const dM = s.matched - prevMatched;
      prevPushedFrames = pushedF;
      prevPushedDetections = pushedD;
      prevMatched = s.matched;
      console.log(
        `[SYNC] matched=${s.matched}(+${dM}/s) frames=+${dF}/s dets=+${dD}/s ` +
          `bufF=${s.bufferedFrames} bufD=${s.bufferedDetections} ` +
          `dropped=${s.droppedFrames}f/${s.droppedDetections}d`,
      );
    }, 1000);

    return () => {
      clearInterval(statsInterval);
      matcherRef.current = null;
      matcher.dispose();
    };
  }, []);

  // --- Frame capture loop --------------------------------------------
  useEffect(() => {
    if (!mediaStream) return;

    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.autoplay = true;
    video.srcObject = mediaStream;
    void video.play().catch(() => {});

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;

    let cancelled = false;
    let rvfcId: number | undefined;

    const onFrame: VideoFrameRequestCallback = () => {
      if (cancelled) return;
      lastFrameAtRef.current = performance.now();
      const w = video.videoWidth;
      const h = video.videoHeight;
      if (w === 0 || h === 0) {
        rvfcId = video.requestVideoFrameCallback(onFrame);
        return;
      }

      const { stripWidth, stripHeight } = stripDimensions(w);
      if (stripWidth > w || stripHeight > h) {
        rvfcId = video.requestVideoFrameCallback(onFrame);
        return;
      }

      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }

      ctx.drawImage(video, 0, 0);
      const stripData = ctx.getImageData(0, 0, stripWidth, stripHeight);
      const ts = decodeTimestampBurnin(stripData, w);
      const capturedAt = performance.now();

      const bitmapPromise =
        ts !== null && matcherRef.current ? createImageBitmap(canvas) : null;

      rvfcId = video.requestVideoFrameCallback(onFrame);

      if (bitmapPromise) {
        bitmapPromise.then(
          (bitmap) => {
            if (cancelled || !matcherRef.current) {
              bitmap.close();
              return;
            }
            matcherRef.current.pushFrame(ts!, bitmap, capturedAt);
          },
          (err) => {
            console.error("createImageBitmap failed:", err);
          },
        );
      }
    };

    rvfcId = video.requestVideoFrameCallback(onFrame);

    return () => {
      cancelled = true;
      if (rvfcId !== undefined) {
        video.cancelVideoFrameCallback(rvfcId);
      }
      video.srcObject = null;
      video.pause();
    };
  }, [mediaStream]);

  // --- Detections WebSocket ------------------------------------------
  useEffect(() => {
    // When the dashboard is in the awaiting-model state (restored from disk but
    // no NN deployed), skip the detections WS entirely. The backend producer
    // would terminate immediately via ProducerTerminated, causing the WS to
    // cycle through its max reconnect attempts and surface a cosmetic error.
    if (window.DASHBOARD_CONFIG.awaitingModel) return;

    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectAttempts = 0;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const reportDashboardDetections = async (
      dashboardDetections: DashboardDetection[],
    ) => {
      const { remoteBackendUrl } = window.DASHBOARD_CONFIG;
      if (!remoteBackendUrl) return;

      const timestamp = new Date().toISOString();
      const events = dashboardDetections.map((d) => ({
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
        // best effort
      }
    };

    const connect = () => {
      if (cancelled) return;
      const wsUrl = apiBase
        .replace(/^https:\/\//, "wss://")
        .replace(/^http:\/\//, "ws://");
      const endpoint = `${wsUrl}/nn`;

      try {
        ws = new WebSocket(endpoint);

        ws.onopen = () => {
          if (cancelled) return;
          setIsDetectionsConnected(true);
          setDetectionsError(null);
          reconnectAttempts = 0;
        };

        ws.onmessage = async (event) => {
          if (cancelled) return;
          try {
            const data = JSON.parse(event.data);
            const parsed: NNDetections = Array.isArray(data)
              ? { detections: data }
              : data;

            if (parsed.masks_png) {
              try {
                const raw = atob(parsed.masks_png);
                const buf = new Uint8Array(raw.length);
                for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
                const blob = new Blob([buf], { type: "image/png" });
                parsed.maskBitmap = await createImageBitmap(blob);
              } catch {
                // fall through to legacy `masks` array
              }
              if (cancelled) {
                parsed.maskBitmap?.close?.();
                return;
              }
            }

            if (parsed.dashboard_detections?.length) {
              void reportDashboardDetections(parsed.dashboard_detections);
            }

            // Notify subscribers via callback path. We deliberately do NOT
            // call setDetections here — the legacy `detections` state is
            // unused by every consumer (all of them use onDetections), and
            // updating it 12×/s thrashes the React tree (provider context
            // value churn → all useCameraStream consumers re-render),
            // which starves requestVideoFrameCallback on the off-DOM
            // capture video and breaks the matcher's frame ingestion.
            subscribersRef.current.forEach((cb) => cb(parsed));

            if (parsed.ts_us !== undefined && matcherRef.current) {
              const ts32 = parsed.ts_us % 0x100000000;
              let detectionsForMatcher: NNDetections = parsed;
              if (parsed.maskBitmap) {
                try {
                  const clonedMask = await createImageBitmap(parsed.maskBitmap);
                  detectionsForMatcher = { ...parsed, maskBitmap: clonedMask };
                } catch {
                  const { maskBitmap: _drop, ...rest } = parsed;
                  detectionsForMatcher = rest as NNDetections;
                }
              }
              matcherRef.current.pushDetections(
                ts32,
                detectionsForMatcher,
                performance.now(),
              );
            }

            // The matcher took its own cloned maskBitmap above (or none);
            // close the original so we don't leak GPU memory.
            parsed.maskBitmap?.close?.();
          } catch {
            // ignore malformed messages
          }
        };

        ws.onerror = () => {
          if (cancelled) return;
          setDetectionsError("WebSocket connection error");
        };

        ws.onclose = () => {
          if (cancelled) return;
          setIsDetectionsConnected(false);
          ws = null;
          // Same policy as the WebRTC effect: retry forever so the
          // dashboard recovers from arbitrarily long backend outages
          // without a page reload.
          const delay = reconnectDelayMs(reconnectAttempts);
          reconnectAttempts += 1;
          reconnectTimeout = setTimeout(connect, delay);
        };
      } catch (err) {
        setDetectionsError(
          err instanceof Error ? err.message : "Failed to connect to NN stream",
        );
      }
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
      setDetections({ detections: [] });
      setIsDetectionsConnected(false);
    };
  }, [apiBase]);

  const value: CameraStreamContextValue = {
    mediaStream,
    isStreaming,
    isReconnecting,
    streamError,
    replayEnded,
    detections,
    isDetectionsConnected,
    detectionsError,
    subscribeDetections,
    subscribeSyncedFrames,
  };

  return (
    <CameraStreamContext.Provider value={value}>
      {children}
    </CameraStreamContext.Provider>
  );
};
