import { useEffect, useState } from "react";
import type {
  StoredConfigSummary,
  DashboardConfigsResponse,
} from "../../types";

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

/**
 * Blocking modal shown when the dashboard has been restored from disk after a
 * restart but no NN model has been deployed yet (awaitingModel === true).
 *
 * Non-dismissible by design: the user MUST select a configuration to deploy
 * before the dashboard becomes functional. Selecting one calls
 * POST .../activate and reloads the page — exactly the ModelSwitcher flow.
 */
export const ModelSelectModal = () => {
  const [configs, setConfigs] = useState<StoredConfigSummary[]>([]);
  const [activeConfigId, setActiveConfigId] = useState<number | null>(null);
  const [deploying, setDeploying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiBase = window.DASHBOARD_CONFIG.apiBase;

  useEffect(() => {
    const fetchConfigs = async () => {
      try {
        const resp = await fetch(`${apiBase}/dashboard/configs`);
        if (!resp.ok) return;
        const data: DashboardConfigsResponse = await resp.json();
        setConfigs(data.configs);
        setActiveConfigId(data.active_config_id);
      } catch {
        // silently fail — user can retry by clicking Deploy
      }
    };
    void fetchConfigs();
  }, [apiBase]);

  const handleDeploy = async (configId: number) => {
    if (deploying) return;
    setDeploying(true);
    setError(null);

    try {
      const resp = await fetch(
        `${apiBase}/dashboard/configs/${configId}/activate`,
        { method: "POST" },
      );
      if (!resp.ok) {
        const data = await resp.json().catch(() => null);
        setError(data?.detail || "Failed to deploy model");
        setDeploying(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Connection error");
      setDeploying(false);
    }
  };

  return (
    /* Backdrop — intentionally not clickable to close (blocking modal) */
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="w-sm max-h-[85vh] flex flex-col bg-gray-900 border border-gray-700 rounded-xl shadow-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700 shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-white">Select a model</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              The camera was restarted. Pick a model to deploy and continue.
            </p>
          </div>
        </div>

        {/* Config list */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {deploying ? (
            <div className="flex items-center justify-center py-10 gap-3">
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span className="text-gray-300 text-sm">Deploying model…</span>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {configs.map((config) => {
                const isLastActive = config.config_id === activeConfigId;
                return (
                  <button
                    key={config.config_id}
                    className={`w-full text-left px-4 py-3 rounded-xl transition-colors flex items-center gap-3 text-sm font-medium text-white cursor-pointer ${
                      isLastActive
                        ? "bg-emerald-500/10 border border-emerald-500/40 hover:bg-emerald-500/20"
                        : "bg-gray-800 hover:bg-gray-700 border border-transparent"
                    }`}
                    onClick={() => handleDeploy(config.config_id)}
                    disabled={deploying}
                  >
                    <BoltIcon />
                    <div className="flex flex-col min-w-0">
                      <span className="truncate">
                        {config.project_name || config.config_name}
                      </span>
                      {config.project_name && (
                        <span className="text-xs text-gray-300 truncate">
                          {config.config_name}
                        </span>
                      )}
                    </div>
                    {isLastActive && (
                      <span className="ml-auto text-xs text-emerald-400 shrink-0">
                        last active
                      </span>
                    )}
                  </button>
                );
              })}

              {configs.length === 0 && (
                <p className="text-gray-400 text-center py-8 text-sm">
                  No stored configurations found. Deploy a dashboard from Studio first.
                </p>
              )}
            </div>
          )}

          {error && (
            <p className="text-red-400 text-sm text-center mt-4">{error}</p>
          )}
        </div>
      </div>
    </div>
  );
};
