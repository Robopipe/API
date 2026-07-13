-- Why a run ended: 'manual' (operator or teardown), 'product_switch_auto_stop'
-- (product-check alarm countdown expired), 'product_switch_confirmed'
-- (operator pressed Stop on the alarm modal). NULL for sessions ended before
-- this migration. product_alarm_time is the UTC ISO timestamp the alarm
-- fired, set only for the product_switch_* reasons.
ALTER TABLE dashboard_run_session ADD COLUMN end_reason TEXT;
ALTER TABLE dashboard_run_session ADD COLUMN product_alarm_time TEXT;
