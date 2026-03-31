import type { Label } from "../../types/label";
import { Sidebar } from "../../ui";

interface CounterSidebarProps {
  open: boolean;
  onClose: () => void;
  labels: Label[];
  selectedLabelId: number | null;
  onSelectLabel: (labelId: number) => void;
}

export const CounterSidebar = ({
  open,
  onClose,
  labels,
  selectedLabelId,
  onSelectLabel,
}: CounterSidebarProps) => {
  return (
    <Sidebar open={open} onClose={onClose}>
      <div className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-1">
          Count label
        </h3>
        {labels.map((label) => {
          const isActive = label.id === selectedLabelId;
          return (
            <button
              key={label.id}
              className={`w-full text-left px-4 py-3 rounded-xl transition-colors flex items-center gap-2 text-sm font-medium ${
                isActive
                  ? "bg-emerald-500/20 border border-emerald-500/50 cursor-default"
                  : "bg-gray-800 hover:bg-gray-700 border border-transparent cursor-pointer"
              }`}
              onClick={() => {
                onSelectLabel(label.id);
                onClose();
              }}
              disabled={isActive}
            >
              <span
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: label.color }}
              />
              <span>{label.name}</span>
            </button>
          );
        })}
        {labels.length === 0 && (
          <p className="text-gray-400 text-center py-4 text-sm">
            No labels available
          </p>
        )}
      </div>
    </Sidebar>
  );
};
