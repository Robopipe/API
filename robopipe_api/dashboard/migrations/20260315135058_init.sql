CREATE TABLE dashboard_run_session (
    id INTEGER PRIMARY KEY,
    start_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TEXT,
    dashboard_config_id INTEGER
);
CREATE TABLE dashboard_counter (
    dashboard_run_session_id INTEGER NOT NULL REFERENCES dashboard_run_session(id),
    label_id INTEGER NOT NULL,
    label_name TEXT NOT NULL,
    value INTEGER NOT NULL,
    PRIMARY KEY (dashboard_run_session_id, label_id)
);