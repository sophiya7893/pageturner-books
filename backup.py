"""Create a consistent SQLite backup and retain only the latest five backups.

Usage:
    python backup.py
    python backup.py --database path/to/pageturner.db --backup-dir backups

The SQLite backup API supports making a consistent copy while the application
is running; it is safer than copying the database file directly.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def create_backup(database: str | Path, backup_dir: str | Path, keep: int = 5) -> Path:
    source_path = Path(database).expanduser().resolve()
    destination_dir = Path(backup_dir).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Database does not exist: {source_path}")
    if keep < 1:
        raise ValueError("keep must be at least 1")
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    destination = destination_dir / f"pageturner-{stamp}.db"
    # Avoid overwriting a backup if multiple runs happen in the same second.
    suffix = 1
    while destination.exists():
        destination = destination_dir / f"pageturner-{stamp}-{suffix}.db"
        suffix += 1

    source = sqlite3.connect(str(source_path), timeout=30)
    target = sqlite3.connect(str(destination), timeout=30)
    try:
        source.backup(target)
        integrity = target.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise sqlite3.DatabaseError(f"Backup integrity check failed: {integrity[0] if integrity else 'no result'}")
        target.commit()
    except Exception:
        target.close()
        source.close()
        destination.unlink(missing_ok=True)
        raise
    else:
        target.close()
        source.close()

    backups = sorted(
        destination_dir.glob("pageturner-*.db"),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    for old in backups[keep:]:
        old.unlink(missing_ok=True)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up the PageTurner SQLite database")
    parser.add_argument("--database", default=os.environ.get("PAGETURNER_DATABASE", str(BASE_DIR / "pageturner.db")))
    parser.add_argument("--backup-dir", default=str(BASE_DIR / "backups"))
    parser.add_argument("--keep", type=int, default=5)
    args = parser.parse_args()
    path = create_backup(args.database, args.backup_dir, args.keep)
    print(f"Backup created: {path}")
    print(f"Retained at most {args.keep} backups in {Path(args.backup_dir).resolve()}")


if __name__ == "__main__":
    main()
