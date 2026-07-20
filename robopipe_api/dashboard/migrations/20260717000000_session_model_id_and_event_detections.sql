-- Snapshot of the active NN config's model at session start
-- (NNConfig.model_id). NULL when the stream had no NN config, the config
-- carries no model id, or the session predates this migration. Storage
-- only — not exposed via the report CSV or any API endpoint.
ALTER TABLE dashboard_run_session ADD COLUMN model_id INTEGER;

-- Full commit-frame detection set per evaluation event (passing and
-- failing). Event pictures are saved clean from this migration on — the
-- boxes formerly burned into the JPEG live here instead, so presence of
-- rows for an event implies its picture has no annotations.
-- Coordinates are normalized [0,1] xyxy, exactly as BBoxDetection.coords.
-- label_id/label_name are denormalized like dashboard_counter. role records
-- what the old renderer would have highlighted on the picture:
--   'parent'         — the exiting tracker's own detection (blue box)
--   'violated_child' — detection inside the exit parent whose label is the
--                      target of a violated parent-scoped limit
--   'violation'      — parentless-limit violating item
--   NULL             — plain detection, would not have been highlighted
-- Rows are kept forever; the disk-pressure CleanupTask never touches them.
CREATE TABLE dashboard_evaluation_event_detection (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES dashboard_evaluation_event(id) ON DELETE CASCADE,
    label_id INTEGER NOT NULL,
    label_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    x_min REAL NOT NULL,
    y_min REAL NOT NULL,
    x_max REAL NOT NULL,
    y_max REAL NOT NULL,
    display_id INTEGER,
    parent_display_id INTEGER,
    role TEXT
);

CREATE INDEX idx_event_detection_event
    ON dashboard_evaluation_event_detection(event_id);
