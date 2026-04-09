import type { TestCase } from "../types";
import type { NNDetections } from "../types/detections";

export interface Violation {
  name: string;
  severity: "ALERT" | "WARNING";
}

export function collectViolations(
  detections: NNDetections,
  testCaseMap: Record<string, TestCase>,
): Violation[] {
  const fromTestCases =
    detections.dashboard_detections?.flatMap((d) => {
      const tc = testCaseMap[d.test_case_id];
      return tc?.severity ? [{ name: tc.name, severity: tc.severity }] : [];
    }) ?? [];

  const fromDetections = detections.detections.flatMap((det) =>
    "violations" in det && det.violations
      ? det.violations.map((v) => ({ name: v.limit_name, severity: v.severity }))
      : [],
  );

  return [...fromTestCases, ...fromDetections];
}

export function countBySeverity(violations: Violation[]) {
  return violations.reduce(
    (acc, v) => {
      if (v.severity === "ALERT") acc.alerts++;
      else acc.warnings++;
      return acc;
    },
    { alerts: 0, warnings: 0 },
  );
}
