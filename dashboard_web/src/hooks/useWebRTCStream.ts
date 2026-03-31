import { useEffect, useRef, useState } from "react";

export interface UseWebRTCStreamReturn {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  isStreaming: boolean;
  error: string | null;
}

const ICE_SERVERS: RTCIceServer[] = [
  { urls: ["stun:stun.l.google.com:19302"] },
  // Add TURN server(s) for relay fallback when direct connection fails.
  // Replace the credentials below with your own TURN server config.
  // You can self-host with coturn or use a managed service (Twilio, Xirsys).
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

export const useWebRTCStream = (): UseWebRTCStreamReturn => {
  const { apiBase } = window.DASHBOARD_CONFIG;
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initWebRTC = async () => {
      try {
        setError(null);

        const peerConnection = new RTCPeerConnection({
          iceServers: ICE_SERVERS,
          // Allow all candidate types; relay-only would force TURN usage
          // Set to "relay" to debug whether TURN works in isolation
          iceTransportPolicy: "all",
        });

        peerConnectionRef.current = peerConnection;

        // Add transceiver to receive video
        peerConnection.addTransceiver("video", { direction: "recvonly" });

        // Handle remote stream
        const handleTrack = (event: RTCTrackEvent) => {
          if (videoRef.current) {
            if (videoRef.current.srcObject !== event.streams[0]) {
              videoRef.current.srcObject = event.streams[0];
            }
            setIsStreaming(true);
          }
        };

        peerConnection.addEventListener("track", handleTrack);

        // Collect ICE candidates to send with the offer
        const iceCandidates: RTCIceCandidate[] = [];

        const handleICECandidate = (event: RTCPeerConnectionIceEvent) => {
          if (event.candidate) {
            console.debug(
              "ICE candidate gathered:",
              event.candidate.type,
              event.candidate.candidate,
            );
            iceCandidates.push(event.candidate);
          }
        };

        peerConnection.addEventListener("icecandidate", handleICECandidate);

        // Log ICE connection state for debugging
        peerConnection.addEventListener("iceconnectionstatechange", () => {
          console.debug(
            "ICE connection state:",
            peerConnection.iceConnectionState,
          );
        });

        // Create and send offer
        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);

        // Wait for ICE gathering to complete with a timeout
        const ICE_GATHERING_TIMEOUT_MS = 5000;
        await new Promise<void>((resolve) => {
          const timeout = setTimeout(() => {
            console.warn(
              "ICE gathering timed out, proceeding with collected candidates",
            );
            resolve();
          }, ICE_GATHERING_TIMEOUT_MS);

          const checkGathering = () => {
            if (peerConnection.iceGatheringState === "complete") {
              clearTimeout(timeout);
              resolve();
            } else {
              setTimeout(checkGathering, 100);
            }
          };
          checkGathering();
        });

        const offerUrl = `${apiBase}/video`;

        const response = await fetch(offerUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
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
        const answer = new RTCSessionDescription(answerData);
        await peerConnection.setRemoteDescription(answer);

        // Add ICE candidates from the answer if provided
        if (answerData.candidates && Array.isArray(answerData.candidates)) {
          for (const candidate of answerData.candidates) {
            try {
              await peerConnection.addIceCandidate(
                new RTCIceCandidate(candidate),
              );
            } catch (err) {
              console.warn("Failed to add ICE candidate:", err);
            }
          }
        }

        // Handle connection state changes
        const handleConnectionStateChange = () => {
          if (
            peerConnection.connectionState === "failed" ||
            peerConnection.connectionState === "disconnected"
          ) {
            setIsStreaming(false);
            setError("Connection lost");
          } else if (peerConnection.connectionState === "connected") {
            setIsStreaming(true);
          }
        };

        peerConnection.addEventListener(
          "connectionstatechange",
          handleConnectionStateChange,
        );
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Unknown error occurred";
        setError(errorMessage);
        setIsStreaming(false);
        console.error("WebRTC error:", err);
      }
    };

    initWebRTC();

    return () => {
      if (peerConnectionRef.current) {
        peerConnectionRef.current.close();
        peerConnectionRef.current = null;
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
      setIsStreaming(false);
    };
  }, [apiBase]);

  return {
    videoRef,
    isStreaming,
    error,
  };
};
