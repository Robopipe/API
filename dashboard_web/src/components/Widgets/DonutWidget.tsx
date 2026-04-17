import type { ThresholdTestCaseStatus } from "../../types/detections";
import type { WidgetDisplayMode } from "./widgetStorage";

export interface DonutWidgetProps {
  name: string;
  status: ThresholdTestCaseStatus | null;
  displayMode?: WidgetDisplayMode;
  /** Default color when no threshold status is available */
  defaultColor?: string;
  /** Donut outer size in px (default 140) */
  size?: number;
  /** Ring stroke width in px (derived from size when omitted) */
  strokeWidth?: number;
  /** Override the center label (defaults to zone_name from status) */
  primaryLabel?: string;
  /** When false, the name label below the donut is hidden (used at very small sizes) */
  showName?: boolean;
}

export const DonutWidget = ({
  name,
  status,
  displayMode = "failures",
  defaultColor = "#20a963",
  size = 140,
  strokeWidth,
  primaryLabel,
  showName = true,
}: DonutWidgetProps) => {
  const stroke = strokeWidth ?? Math.max(4, Math.round(size * 0.086));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const innerContentWidth = Math.round(size * 0.6);

  const primaryFontSize = Math.max(10, Math.round(size * 0.11));
  const secondaryFontSize = Math.max(9, Math.round(size * 0.085));
  const nameFontSize = Math.max(10, Math.round(size * 0.095));
  const warningSize = Math.max(10, Math.round(size * 0.1));

  const failures = status?.failures ?? 0;
  const total = status?.total ?? 0;
  const passRate = status?.pass_rate ?? 1.0;
  const zoneColor = status?.zone_color ?? defaultColor;
  const showWarning =
    status !== null && status.total > 0 && !status.is_best_zone;

  const fillOffset = circumference * (1 - passRate);

  const secondaryMetric = () => {
    if (displayMode === "pass_rate") {
      return (
        <span className="text-gray-400" style={{ fontSize: secondaryFontSize }}>
          {(passRate * 100).toFixed(1)}%
        </span>
      );
    }
    if (displayMode === "failures_of_total") {
      return (
        <span className="text-gray-400" style={{ fontSize: secondaryFontSize }}>
          {failures}/{total}
        </span>
      );
    }
    // default: "failures"
    return (
      <span className="text-gray-400" style={{ fontSize: secondaryFontSize }}>
        {failures} fail
      </span>
    );
  };

  return (
    <div className="flex flex-col items-center gap-2" title={name}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="transform -rotate-90"
        >
          {/* Background ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#374151"
            strokeWidth={stroke}
          />
          {/* Foreground ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={zoneColor}
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={fillOffset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 500ms" }}
          />
        </svg>
        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
          <div
            className="flex flex-col items-center gap-0.5"
            style={{ width: innerContentWidth }}
          >
            <span
              className="font-bold text-white px-1 rounded leading-snug text-center w-full truncate"
              style={{
                backgroundColor: zoneColor + "33",
                fontSize: primaryFontSize,
              }}
            >
              {primaryLabel ?? status?.zone_name ?? "—"}
            </span>
            {secondaryMetric()}
            {showWarning && (
              <svg
                width={warningSize}
                height={warningSize}
                viewBox="0 0 24 24"
                fill="none"
              >
                <path
                  d="M12 2L1 21h22L12 2z"
                  fill={zoneColor}
                  stroke={zoneColor}
                  strokeWidth="1"
                />
                <text
                  x="12"
                  y="18"
                  textAnchor="middle"
                  fill="white"
                  fontSize="12"
                  fontWeight="bold"
                >
                  !
                </text>
              </svg>
            )}
          </div>
        </div>
      </div>
      {showName && (
        <span
          className="text-white font-medium text-center max-w-full truncate px-1"
          style={{ fontSize: nameFontSize, maxWidth: size * 1.4 }}
        >
          {name}
        </span>
      )}
    </div>
  );
};
