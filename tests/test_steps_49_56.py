"""SQLite-level regression tests for catalogue and account constraints."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def connection_with_schema():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    return conn


def test_multi_category_filter_uses_group_by_and_having():
    conn = connection_with_schema()
    try:
        # Use the existing schema's book columns but keep the fixture minimal.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(books)")}
        values = {
            "title": "Python for Everyone", "author": "A. Writer",
            "price_paise": 3333, "stock": 5, "description": "test",
            "cover_image": "", "category": "Programming",
        }
        fields = [key for key in values if key in columns]
        conn.execute(
            f"INSERT INTO books ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            [values[key] for key in fields],
        )
        book_id = conn.execute("SELECT id FROM books WHERE title=?", ("Python for Everyone",)).fetchone()[0]
        for name in ("Programming", "Technology"):
            conn.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (name,))
            category_id = conn.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()[0]
            conn.execute("INSERT INTO book_categories(book_id,category_id) VALUES (?,?)", (book_id, category_id))
        result = conn.execute(
            """SELECT b.id FROM books b WHERE b.id IN (
                   SELECT bc.book_id FROM book_categories bc
                   JOIN categories c ON c.id=bc.category_id
                   WHERE c.name IN (?,?) GROUP BY bc.book_id
                   HAVING COUNT(DISTINCT c.id)=?
               )""",
            ("Programming", "Technology", 2),
        ).fetchall()
        assert [row[0] for row in result] == [book_id]
    finally:
        conn.close()


def test_wishlist_and_cart_enforce_unique_user_book_pairs():
    conn = connection_with_schema()
    try:
        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        user_values = {"name": "Test Customer", "email": "steps49@example.test", "password_hash": "hash", "role": "customer"}
        fields = [key for key in user_values if key in user_columns]
        conn.execute(f"INSERT INTO users ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [user_values[key] for key in fields])
        user_id = conn.execute("SELECT id FROM users WHERE email=?", ("steps49@example.test",)).fetchone()[0]
        book_columns = {row[1] for row in conn.execute("PRAGMA table_info(books)")}
        book_values = {"title": "Unique Book", "author": "A. Writer", "price_paise": 1000, "stock": 2, "description": "test", "cover_image": "", "category": "Test"}
        book_fields = [key for key in book_values if key in book_columns]
        conn.execute(f"INSERT INTO books ({','.join(book_fields)}) VALUES ({','.join('?' for _ in book_fields)})", [book_values[key] for key in book_fields])
        book_id = conn.execute("SELECT id FROM books WHERE title=?", ("Unique Book",)).fetchone()[0]
        conn.execute("INSERT INTO wishlist(user_id,book_id) VALUES (?,?)", (user_id, book_id))
        conn.execute("INSERT OR IGNORE INTO wishlist(user_id,book_id) VALUES (?,?)", (user_id, book_id))
        conn.execute("INSERT INTO cart_items(user_id,book_id,quantity) VALUES (?,?,1)", (user_id, book_id))
        conn.execute("INSERT INTO cart_items(user_id,book_id,quantity) VALUES (?,?,2) ON CONFLICT(user_id,book_id) DO UPDATE SET quantity=excluded.quantity", (user_id, book_id))
        assert conn.execute("SELECT COUNT(*) FROM wishlist WHERE user_id=? AND book_id=?", (user_id, book_id)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM cart_items WHERE user_id=? AND book_id=?", (user_id, book_id)).fetchone()[0] == 1
        assert conn.execute("SELECT quantity FROM cart_items WHERE user_id=? AND book_id=?", (user_id, book_id)).fetchone()[0] == 2
    finally:
        conn.close()
