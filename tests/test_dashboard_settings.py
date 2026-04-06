"""
Tests for dashboard slider DB writeback (dashboard_settings table).

The dashboard module requires streamlit which may not be in the test
environment, so we test the pure SQLite logic directly.
"""
import os
import sqlite3
import tempfile
import pytest


def _ensure_settings_table(conn: sqlite3.Connection) -> None:
    """Mirror of dashboard.app._ensure_settings_table."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS dashboard_settings "
        "(key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.commit()


def _read_setting(db_path: str, key: str, default: str = "") -> str:
    """Mirror of dashboard.app._read_setting."""
    if not os.path.exists(db_path):
        return default
    try:
        with sqlite3.connect(db_path) as conn:
            _ensure_settings_table(conn)
            row = conn.execute(
                "SELECT value FROM dashboard_settings WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else default
    except Exception:
        return default


def _write_setting(db_path: str, key: str, value: str) -> None:
    """Mirror of dashboard.app._write_setting."""
    with sqlite3.connect(db_path) as conn:
        _ensure_settings_table(conn)
        conn.execute(
            "INSERT INTO dashboard_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()


def test_write_and_read_setting():
    """Settings can be written and read back from the DB."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _write_setting(db_path, "max_daily_budget", "750")
        result = _read_setting(db_path, "max_daily_budget", "500")
        assert result == "750"
    finally:
        os.unlink(db_path)


def test_read_setting_default_when_no_db():
    """Reading a setting when DB doesn't exist returns the default."""
    result = _read_setting("/tmp/nonexistent_pop_test_12345.db", "max_daily_budget", "500")
    assert result == "500"


def test_write_setting_upsert():
    """Writing the same key twice should update, not duplicate."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _write_setting(db_path, "max_daily_budget", "100")
        _write_setting(db_path, "max_daily_budget", "200")
        result = _read_setting(db_path, "max_daily_budget", "500")
        assert result == "200"

        # Verify only one row exists
        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM dashboard_settings WHERE key = 'max_daily_budget'"
            ).fetchone()[0]
            assert count == 1
    finally:
        os.unlink(db_path)


def test_ensure_settings_table_creates_table():
    """_ensure_settings_table should create the table if it doesn't exist."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with sqlite3.connect(db_path) as conn:
            _ensure_settings_table(conn)
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_settings'"
            ).fetchone()
            assert row is not None
    finally:
        os.unlink(db_path)


def test_read_setting_returns_default_for_missing_key():
    """Reading a key that doesn't exist returns the default."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        result = _read_setting(db_path, "nonexistent_key", "42")
        assert result == "42"
    finally:
        os.unlink(db_path)
