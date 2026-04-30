import { useContext } from "react";
import { CameraStreamContext } from "./cameraStreamContext";
import type { CameraStreamContextValue } from "./cameraStreamContext";

export const useCameraStream = (): CameraStreamContextValue => {
  const ctx = useContext(CameraStreamContext);
  if (!ctx) {
    throw new Error(
      "useCameraStream must be used within a CameraStreamProvider",
    );
  }
  return ctx;
};
