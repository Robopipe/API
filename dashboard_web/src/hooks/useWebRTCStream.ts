import { useEffect, useRef } from "react";
import { useCameraStream } from "../provider";

export interface UseWebRTCStreamReturn {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  mediaStream: MediaStream | null;
  isStreaming: boolean;
  error: string | null;
}

/**
 * Thin wrapper that attaches the provider's MediaStream to a local
 * <video> element. The provider owns the WebRTC peer connection and
 * runs its own off-DOM video for sync capture.
 */
export const useWebRTCStream = (): UseWebRTCStreamReturn => {
  const { mediaStream, isStreaming, streamError } = useCameraStream();
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    if (!videoRef.current || !mediaStream) return;
    if (videoRef.current.srcObject !== mediaStream) {
      videoRef.current.srcObject = mediaStream;
    }
  }, [mediaStream]);

  return {
    videoRef,
    mediaStream,
    isStreaming,
    error: streamError,
  };
};
