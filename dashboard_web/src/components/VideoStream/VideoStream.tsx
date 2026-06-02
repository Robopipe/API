import { useCallback, useState } from "react";
import { useWebRTCStream } from "../../hooks";
import { useDetections } from "../../hooks/useDetections";
import { useSyncedRenderer } from "../../hooks/useSyncedRenderer";
import { useAppState } from "../../provider";
import type { NNDetections } from "../../types";
import { collectViolations } from "../../utils/collectViolations";

interface BorderInfo {
  severity: "ALERT" | "WARNING";
  name: string;
  extraCount: number;
}

export const VideoStream = () => {
  const {
    running,
    testCaseMap,
    displayMode,
    multiLimitMode,
    hiddenLabelIds,
    zoneVisible,
  } = useAppState();
  const { isStreaming, error, replayEnded } = useWebRTCStream();
  const { canvasRef } = useSyncedRenderer({
    displayMode,
    multiLimitMode,
    hiddenLabelIds,
    zoneVisible,
  });
  const [borderInfo, setBorderInfo] = useState<BorderInfo | null>(null);

  const onDetections = useCallback(
    (detections: NNDetections) => {
      const allViolations = collectViolations(detections, testCaseMap);

      if (allViolations.length === 0) {
        setBorderInfo(null);
        return;
      }

      // Sort: ALERT first
      allViolations.sort((a, b) =>
        a.severity === b.severity ? 0 : a.severity === "ALERT" ? -1 : 1,
      );

      setBorderInfo({
        severity: allViolations[0].severity,
        name: allViolations[0].name,
        extraCount: allViolations.length - 1,
      });
    },
    [testCaseMap],
  );
  useDetections({ onDetections });

  const getBorderClassName = (info: BorderInfo | null): string => {
    if (!info) return "bg-emerald-500/80";
    return info.severity === "ALERT" ? "bg-red-500/80" : "bg-pear-500/80";
  };

  const getBorderText = (info: BorderInfo | null): string => {
    if (!info) return "OK";
    const extra = info.extraCount > 0 ? ` (+${info.extraCount})` : "";
    return `${info.severity}: ${info.name}${extra}`;
  };

  return (
    <div
      className={
        "w-full" +
        (running ? " rounded-xl p-1.5 " + getBorderClassName(borderInfo) : "")
      }
    >
      <div className="relative bg-gray-950 rounded-md overflow-hidden aspect-square">
        <canvas ref={canvasRef} className="absolute left-0 w-full" />
        {(!isStreaming || replayEnded) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-10">
            {replayEnded ? (
              <span className="text-red-500 text-sm">Replay finished</span>
            ) : error ? (
              <span className="text-red-400 text-sm">{error}</span>
            ) : (
              <>
                <div className="w-8 h-8 border-2 border-white/20 border-t-white/70 rounded-full animate-spin" />
                <span className="text-gray-400 text-sm">Connecting...</span>
              </>
            )}
          </div>
        )}
      </div>
      {running && (
        <p className="text-center text-4xl mt-9 mb-12">
          {getBorderText(borderInfo)}
        </p>
      )}
    </div>
  );
};
