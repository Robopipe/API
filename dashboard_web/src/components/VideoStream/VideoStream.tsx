import { useCallback, useState } from "react";
import { useWebRTCStream } from "../../hooks";
import { useDetections } from "../../hooks/useDetections";
import { useDetectionsRenderer } from "../../hooks/useDetectionsRenderer";
import { useAppState } from "../../provider";
import type { TestCase, NNDetections } from "../../types";

export const VideoStream = () => {
  const { running } = useAppState();
  const { videoRef } = useWebRTCStream();
  const { renderDetections, canvasRef } = useDetectionsRenderer({ videoRef });
  const [dashboardDetection, setDashboardDetection] =
    useState<TestCase | null>(null);
  const onDetections = useCallback(
    (detections: NNDetections) => {
      renderDetections(detections);
      setDashboardDetection(
        detections.dashboard_detections?.[0]
          ? window.DASHBOARD_CONFIG.testCases.find(
              (tc) => tc.id === detections.dashboard_detections?.[0]?.test_case_id,
            ) || null
          : null,
      );
    },
    [renderDetections],
  );
  useDetections({ onDetections });
  const getDetectionClassName = (d: TestCase | null): string => {
    if (!d) return "bg-emerald-500/80";
    switch (d.severity) {
      case "ALERT":
        return "bg-red-500/80";
      case "WARNING":
        return "bg-pear-500/80";
      default:
        return "";
    }
  };

  return (
    <div
      className={
        "w-full" +
        (running
          ? " rounded-xl p-1.5 " + getDetectionClassName(dashboardDetection)
          : "")
      }
    >
      <div className="relative">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="rounded-md w-full"
        />
        <canvas
          ref={canvasRef}
          className="absolute top-0 left-0 w-full h-full"
        />
      </div>
      {running && (
        <p className="text-center text-4xl mt-9 mb-12">
          {dashboardDetection
            ? `${dashboardDetection.severity}: ${dashboardDetection.name}`
            : "OK"}
        </p>
      )}
    </div>
  );
};
