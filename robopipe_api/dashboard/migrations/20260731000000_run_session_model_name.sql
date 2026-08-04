-- Human-readable name of the active NN config's model, snapshotted at
-- session start alongside model_id (NNConfig.model_name). NULL when the
-- stream had no NN config, the config carries no name, or the session
-- predates this migration.
ALTER TABLE dashboard_run_session ADD COLUMN model_name TEXT;
