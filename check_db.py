
import sqlite3
from pathlib import Path

database = Path(__file__).resolve().parent / "pageturner.db"

db = sqlite3.connect(database)

tables = db.execute(
    """
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
    """
).fetchall()

print("DATABASE TABLES:")
for table in tables:
    print("-", table[0])

for table_name in (
    "users",
    "orders",
    "order_items",
    "addresses",
    "password_reset_tokens",
    "login_attempts",
    "stock_log",
):
    print(f"\nCOLUMNS IN {table_name}:")

    columns = db.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    for column in columns:
        print("-", column[1])

db.close()
