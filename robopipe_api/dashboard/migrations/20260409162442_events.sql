CREATE TABLE dashboard_evaluation_event (
    id INTEGER PRIMARY KEY,
    dashboard_run_session_id INTEGER NOT NULL REFERENCES dashboard_run_session(id),
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    test_case_id INTEGER NOT NULL,
    test_case_name TEXT NOT NULL,
    failed_limit_id INTEGER,
    failed_limit_name TEXT,
    picture_url TEXT
);