DROP TABLE IF EXISTS dashboard_evaluation_event;

CREATE TABLE dashboard_evaluation_event (
    id INTEGER PRIMARY KEY,
    dashboard_run_session_id INTEGER NOT NULL REFERENCES dashboard_run_session(id),
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    test_case_id TEXT NOT NULL,
    test_case_name TEXT NOT NULL,
    passed INTEGER NOT NULL,
    picture_url TEXT
);

CREATE TABLE dashboard_evaluation_event_violated_limit (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES dashboard_evaluation_event(id) ON DELETE CASCADE,
    limit_id TEXT NOT NULL,
    limit_name TEXT NOT NULL
);

CREATE INDEX idx_violated_limit_event ON dashboard_evaluation_event_violated_limit(event_id);
