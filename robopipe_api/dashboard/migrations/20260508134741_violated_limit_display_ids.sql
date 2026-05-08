ALTER TABLE dashboard_evaluation_event_violated_limit
    RENAME COLUMN tracking_id TO display_id;
ALTER TABLE dashboard_evaluation_event_violated_limit
    RENAME COLUMN parent_tracking_id TO parent_display_id;
