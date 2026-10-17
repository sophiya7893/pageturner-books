
import sqlite3
from app import app

database_path = app.config["DATABASE"]
print("Database:", database_path)

connection = sqlite3.connect(database_path)

try:
    for table_name in ("returns", "return_items", "orders", "order_items"):
        print(f"\n--- {table_name} ---")

        exists = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table_name,)
        ).fetchone()

        if not exists:
            print("Table does not exist")
            continue

        columns = connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()

        for column in columns:
            print(f"Column: {column[1]} | Type: {column[2]}")

finally:
    connection.close()
