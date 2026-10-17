
import sqlite3

from config import Config

db_path = Config.DATABASE

connection = sqlite3.connect(db_path)

columns = connection.execute(
    "PRAGMA table_info(coupons)"
).fetchall()

print("Coupons table columns:")

for column in columns:
    print(column[1], column[2])

connection.close()
