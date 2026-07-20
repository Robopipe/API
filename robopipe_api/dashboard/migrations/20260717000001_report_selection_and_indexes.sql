-- Report selection: a report can now target a single session and/or an
-- explicit set of events in addition to the start/end time range.
-- filter_event_ids is a JSON array of event ids; NULL means no selection.
ALTER TABLE dashboard_report ADD COLUMN filter_session_id INTEGER;
ALTER TABLE dashboard_report ADD COLUMN filter_event_ids TEXT;

-- The reports API pages events per dashboard; both lookups were table scans.
CREATE INDEX idx_evaluation_event_session
    ON dashboard_evaluation_event(dashboard_run_session_id);
CREATE INDEX idx_run_session_config
    ON dashboard_run_session(dashboard_config_id);
