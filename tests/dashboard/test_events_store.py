"""EventsStore migrations and session end-reason persistence."""

import sqlite3

import pytest

from robopipe_api.dashboard.events_store import EventsStore


@pytest.fixture()
def store(tmp_path):
    s = EventsStore(db_path=tmp_path / "test.db")
    s.init()
    return s


def read_session(store, session_id):
    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM dashboard_run_session WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row)


def test_migrations_add_end_reason_columns(store):
    session_id = store.start_session(dashboard_config_id=1)
    row = read_session(store, session_id)
    assert "end_reason" in row
    assert "product_alarm_time" in row
    assert row["end_time"] is None


def test_end_session_defaults_to_manual(store):
    session_id = store.start_session(dashboard_config_id=1)
    store.end_session(session_id)
    row = read_session(store, session_id)
    assert row["end_time"] is not None
    assert row["end_reason"] == "manual"
    assert row["product_alarm_time"] is None


@pytest.mark.parametrize(
    "reason", ["product_switch_auto_stop", "product_switch_confirmed"]
)
def test_end_session_records_product_switch_reasons(store, reason):
    session_id = store.start_session(dashboard_config_id=1)
    store.end_session(session_id, reason, "2026-07-08T12:00:00+00:00")
    row = read_session(store, session_id)
    assert row["end_reason"] == reason
    assert row["product_alarm_time"] == "2026-07-08T12:00:00+00:00"
