import sqlite3
from pathlib import Path

from backup import create_backup


def test_backup_uses_sqlite_backup_and_keeps_latest_five(tmp_path):
    database = tmp_path / "source.db"
    conn = sqlite3.connect(database)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO sample(value) VALUES ('kept')")
    conn.commit()
    conn.close()

    backup_dir = tmp_path / "backups"
    paths = []
    for _ in range(6):
        paths.append(create_backup(database, backup_dir, keep=5))

    backups = list(backup_dir.glob("pageturner-*.db"))
    assert len(backups) == 5
    newest = sqlite3.connect(paths[-1])
    try:
        assert newest.execute("SELECT value FROM sample").fetchone()[0] == "kept"
        assert newest.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        newest.close()


def test_backup_fails_for_missing_database(tmp_path):
    try:
        create_backup(tmp_path / "missing.db", tmp_path / "backups")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Expected missing database to raise FileNotFoundError")
