import { useState, useEffect } from "react";
import type {
  StoredConfigSummary,
  DashboardConfigsResponse,
} from "../../types";
import { Sidebar } from "../../ui";

const SwitchIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M9 3H5C3.89543 3 3 3.89543 3 5V9C3 10.1046 3.89543 11 5 11H9C10.1046 11 11 10.1046 11 9V5C11 3.89543 10.1046 3 9 3Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M19 3H15C13.8954 3 13 3.89543 13 5V9C13 10.1046 13.8954 11 15 11H19C20.1046 11 21 10.1046 21 9V5C21 3.89543 20.1046 3 19 3Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M9 13H5C3.89543 13 3 13.8954 3 15V19C3 20.1046 3.89543 21 5 21H9C10.1046 21 11 20.1046 11 19V15C11 13.8954 10.1046 13 9 13Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M19 13H15C13.8954 13 13 13.8954 13 15V19C13 20.1046 13.8954 21 15 21H19C20.1046 21 21 20.1046 21 19V15C21 13.8954 20.1046 13 19 13Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const BoltIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
  </svg>
);

export const ModelSwitcher = () => {
  const [open, setOpen] = useState(false);
  const [configs, setConfigs] = useState<StoredConfigSummary[]>([]);
  const [activeConfigId, setActiveConfigId] = useState<number | null>(null);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiBase = window.DASHBOARD_CONFIG.apiBase;

  const fetchConfigs = async () => {
    try {
      const resp = await fetch(`${apiBase}/dashboard/configs`);
      if (!resp.ok) return;
      const data: DashboardConfigsResponse = await resp.json();
      setConfigs(data.configs);
      setActiveConfigId(data.active_config_id);
    } catch {
      // silently fail
    }
  };

  const handleSwitch = async (configId: number) => {
    if (configId === activeConfigId || switching) return;
    setSwitching(true);
    setError(null);

    try {
      const resp = await fetch(
        `${apiBase}/dashboard/configs/${configId}/activate`,
        { method: "POST" },
      );
      if (!resp.ok) {
        const data = await resp.json().catch(() => null);
        setError(data?.detail || "Failed to switch config");
        setSwitching(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Connection error");
      setSwitching(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchConfigs();
    }
  }, [open]);

  if (!window.DASHBOARD_CONFIG.hasMultipleConfigs) {
    return null;
  }

  return (
    <>
      <button
        className="py-3 px-3 md:px-4 bg-gray-700 rounded-xl flex items-center gap-2 shrink-0"
        onClick={() => setOpen((prev) => !prev)}
        title="Switch model"
      >
        <SwitchIcon />
        <span className="hidden md:inline">Switch model</span>
      </button>

      <Sidebar open={open} onClose={() => setOpen(false)}>
        {switching && (
          <div className="flex items-center justify-center py-8 gap-3">
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            <span className="text-gray-300 text-sm">Switching...</span>
          </div>
        )}

        {!switching && (
          <div className="flex flex-col gap-3">
            {configs.map((config) => {
              const isActive = config.config_id === activeConfigId;
              return (
                <button
                  key={config.config_id}
                  className={`w-full text-left px-4 py-3 rounded-xl transition-colors flex items-center gap-2 text-sm font-medium ${
                    isActive
                      ? "bg-emerald-500/20 border border-emerald-500/50 cursor-default"
                      : "bg-gray-800 hover:bg-gray-700 border border-transparent cursor-pointer"
                  }`}
                  onClick={() => handleSwitch(config.config_id)}
                  disabled={isActive}
                >
                  <BoltIcon />
                  <div className="flex flex-col">
                    <span>{config.project_name || config.config_name}</span>
                    {config.project_name && (
                      <span className="text-xs text-gray-400">
                        {config.config_name}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}

            {configs.length === 0 && (
              <p className="text-gray-400 text-center py-4 text-sm">
                No configs available
              </p>
            )}
          </div>
        )}

        {error && (
          <p className="text-red-400 text-sm text-center mt-4">{error}</p>
        )}
      </Sidebar>
    </>
  );
};
