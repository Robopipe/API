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
  /** Ring stroke width in px (default 12) */
  strokeWidth?: number;
}

export const DonutWidget = ({
  name,
  status,
  displayMode = "failures",
  defaultColor = "#20a963",
  size = 140,
  strokeWidth = 12,
}: DonutWidgetProps) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const innerContentWidth = Math.round(size * 0.6);
  const isLarge = size > 160;

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
        <span className={`${isLarge ? "text-base" : "text-sm"} text-gray-400`}>
          {(passRate * 100).toFixed(1)}%
        </span>
      );
    }
    if (displayMode === "failures_of_total") {
      return (
        <span className={`${isLarge ? "text-base" : "text-sm"} text-gray-400`}>
          {failures}/{total}
        </span>
      );
    }
    // default: "failures"
    return (
      <span className={`${isLarge ? "text-base" : "text-sm"} text-gray-400`}>
        {failures} fail
      </span>
    );
  };

  return (
    <div className="flex flex-col items-center gap-2">
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
            strokeWidth={strokeWidth}
          />
          {/* Foreground ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={zoneColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={fillOffset}
            strokeLinecap="round"
            className="transition-all duration-500"
          />
        </svg>
        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
          <div
            className="flex flex-col items-center gap-0.5"
            style={{ width: innerContentWidth }}
          >
            <span
              className={`${isLarge ? "text-xl" : "text-base"} font-bold text-white px-1 rounded leading-snug text-center w-full`}
              style={{ backgroundColor: zoneColor + "33" }}
            >
              {status?.zone_name ?? "—"}
            </span>
            {secondaryMetric()}
            {showWarning && (
              <svg
                width="14"
                height="14"
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
      <span
        className={`${isLarge ? "text-base" : "text-sm"} text-white font-medium text-center`}
      >
        {name}
      </span>
    </div>
  );
};
