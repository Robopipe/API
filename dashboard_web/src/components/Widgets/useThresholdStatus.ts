import { useCallback, useEffect, useState } from "react";
import { useDetections } from "../../hooks/useDetections";
import type {
  ThresholdStatus,
  ThresholdTestCaseStatus,
} from "../../types/detections";

export function useThresholdStatus(running: boolean) {
  const [thresholdStatus, setThresholdStatus] =
    useState<ThresholdStatus | null>(null);
  const [masterStatus, setMasterStatus] =
    useState<ThresholdTestCaseStatus | null>(null);

  const onDetections = useCallback(
    (detections: {
      threshold_status?: ThresholdStatus;
      master_threshold_status?: ThresholdTestCaseStatus;
    }) => {
      if (detections.threshold_status) {
        setThresholdStatus(detections.threshold_status);
      }
      if (detections.master_threshold_status) {
        setMasterStatus(detections.master_threshold_status);
      }
    },
    [],
  );

  useDetections({ onDetections, enabled: running });

  useEffect(() => {
    if (!running) return;
    fetch(`${window.DASHBOARD_CONFIG.apiBase}/dashboard/metrics`)
      .then((r) => r.json())
      .then((data) => {
        if (
          data &&
          data.threshold_status &&
          Object.keys(data.threshold_status).length > 0
        ) {
          setThresholdStatus(data.threshold_status);
        }
        if (data && data.master_threshold_status) {
          setMasterStatus(data.master_threshold_status);
        }
      })
      .catch(() => {});
  }, [running]);

  return { thresholdStatus, masterStatus };
}
