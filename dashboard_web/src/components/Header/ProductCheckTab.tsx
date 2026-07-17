import { useState } from "react";
import { PRODUCT_CHECK_FIELDS } from "./productCheckFields";
import type { SettingsField } from "./SettingsModal";

const enabledOptions: { value: boolean; label: string }[] = [
  { value: true, label: "Enabled" },
  { value: false, label: "Disabled" },
];

// Only the on/off switch and the auto-stop timer are everyday controls;
// the tuning knobs live behind the Advanced options chevron.
const BASIC_KEYS = ["productCheckAlarmSeconds"];
const basicFields = PRODUCT_CHECK_FIELDS.filter((f) =>
  BASIC_KEYS.includes(f.key),
);
const advancedFields = PRODUCT_CHECK_FIELDS.filter(
  (f) => !BASIC_KEYS.includes(f.key),
);

const ChevronIcon = ({ open }: { open: boolean }) => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={`transition-transform ${open ? "rotate-180" : ""}`}
  >
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const FieldInput = ({
  field,
  values,
  onChange,
}: {
  field: SettingsField;
  values: Record<string, number>;
  onChange: (key: string, raw: string, field: SettingsField) => void;
}) => (
  <div>
    <label className="block text-sm font-medium text-gray-200 mb-1">
      {field.label}
    </label>
    <input
      type="number"
      min={field.min}
      max={field.max}
      step={field.step}
      value={values[field.key]}
      onChange={(e) => onChange(field.key, e.target.value, field)}
      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-emerald-500 transition-colors"
    />
    <p className="mt-1 text-xs text-gray-400">{field.description}</p>
  </div>
);

export const ProductCheckTab = ({
  values,
  onChange,
  enabled,
  onEnabledChange,
}: {
  values: Record<string, number>;
  onChange: (key: string, raw: string, field: SettingsField) => void;
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
}) => {
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Product check
        </h3>
        <p className="text-xs text-gray-500 mb-1">
          Learns each run's detection profile and alarms when the model's
          output stops matching it (e.g. a different product started on the
          line).
        </p>
        {enabledOptions.map((opt) => {
          const isActive = enabled === opt.value;
          return (
            <button
              key={String(opt.value)}
              className={`w-full text-left px-4 py-3 rounded-xl transition-colors text-sm font-medium ${
                isActive
                  ? "bg-emerald-500/20 border border-emerald-500/50 cursor-default"
                  : "bg-gray-800 hover:bg-gray-700 border border-transparent cursor-pointer"
              }`}
              onClick={() => onEnabledChange(opt.value)}
              disabled={isActive}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      {basicFields.map((field) => (
        <FieldInput
          key={field.key}
          field={field}
          values={values}
          onChange={onChange}
        />
      ))}

      <div className="flex flex-col gap-4">
        <button
          className="flex items-center gap-1.5 text-sm font-medium text-gray-400 hover:text-gray-200 transition-colors cursor-pointer self-start"
          onClick={() => setShowAdvanced((v) => !v)}
          aria-expanded={showAdvanced}
        >
          <ChevronIcon open={showAdvanced} />
          Advanced options
        </button>

        {showAdvanced &&
          advancedFields.map((field) => (
            <FieldInput
              key={field.key}
              field={field}
              values={values}
              onChange={onChange}
            />
          ))}
      </div>
    </div>
  );
};
