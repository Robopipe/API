ALTER TABLE dashboard_evaluation_event_violated_limit
    ADD COLUMN tracking_id INTEGER;
ALTER TABLE dashboard_evaluation_event_violated_limit
    ADD COLUMN parent_tracking_id INTEGER;
