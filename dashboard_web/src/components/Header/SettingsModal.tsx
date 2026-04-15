import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

interface SettingsField {
  key: string;
  label: string;
  description: string;
  min: number;
  max: number;
  step: number;
  integer?: boolean;
}

const FIELDS: SettingsField[] = [
  {
    key: "confidenceThreshold",
    label: "Confidence Threshold",
    description: "Minimum detection confidence (0–1)",
    min: 0,
    max: 1,
    step: 0.05,
  },
  {
    key: "debounceFrames",
    label: "Debounce Frames",
    description: "Frames needed to confirm a track",
    min: 1,
    max: 100,
    step: 1,
    integer: true,
  },
  {
    key: "maxMissingFrames",
    label: "Max Missing Frames",
    description: "Frames before an unmatched track expires",
    min: 0,
    max: 100,
    step: 1,
    integer: true,
  },
  {
    key: "maxMatchDistance",
    label: "Max Match Distance",
    description: "Max distance for track matching (not currently active)",
    min: 0,
    max: 1,
    step: 0.05,
  },
];

type Values = Record<string, number>;

function loadCurrentValues(): Values {
  const cfg = window.DASHBOARD_CONFIG;
  return {
    confidenceThreshold: cfg.confidenceThreshold,
    debounceFrames: cfg.debounceFrames,
    maxMissingFrames: cfg.maxMissingFrames,
    maxMatchDistance: cfg.maxMatchDistance,
  };
}

export const SettingsModal = ({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) => {
  const [values, setValues] = useState<Values>(loadCurrentValues);
  const [saving, setSaving] = useState(false);
  const backdropRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) setValues(loadCurrentValues());
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  const handleChange = (key: string, raw: string, field: SettingsField) => {
    const num = field.integer ? parseInt(raw, 10) : parseFloat(raw);
    if (!isNaN(num)) {
      setValues((prev) => ({ ...prev, [key]: num }));
    }
  };

  const isValid = FIELDS.every((f) => {
    const v = values[f.key];
    return v !== undefined && v >= f.min && v <= f.max;
  });

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(
        `${window.DASHBOARD_CONFIG.apiBase}/dashboard/config`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(values),
        },
      );
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail);
      }
      const updated = await res.json();
      // Update in-place so subsequent opens reflect the new values
      window.DASHBOARD_CONFIG.confidenceThreshold = updated.confidenceThreshold;
      window.DASHBOARD_CONFIG.debounceFrames = updated.debounceFrames;
      window.DASHBOARD_CONFIG.maxMissingFrames = updated.maxMissingFrames;
      window.DASHBOARD_CONFIG.maxMatchDistance = updated.maxMatchDistance;
      toast.success("Settings updated");
      onClose();
    } catch (err) {
      toast.error(
        `Failed to update settings: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === backdropRef.current) onClose();
      }}
    >
      <div className="w-96 bg-gray-900 border border-gray-700 rounded-xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Dashboard Settings</h2>
          <button
            className="text-gray-400 hover:text-white transition-colors"
            onClick={onClose}
          >
            &times;
          </button>
        </div>

        <div className="flex flex-col gap-4">
          {FIELDS.map((field) => (
            <div key={field.key}>
              <label className="block text-sm font-medium text-gray-200 mb-1">
                {field.label}
              </label>
              <input
                type="number"
                min={field.min}
                max={field.max}
                step={field.step}
                value={values[field.key]}
                onChange={(e) =>
                  handleChange(field.key, e.target.value, field)
                }
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-emerald-500 transition-colors"
              />
              <p className="mt-1 text-xs text-gray-400">{field.description}</p>
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <button
            className="py-2 px-4 bg-gray-700 rounded-xl text-sm hover:bg-gray-600 transition-colors"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="py-2 px-4 bg-emerald-500/80 rounded-xl text-sm hover:bg-emerald-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            disabled={!isValid || saving}
            onClick={handleSave}
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
};
