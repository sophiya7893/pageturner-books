"""Idempotently add a small demo catalogue and coupons after migrate.py."""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE = os.environ.get("PAGETURNER_DATABASE", str(BASE_DIR / "pageturner.db"))

BOOKS = [
    ("Atomic Habits", "James Clear", "Self Help", 49900, 10, "A practical guide to building good habits.", "" , ["habits", "personal growth"]),
    ("Deep Work", "Cal Newport", "Productivity", 45000, 8, "Rules for focused success in a distracted world.", "", ["focus", "productivity"]),
    ("Clean Code", "Robert C. Martin", "Programming", 69900, 6, "A guide to readable and maintainable software.", "", ["software", "programming"]),
    ("Python Crash Course", "Eric Matthes", "Programming", 79900, 5, "A hands-on introduction to Python programming.", "", ["python", "programming"]),
    ("The Pragmatic Programmer", "Andrew Hunt", "Programming", 65000, 7, "Practical advice for software developers.", "", ["software", "programming"]),
    ("A Brief History of Time", "Stephen Hawking", "Science", 55000, 8, "An introduction to cosmology and modern physics.", "", ["science", "space"]),
    ("Sapiens", "Yuval Noah Harari", "History", 69900, 10, "A broad history of humankind.", "", ["history", "humanity"]),
    ("The Alchemist", "Paulo Coelho", "Fiction", 39900, 15, "A young shepherd follows his dreams.", "", ["fiction", "novel"]),
]


def main() -> None:
    path = Path(DATABASE)
    if not path.exists():
        raise SystemExit(f"Database not found: {path}. Run python migrate.py first.")
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        for title, author, category, price, stock, description, cover, tags in BOOKS:
            row = conn.execute("SELECT id FROM books WHERE title=? COLLATE NOCASE AND author=? COLLATE NOCASE", (title, author)).fetchone()
            if row:
                book_id = row["id"]
            else:
                book_id = conn.execute(
                    "INSERT INTO books(title,author,category,price_paise,stock,description,cover_image) VALUES(?,?,?,?,?,?,?)",
                    (title, author, category, price, stock, description, cover or None),
                ).lastrowid
            cat = conn.execute("SELECT id FROM categories WHERE name=? COLLATE NOCASE", (category,)).fetchone()
            category_id = cat["id"] if cat else conn.execute("INSERT INTO categories(name) VALUES(?)", (category,)).lastrowid
            conn.execute("INSERT OR IGNORE INTO book_categories(book_id,category_id) VALUES(?,?)", (book_id, category_id))
            for tag in tags:
                tag_row = conn.execute("SELECT id FROM tags WHERE name=? COLLATE NOCASE", (tag,)).fetchone()
                tag_id = tag_row["id"] if tag_row else conn.execute("INSERT INTO tags(name) VALUES(?)", (tag,)).lastrowid
                conn.execute("INSERT OR IGNORE INTO book_tags(book_id,tag_id) VALUES(?,?)", (book_id, tag_id))
        for code, percent in (("WELCOME10", 10), ("BOOK20", 20)):
            conn.execute("""INSERT OR IGNORE INTO coupons
                (code,percent,expiry_date,active,discount_type,discount_value,end_date,is_active)
                VALUES(?,?, '2099-12-31',1,'percentage',?,'2099-12-31',1)""", (code, percent, percent))
        conn.commit()
        print(f"Demo catalogue ready in {path}.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
