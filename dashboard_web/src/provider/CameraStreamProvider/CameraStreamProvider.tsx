import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type {
  DashboardDetection,
  NNDetections,
} from "../../types/detections";
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
const DETECTIONS_RECONNECT_DELAY_MS = 3000;
const DETECTIONS_MAX_RECONNECT_ATTEMPTS = 10;
// Cap on per-tracker buffered violation frames. Anything beyond this is
// stale state from trackers that never produced a commit (wrong-direction
// exits, etc.). Eviction is LRU on insertion order.
const VIOLATION_FRAME_BUFFER_CAP = 50;

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
  const [streamError, setStreamError] = useState<string | null>(null);

  const [detections, setDetections] = useState<NNDetections>({ detections: [] });
  const [isDetectionsConnected, setIsDetectionsConnected] = useState(false);
  const [detectionsError, setDetectionsError] = useState<string | null>(null);

  const subscribersRef = useRef<Set<(d: NNDetections) => void>>(new Set());
  const syncedSubscribersRef = useRef<Set<(s: SyncedFrame) => void>>(new Set());
  const matcherRef = useRef<FrameMatcher | null>(null);
  const displayCanvasRef = useRef<HTMLCanvasElement | null>(null);
  // tracker_id -> closest-to-zone-center in-zone violation frame seen so
  // far. Each entry stores the rendered blob along with the bbox-center's
  // distance to zoneCenter at the moment of capture; new in-zone frames
  // overwrite the entry only when their distance is smaller. Consumed at
  // commit (zone exit), so the saved picture is the moment the object
  // was best-framed within the zone, not the last frame before exit.
  const violationFrameBufferRef = useRef<
    Map<number, { blob: Blob; distance: number }>
  >(new Map());

  const subscribeDetections = useCallback(
    (cb: (d: NNDetections) => void) => {
      subscribersRef.current.add(cb);
      return () => {
        subscribersRef.current.delete(cb);
      };
    },
    [],
  );

  const subscribeSyncedFrames = useCallback(
    (cb: (s: SyncedFrame) => void) => {
      syncedSubscribersRef.current.add(cb);
      return () => {
        syncedSubscribersRef.current.delete(cb);
      };
    },
    [],
  );

  const setDisplayCanvas = useCallback((el: HTMLCanvasElement | null) => {
    displayCanvasRef.current = el;
  }, []);

  const bufferViolationFrame = useCallback(
    (
      entries: { trackerId: number; distance: number }[],
      frame: Blob,
    ) => {
      if (entries.length === 0) return;
      const buf = violationFrameBufferRef.current;
      for (const { trackerId, distance } of entries) {
        const existing = buf.get(trackerId);
        // Keep whichever frame is closer to the zone center. Equal
        // distances keep the existing entry (earlier frame wins ties).
        if (existing !== undefined && existing.distance <= distance) {
          continue;
        }
        if (existing !== undefined) buf.delete(trackerId);
        buf.set(trackerId, { blob: frame, distance });
      }
      while (buf.size > VIOLATION_FRAME_BUFFER_CAP) {
        const oldest = buf.keys().next().value;
        if (oldest === undefined) break;
        buf.delete(oldest);
      }
    },
    [],
  );

  // --- WebRTC ---------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    let peer: RTCPeerConnection | null = null;

    const init = async () => {
      try {
        setStreamError(null);
        const pc = new RTCPeerConnection({
          iceServers: ICE_SERVERS,
          iceTransportPolicy: "all",
        });
        peer = pc;
        pc.addTransceiver("video", { direction: "recvonly" });

        pc.addEventListener("track", (event) => {
          if (cancelled) return;
          const incoming = event.streams[0] ?? null;
          setMediaStream(incoming);
          setIsStreaming(true);
        });

        const iceCandidates: RTCIceCandidate[] = [];
        pc.addEventListener("icecandidate", (event) => {
          if (event.candidate) iceCandidates.push(event.candidate);
        });

        pc.addEventListener("connectionstatechange", () => {
          if (cancelled) return;
          if (
            pc.connectionState === "failed" ||
            pc.connectionState === "disconnected"
          ) {
            setIsStreaming(false);
            setStreamError("Connection lost");
          } else if (pc.connectionState === "connected") {
            setIsStreaming(true);
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

        if (cancelled) return;

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
        if (cancelled) return;
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
      }
    };

    init();

    return () => {
      cancelled = true;
      if (peer) peer.close();
      setMediaStream(null);
      setIsStreaming(false);
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
        ts !== null && matcherRef.current
          ? createImageBitmap(canvas)
          : null;

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

    const snapshotDisplayCanvas = (): Promise<Blob | null> => {
      const display = displayCanvasRef.current;
      if (!display || !display.width || !display.height)
        return Promise.resolve(null);
      return new Promise((resolve) =>
        display.toBlob(resolve, "image/jpeg", 0.85),
      );
    };

    const uploadViolationPictures = async (
      events: { event_id: number; tracker_id: number }[],
    ) => {
      // Group event IDs by tracker_id: each tracker shares one buffered frame
      // for all of its violations on this commit.
      const byTracker = new Map<number, number[]>();
      for (const ev of events) {
        let list = byTracker.get(ev.tracker_id);
        if (!list) {
          list = [];
          byTracker.set(ev.tracker_id, list);
        }
        list.push(ev.event_id);
      }

      const buf = violationFrameBufferRef.current;
      console.log(
        "[violation-picture] commit received",
        events,
        "buffered_trackers=",
        Array.from(buf.keys()),
      );
      for (const [tid, eventIds] of byTracker) {
        const entry = buf.get(tid);
        let blob: Blob | null | undefined = entry?.blob;
        const usedBuffered = blob !== undefined;
        buf.delete(tid);
        if (!blob) {
          // No in-zone snapshot was buffered (e.g. tracker never appeared
          // with a live violation flag while in the zone). Fall back to the
          // current display so the event still gets a picture.
          blob = await snapshotDisplayCanvas();
        }
        if (!blob) {
          console.warn(
            "[violation-picture] no blob for tracker",
            tid,
            "events=",
            eventIds,
            "displayCanvas=",
            displayCanvasRef.current,
          );
          continue;
        }

        const formData = new FormData();
        formData.append("picture", blob, "violation.jpg");
        formData.append("event_ids", JSON.stringify(eventIds));
        try {
          const resp = await fetch(`${apiBase}/dashboard/events/picture`, {
            method: "POST",
            body: formData,
            signal: AbortSignal.timeout(10000),
          });
          console.log(
            "[violation-picture] upload",
            resp.status,
            "tracker=",
            tid,
            "events=",
            eventIds,
            "buffered=",
            usedBuffered,
          );
        } catch (err) {
          console.warn(
            "[violation-picture] upload failed",
            err,
            "tracker=",
            tid,
          );
        }
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

            // Frame buffering for violations is owned by the synced
            // renderer post-paint (see useSyncedRenderer): it has direct
            // access to the freshly-painted canvas for each matched frame
            // and pushes blobs to bufferViolationFrame. Here we only react
            // to commits.
            if (parsed.violation_events?.length) {
              void uploadViolationPictures(parsed.violation_events);
            }
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
          if (reconnectAttempts < DETECTIONS_MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts += 1;
            reconnectTimeout = setTimeout(
              connect,
              DETECTIONS_RECONNECT_DELAY_MS,
            );
          } else {
            setDetectionsError(
              "Connection lost. Max reconnect attempts reached.",
            );
          }
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
    streamError,
    detections,
    isDetectionsConnected,
    detectionsError,
    subscribeDetections,
    subscribeSyncedFrames,
    setDisplayCanvas,
    bufferViolationFrame,
  };

  return (
    <CameraStreamContext.Provider value={value}>
      {children}
    </CameraStreamContext.Provider>
  );
};
