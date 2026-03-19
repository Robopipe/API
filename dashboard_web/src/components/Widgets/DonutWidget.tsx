import type { ThresholdTestCaseStatus } from "../../types/detections";

export interface DonutWidgetProps {
  name: string;
  status: ThresholdTestCaseStatus | null;
  /** Default color when no threshold status is available */
  defaultColor?: string;
}

const SIZE = 140;
const STROKE_WIDTH = 12;
const RADIUS = (SIZE - STROKE_WIDTH) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export const DonutWidget = ({
  name,
  status,
  defaultColor = "#20a963",
}: DonutWidgetProps) => {
  const failures = status?.failures ?? 0;
  const passRate = status?.pass_rate ?? 100;
  const zoneColor = status?.zone_color ?? defaultColor;
  const showWarning = status !== null && status.total > 0 && status.failures > 0;

  const fillOffset = CIRCUMFERENCE * (1 - passRate / 100);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="transform -rotate-90"
        >
          {/* Background ring */}
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="#374151"
            strokeWidth={STROKE_WIDTH}
          />
          {/* Foreground ring */}
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke={zoneColor}
            strokeWidth={STROKE_WIDTH}
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={fillOffset}
            strokeLinecap="round"
            className="transition-all duration-500"
          />
        </svg>
        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-white">{failures}</span>
          {showWarning && (
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              className="mt-0.5"
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
      <span className="text-sm text-white font-medium text-center">{name}</span>
    </div>
  );
};
