"""Transactional, numbered SQLite migration runner for PageTurner Books."""
from pathlib import Path
import sqlite3
import os

BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("PAGETURNER_DATABASE", BASE_DIR / "pageturner.db"))
MIGRATIONS_DIR = BASE_DIR / "migrations"


def _statements(sql):
    """Yield one complete SQL statement at a time, without implicit commits."""
    buffer = ""
    for character in sql:
        buffer += character
        if character == ";" and sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                yield statement
            buffer = ""
    if buffer.strip():
        if not sqlite3.complete_statement(buffer):
            raise ValueError("Incomplete SQL statement at end of migration")
        yield buffer.strip()


def _clean_legacy_money(conn):
    """Copy legacy rupee-valued columns into integer paise before removing them.

    This runs inside the migration transaction, so any failure rolls back both
    the new columns and the conversion. Existing integer values are preserved.
    """
    mappings = (
        ("books", "price", "price_paise"),
        ("orders", "total_amount", "total_paise"),
        ("orders", "discount_amount", "discount_paise"),
        ("orders", "subtotal_amount", "subtotal_paise"),
        ("orders", "shipping_amount", "shipping_paise"),
        ("orders", "tax_amount", "tax_paise"),
        ("order_items", "price_at_purchase", "price_at_purchase_paise"),
        ("order_items", "price", "price_paise"),
        ("returns", "refund_amount", "refund_paise"),
    )
    for table, old_col, paise_col in mappings:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not table_exists:
            continue
        columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        if old_col not in columns:
            continue
        if paise_col not in columns:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{paise_col}" INTEGER NOT NULL DEFAULT 0')
        conn.execute(
            f'UPDATE "{table}" SET "{paise_col}" = CAST(ROUND(CAST("{old_col}" AS NUMERIC) * 100) AS INTEGER) WHERE "{old_col}" IS NOT NULL AND ("{paise_col}" IS NULL OR "{paise_col}" = 0)'
        )
        conn.execute(f'ALTER TABLE "{table}" DROP COLUMN "{old_col}"')


def _migrate_coupon_money(conn):
    """Normalize coupon monetary fields without retaining REAL money columns."""
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='coupons'").fetchone()
    if not exists:
        return
    columns = {row[1]: row[2].upper() for row in conn.execute('PRAGMA table_info("coupons")')}

    def add(name, definition):
        nonlocal columns
        if name not in columns:
            conn.execute(f'ALTER TABLE coupons ADD COLUMN "{name}" {definition}')
            columns[name] = definition.split()[0].upper()

    add("discount_type", "TEXT NOT NULL DEFAULT 'percentage'")
    add("min_order_paise", "INTEGER NOT NULL DEFAULT 0")
    add("max_discount_paise", "INTEGER")

    if "discount_value" not in columns:
        add("discount_value", "INTEGER NOT NULL DEFAULT 0")
    elif "REAL" in columns["discount_value"] or "FLOA" in columns["discount_value"] or "DOUB" in columns["discount_value"]:
        conn.execute("ALTER TABLE coupons ADD COLUMN discount_value_integer INTEGER NOT NULL DEFAULT 0")
        conn.execute("""UPDATE coupons SET discount_value_integer = CASE
            WHEN LOWER(COALESCE(discount_type, 'percentage')) = 'fixed'
                THEN CAST(ROUND(COALESCE(discount_value, 0) * 100) AS INTEGER)
            ELSE CAST(ROUND(COALESCE(discount_value, 0)) AS INTEGER) END""")
        conn.execute("ALTER TABLE coupons DROP COLUMN discount_value")
        conn.execute("ALTER TABLE coupons RENAME COLUMN discount_value_integer TO discount_value")
        columns.pop("discount_value", None)
        columns["discount_value"] = "INTEGER"

    if "min_order_amount" in columns:
        conn.execute("UPDATE coupons SET min_order_paise=CAST(ROUND(COALESCE(min_order_amount,0)*100) AS INTEGER)")
        conn.execute("ALTER TABLE coupons DROP COLUMN min_order_amount")
    if "max_discount" in columns:
        conn.execute("UPDATE coupons SET max_discount_paise=CASE WHEN max_discount IS NULL THEN max_discount_paise ELSE CAST(ROUND(max_discount*100) AS INTEGER) END")
        conn.execute("ALTER TABLE coupons DROP COLUMN max_discount")

    # Normalize older coupon schemas used by the earlier roadmap versions.
    add("start_date", "TEXT")
    add("end_date", "TEXT")
    add("usage_limit", "INTEGER")
    add("used_count", "INTEGER NOT NULL DEFAULT 0")
    add("is_active", "INTEGER NOT NULL DEFAULT 1")
    add("created_at", "TEXT")
    current = {row[1] for row in conn.execute('PRAGMA table_info("coupons")')}
    if "expiry_date" in current:
        conn.execute("UPDATE coupons SET end_date=COALESCE(end_date, expiry_date)")
    if "active" in current:
        conn.execute("UPDATE coupons SET is_active=active")


def _backfill_coupon_minimum(conn):
    """Preserve the prior integer-paise minimum-order field name if present."""
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='coupons'").fetchone()
    if not exists:
        return
    columns = {row[1] for row in conn.execute('PRAGMA table_info("coupons")')}
    if "minimum_order_paise" in columns and "min_order_paise" in columns:
        conn.execute("UPDATE coupons SET min_order_paise=minimum_order_paise WHERE COALESCE(min_order_paise,0)=0 AND COALESCE(minimum_order_paise,0)>0")




def _migrate_advanced_coupon_rules(conn):
    """Add advanced coupon fields while tolerating columns added by older runtime code."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='coupons'"
    ).fetchone()
    if not exists:
        return
    columns = {row[1] for row in conn.execute('PRAGMA table_info("coupons")')}
    if "one_use_per_customer" not in columns:
        conn.execute(
            "ALTER TABLE coupons ADD COLUMN one_use_per_customer INTEGER NOT NULL DEFAULT 0 CHECK (one_use_per_customer IN (0,1))"
        )
    if "category_id" not in columns:
        conn.execute(
            "ALTER TABLE coupons ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL"
        )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_coupons_category_id ON coupons(category_id)")

def _upgrade_orders_status_constraint(conn):
    """Rebuild legacy orders tables whose CHECK constraint omitted Shipped."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
    if not row or "Shipped" in (row[0] or ""):
        return
    columns = {r[1] for r in conn.execute('PRAGMA table_info("orders")')}
    required = {"id", "user_id", "customer_name", "email", "phone", "address_snapshot", "total_paise", "discount_paise", "subtotal_paise", "shipping_paise", "tax_paise", "coupon_code", "status", "created_at"}
    if not required.issubset(columns):
        return
    conn.execute("PRAGMA legacy_alter_table=ON")
    conn.execute("""CREATE TABLE orders_step57_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        customer_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL DEFAULT '',
        address_snapshot TEXT NOT NULL,
        coupon_code TEXT,
        status TEXT NOT NULL DEFAULT 'Placed' CHECK(status IN ('Placed','Packed','Shipped','Delivered','Cancelled')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        total_paise INTEGER NOT NULL DEFAULT 0,
        discount_paise INTEGER NOT NULL DEFAULT 0,
        subtotal_paise INTEGER NOT NULL DEFAULT 0 CHECK(subtotal_paise >= 0),
        shipping_paise INTEGER NOT NULL DEFAULT 0 CHECK(shipping_paise >= 0),
        tax_paise INTEGER NOT NULL DEFAULT 0 CHECK(tax_paise >= 0),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
    )""")
    conn.execute("""INSERT INTO orders_step57_new
        (id,user_id,customer_name,email,phone,address_snapshot,coupon_code,status,created_at,total_paise,discount_paise,subtotal_paise,shipping_paise,tax_paise)
        SELECT id,user_id,COALESCE(customer_name,''),COALESCE(email,''),COALESCE(phone,''),COALESCE(address_snapshot,''),coupon_code,
        CASE WHEN status='Pending' THEN 'Placed' WHEN status IN ('Placed','Packed','Shipped','Delivered','Cancelled') THEN status ELSE 'Placed' END,
        COALESCE(created_at,CURRENT_TIMESTAMP),COALESCE(total_paise,0),COALESCE(discount_paise,0),COALESCE(subtotal_paise,0),COALESCE(shipping_paise,0),COALESCE(tax_paise,0)
        FROM orders""")
    conn.execute("DROP TABLE orders")
    conn.execute("ALTER TABLE orders_step57_new RENAME TO orders")
    conn.execute("PRAGMA legacy_alter_table=OFF")

def migrate(database=DATABASE):
    database = str(database)
    conn = sqlite3.connect(database, timeout=30, isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("BEGIN IMMEDIATE")
        schema_version_existed = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone() is not None
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, filename TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(schema_version)")}
        version_name_column = "filename" if "filename" in columns else "name"
        conn.commit()
        files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
        for path in files:
            version = int(path.name[:3])
            if conn.execute("SELECT 1 FROM schema_version WHERE version=?", (version,)).fetchone():
                continue
            sql = path.read_text(encoding="utf-8")
            if version == 8:
                # This legacy-table rebuild needs foreign keys disabled outside the transaction;
                # the migration itself remains atomic and foreign keys are restored immediately after.
                conn.commit()
                conn.execute("PRAGMA foreign_keys=OFF")
                conn.execute("PRAGMA legacy_alter_table=ON")
            conn.execute("BEGIN IMMEDIATE")
            try:
                if version == 8:
                    _upgrade_orders_status_constraint(conn)
                if version == 4:
                    _clean_legacy_money(conn)
                if version == 6:
                    _migrate_coupon_money(conn)
                if version == 7:
                    _backfill_coupon_minimum(conn)
                if version == 11:
                    _migrate_advanced_coupon_rules(conn)
                for statement in _statements(sql):
                    conn.execute(statement)
                conn.execute(f"INSERT INTO schema_version(version,{version_name_column}) VALUES(?,?)", (version, path.name))
                # Validate a table-rebuild migration before COMMIT. A failed
                # foreign-key check must roll back the schema change as well.
                if version == 8:
                    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                    if violations:
                        raise sqlite3.IntegrityError(
                            f"Foreign key violations after {path.name}: {violations[:5]}"
                        )
                conn.commit()
                if version == 8:
                    conn.execute("PRAGMA legacy_alter_table=OFF")
                    conn.execute("PRAGMA foreign_keys=ON")
                print(f"Applied {path.name}")
            except Exception:
                conn.rollback()
                if version == 8:
                    conn.execute("PRAGMA legacy_alter_table=OFF")
                    conn.execute("PRAGMA foreign_keys=ON")
                # If this was a brand-new database and the very first
                # migration failed, remove the runner's bootstrap table too.
                # The database is then byte-for-byte equivalent at the schema
                # level to its state before this attempted migration.
                if not schema_version_existed:
                    remaining = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
                    if remaining == 0:
                        conn.execute("DROP TABLE IF EXISTS schema_version")
                raise
        print("Database migrations are up to date.")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
