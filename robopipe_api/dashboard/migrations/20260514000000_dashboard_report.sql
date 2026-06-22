CREATE TABLE dashboard_report (
    id INTEGER PRIMARY KEY,
    dashboard_config_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    filter_start TEXT,
    filter_end TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    file_path TEXT,
    error TEXT
);
CREATE INDEX idx_dashboard_report_config ON dashboard_report(dashboard_config_id);
