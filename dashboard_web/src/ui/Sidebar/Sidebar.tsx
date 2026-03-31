import { useEffect } from "react";

export interface SidebarProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

export const Sidebar = ({ open, onClose, children }: SidebarProps) => {
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  return (
    <div
      className={`fixed left-0 top-0 bottom-0 w-48 z-50 bg-gray-900 border-r border-gray-700 transform transition-transform duration-300 ease-in-out flex flex-col ${
        open ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 pt-6">{children}</div>

      {/* Close button */}
      <div className="p-4">
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white transition-colors"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
    </div>
  );
};
