import type { EvalThreshold } from "../../types/dashboard";

/**
 * Compute a numeric grade from a pass rate and a set of thresholds.
 * Grade 1 = best zone, grade X = worst zone (X = number of thresholds).
 * The decimal part reflects position within the bracket (0.00 = near the good
 * boundary, ~0.99 = near the bad boundary).
 */
export function computeGrade(
  passRate: number,
  thresholds: EvalThreshold[],
): number {
  if (thresholds.length === 0) return 1;

  const sorted = [...thresholds].sort((a, b) => a.value - b.value);
  const X = sorted.length;

  // Find zone index (same logic as backend _determine_zone)
  let zoneIndex = X - 1;
  for (let i = 0; i < X - 1; i++) {
    if (passRate < sorted[i].value) {
      zoneIndex = i;
      break;
    }
  }

  const gradeIntegral = X - zoneIndex;
  const lower = zoneIndex === 0 ? 0 : sorted[zoneIndex - 1].value;
  const upper = zoneIndex === X - 1 ? 1.0 : sorted[zoneIndex].value;
  const range = upper - lower;
  const decimal =
    range > 0 ? Math.min((upper - passRate) / range, 0.99) : 0;

  return Math.round((gradeIntegral + decimal) * 100) / 100;
}
