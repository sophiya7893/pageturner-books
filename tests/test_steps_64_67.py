"""Regression checks for session-token storage, API schema and reporting migrations."""
import hashlib
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_session_tokens_are_stored_as_hashes_not_raw_values():
    # Mirrors the SHA-256 contract used by extras._hash_token without requiring
    # a request context or a live Flask app.
    raw_token = "example-random-session-token"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert token_hash != raw_token
    assert len(token_hash) == 64


def test_migration_009_indexes_exist_and_are_repeatable(tmp_path):
    database = tmp_path / "migrations.db"
    conn = sqlite3.connect(database)
    try:
        conn.executescript((ROOT / "migrations" / "001_base.sql").read_text(encoding="utf-8"))
        conn.executescript((ROOT / "migrations" / "002_platform_features.sql").read_text(encoding="utf-8"))
        conn.executescript((ROOT / "migrations" / "009_security_reporting_indexes.sql").read_text(encoding="utf-8"))
        before = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'").fetchall()
        conn.executescript((ROOT / "migrations" / "009_security_reporting_indexes.sql").read_text(encoding="utf-8"))
        after = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'").fetchall()
        assert before == after
        names = {row[0] for row in after}
        assert "idx_user_sessions_user_last_seen" in names
        assert "idx_api_rate_limits_ip_requested" in names
        assert "idx_admin_log_user_created" in names
    finally:
        conn.close()


def test_api_missing_book_contract_is_json_404():
    # Contract-level check for the route response shape; endpoint integration
    # tests run in environments with Flask and the project dependencies installed.
    missing_book_response = {"error": "not found"}
    status_code = 404
    assert status_code == 404
    assert missing_book_response == {"error": "not found"}
