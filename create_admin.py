"""Create or reset an administrator account for a local PageTurner install."""
from __future__ import annotations
import getpass
import os
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = os.environ.get("PAGETURNER_DATABASE", str(BASE_DIR / "pageturner.db"))


def main() -> None:
    if not Path(DATABASE).exists():
        raise SystemExit(f"Database not found: {DATABASE}. Run python migrate.py first.")
    name = input("Admin display name: ").strip()
    email = input("Admin email: ").strip().lower()
    password = getpass.getpass("Admin password (minimum 12 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if not name or not email or "@" not in email:
        raise SystemExit("Enter a name and valid email address.")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    conn = sqlite3.connect(DATABASE, timeout=30)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        password_hash = generate_password_hash(password)
        if existing:
            conn.execute("UPDATE users SET name=?, password_hash=?, role='admin' WHERE id=?", (name, password_hash, existing[0]))
        else:
            conn.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'admin')", (name, email, password_hash))
        conn.commit()
        print(f"Administrator account ready for {email}.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
