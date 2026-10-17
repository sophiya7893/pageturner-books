"""DEPRECATED legacy one-off migration script.

Use `python migrate.py` for the numbered, transactional migration runner.
This file is retained for reference only and intentionally does not execute
legacy table rewrites when run directly.
"""

import os
import sqlite3


# ============================================================
# PAGE TURNER BOOKS
# DATABASE MIGRATION
#
# STEPS 57 - 63
#
# IMPORTANT:
# - Existing data is preserved.
# - Money values use INTEGER PAISE.
# - Migration is designed to be safe to run more than once.
# ============================================================


# ============================================================
# DATABASE PATH
# ============================================================

BASE_DIR = os.path.abspath(
    os.path.dirname(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "pageturner.db"
)


# ============================================================
# HELPER
# TABLE EXISTS
# ============================================================

def table_exists(
    db,
    table_name,
):

    row = db.execute(
        """
        SELECT name

        FROM sqlite_master

        WHERE type = 'table'
          AND name = ?
        """,
        (
            table_name,
        ),
    ).fetchone()

    return row is not None


# ============================================================
# HELPER
# INDEX EXISTS
# ============================================================

def index_exists(
    db,
    index_name,
):

    row = db.execute(
        """
        SELECT name

        FROM sqlite_master

        WHERE type = 'index'
          AND name = ?
        """,
        (
            index_name,
        ),
    ).fetchone()

    return row is not None


# ============================================================
# HELPER
# COLUMN EXISTS
# ============================================================

def column_exists(
    db,
    table_name,
    column_name,
):

    rows = db.execute(
        f"""
        PRAGMA table_info({table_name})
        """
    ).fetchall()

    for row in rows:

        if row[1] == column_name:
            return True

    return False


# ============================================================
# HELPER
# ADD COLUMN IF MISSING
# ============================================================

def add_column_if_missing(
    db,
    table_name,
    column_name,
    column_definition,
):

    if column_exists(
        db,
        table_name,
        column_name,
    ):

        print(
            f"{table_name}.{column_name} "
            "already exists."
        )

        return False

    db.execute(
        f"""
        ALTER TABLE {table_name}

        ADD COLUMN
            {column_name}
            {column_definition}
        """
    )

    print(
        f"Added "
        f"{table_name}.{column_name}."
    )

    return True


# ============================================================
# HELPER
# GET TABLE CREATE SQL
# ============================================================

def get_table_sql(
    db,
    table_name,
):

    row = db.execute(
        """
        SELECT sql

        FROM sqlite_master

        WHERE type = 'table'
          AND name = ?
        """,
        (
            table_name,
        ),
    ).fetchone()

    if row is None:
        return ""

    return (
        row[0]
        or ""
    )


# ============================================================
# HELPER
# REQUIRED BASE TABLE
# ============================================================

def require_table(
    db,
    table_name,
):

    if not table_exists(
        db,
        table_name,
    ):

        raise RuntimeError(
            (
                f"Required table "
                f"'{table_name}' "
                "does not exist."
            )
        )


# ============================================================
# CHECK REQUIRED TABLES
# ============================================================

def validate_base_database(db):

    required_tables = [
        "users",
        "books",
        "categories",
        "orders",
        "order_items",
        "coupons",
        "stock_log",
    ]

    for table_name in required_tables:

        require_table(
            db,
            table_name,
        )

    print(
        "Base database tables checked."
    )


# ============================================================
# STEP 57
# ORDER STATUS HISTORY
# ============================================================

def migrate_order_status_history(
    db,
):

    print()
    print(
        "----------------------------------------"
    )
    print(
        "STEP 57 - ORDER STATUS HISTORY"
    )
    print(
        "----------------------------------------"
    )

    # --------------------------------------------------------
    # CREATE TABLE
    # --------------------------------------------------------

    if not table_exists(
        db,
        "order_status_history",
    ):

        db.execute(
            """
            CREATE TABLE order_status_history
            (
                id INTEGER PRIMARY KEY
                    AUTOINCREMENT,

                order_id INTEGER NOT NULL,

                status TEXT NOT NULL
                    CHECK (
                        status IN (
                            'Placed',
                            'Packed',
                            'Shipped',
                            'Delivered',
                            'Cancelled'
                        )
                    ),

                changed_by INTEGER NOT NULL,

                changed_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                note TEXT,

                FOREIGN KEY (order_id)
                    REFERENCES orders(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (changed_by)
                    REFERENCES users(id)
            )
            """
        )

        print(
            "Step 57: "
            "order_status_history created."
        )

    else:

        print(
            "Step 57: "
            "order_status_history already exists."
        )

    # --------------------------------------------------------
    # INDEX
    # --------------------------------------------------------

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_order_status_history_order

        ON order_status_history(
            order_id,
            changed_at
        )
        """
    )

    # --------------------------------------------------------
    # BACKFILL OLD ORDERS
    #
    # IMPORTANT:
    #
    # changed_by is NOT NULL.
    #
    # Therefore only orders with a real existing user are
    # imported.
    #
    # We do NOT invent a user ID.
    # --------------------------------------------------------

    cursor = db.execute(
        """
        INSERT INTO order_status_history
        (
            order_id,
            status,
            changed_by,
            changed_at,
            note
        )

        SELECT
            o.id,
            o.status,
            o.user_id,
            o.created_at,
            'Initial status imported during migration.'

        FROM orders AS o

        INNER JOIN users AS u
            ON u.id = o.user_id

        WHERE o.user_id IS NOT NULL

          AND o.status IN (
              'Placed',
              'Packed',
              'Shipped',
              'Delivered',
              'Cancelled'
          )

          AND NOT EXISTS
          (
              SELECT 1

              FROM order_status_history AS h

              WHERE h.order_id = o.id
          )
        """
    )

    print(
        "Step 57:",
        cursor.rowcount,
        "existing order history row(s) added."
    )

    # --------------------------------------------------------
    # REPORT LEGACY ORDERS WITHOUT VALID USER
    # --------------------------------------------------------

    missing_row = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM orders AS o

        LEFT JOIN users AS u
            ON u.id = o.user_id

        WHERE (
            o.user_id IS NULL
            OR u.id IS NULL
        )

        AND NOT EXISTS
        (
            SELECT 1

            FROM order_status_history AS h

            WHERE h.order_id = o.id
        )
        """
    ).fetchone()

    missing_count = int(
        missing_row[0]
        or 0
    )

    if missing_count > 0:

        print(
            "Step 57 warning:",
            missing_count,
            "legacy order(s) have no valid user "
            "and were not backfilled."
        )

    print(
        "Step 57 completed."
    )


# ============================================================
# STEP 59
# COUPON MANAGEMENT
# ============================================================

def migrate_coupon_management(
    db,
):

    print()
    print(
        "----------------------------------------"
    )
    print(
        "STEP 59 - COUPON MANAGEMENT"
    )
    print(
        "----------------------------------------"
    )

    require_table(
        db,
        "coupons",
    )

    # --------------------------------------------------------
    # USAGE LIMIT
    #
    # NULL = unlimited
    # --------------------------------------------------------

    add_column_if_missing(
        db,
        "coupons",
        "usage_limit",
        """
        INTEGER
        CHECK (
            usage_limit IS NULL
            OR usage_limit > 0
        )
        """,
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_coupons_active

        ON coupons(active)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_coupons_expiry

        ON coupons(expiry_date)
        """
    )

    print(
        "Step 59 completed."
    )


# ============================================================
# STEP 60
# ADVANCED COUPON RULES
# ============================================================

def migrate_advanced_coupon_rules(
    db,
):

    print()
    print(
        "----------------------------------------"
    )
    print(
        "STEP 60 - ADVANCED COUPON RULES"
    )
    print(
        "----------------------------------------"
    )

    # --------------------------------------------------------
    # MINIMUM ORDER
    # --------------------------------------------------------

    add_column_if_missing(
        db,
        "coupons",
        "minimum_order_paise",
        """
        INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            minimum_order_paise >= 0
        )
        """,
    )

    # --------------------------------------------------------
    # MAXIMUM DISCOUNT
    #
    # NULL = no maximum
    # --------------------------------------------------------

    add_column_if_missing(
        db,
        "coupons",
        "max_discount_paise",
        """
        INTEGER
        CHECK (
            max_discount_paise IS NULL
            OR max_discount_paise >= 0
        )
        """,
    )

    # --------------------------------------------------------
    # ONE USE PER CUSTOMER
    # --------------------------------------------------------

    add_column_if_missing(
        db,
        "coupons",
        "one_use_per_customer",
        """
        INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            one_use_per_customer
            IN (0, 1)
        )
        """,
    )

    # --------------------------------------------------------
    # OPTIONAL CATEGORY
    #
    # NULL = coupon applies to all categories
    # --------------------------------------------------------

    add_column_if_missing(
        db,
        "coupons",
        "category_id",
        """
        INTEGER
        REFERENCES categories(id)
        ON DELETE SET NULL
        """,
    )

    # --------------------------------------------------------
    # COUPON USES
    # --------------------------------------------------------

    if not table_exists(
        db,
        "coupon_uses",
    ):

        db.execute(
            """
            CREATE TABLE coupon_uses
            (
                id INTEGER PRIMARY KEY
                    AUTOINCREMENT,

                coupon_id INTEGER NOT NULL,

                user_id INTEGER NOT NULL,

                order_id INTEGER NOT NULL,

                used_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE (
                    coupon_id,
                    order_id
                ),

                FOREIGN KEY (coupon_id)
                    REFERENCES coupons(id),

                FOREIGN KEY (user_id)
                    REFERENCES users(id),

                FOREIGN KEY (order_id)
                    REFERENCES orders(id)
                    ON DELETE CASCADE
            )
            """
        )

        print(
            "Step 60: "
            "coupon_uses created."
        )

    else:

        print(
            "Step 60: "
            "coupon_uses already exists."
        )

    # --------------------------------------------------------
    # INDEXES
    # --------------------------------------------------------

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_coupon_uses_coupon

        ON coupon_uses(
            coupon_id
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_coupon_uses_user

        ON coupon_uses(
            user_id
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_coupon_uses_order

        ON coupon_uses(
            order_id
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_coupon_uses_coupon_user

        ON coupon_uses(
            coupon_id,
            user_id
        )
        """
    )

    print(
        "Step 60 completed."
    )


# ============================================================
# STEP 61
# SHIPPING + TAX
# ============================================================

def migrate_shipping_and_tax(
    db,
):

    print()
    print(
        "----------------------------------------"
    )
    print(
        "STEP 61 - SHIPPING + TAX"
    )
    print(
        "----------------------------------------"
    )

    require_table(
        db,
        "orders",
    )

    # --------------------------------------------------------
    # SUBTOTAL
    # --------------------------------------------------------

    subtotal_added = (
        add_column_if_missing(
            db,
            "orders",
            "subtotal_paise",
            """
            INTEGER NOT NULL
            DEFAULT 0
            CHECK (
                subtotal_paise >= 0
            )
            """,
        )
    )

    # --------------------------------------------------------
    # SHIPPING
    # --------------------------------------------------------

    add_column_if_missing(
        db,
        "orders",
        "shipping_paise",
        """
        INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            shipping_paise >= 0
        )
        """,
    )

    # --------------------------------------------------------
    # TAX
    # --------------------------------------------------------

    add_column_if_missing(
        db,
        "orders",
        "tax_paise",
        """
        INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            tax_paise >= 0
        )
        """,
    )

    # --------------------------------------------------------
    # BACKFILL HISTORICAL SUBTOTALS
    #
    # Only do this when the subtotal column has just been
    # created.
    #
    # This prevents a future rerun from overwriting a genuine
    # zero subtotal.
    #
    # Historical:
    #
    # total = subtotal - discount
    #
    # therefore:
    #
    # subtotal = total + discount
    #
    # Old orders did not have shipping/tax.
    # --------------------------------------------------------

    if subtotal_added:

        db.execute(
            """
            UPDATE orders

            SET subtotal_paise =
                total_paise
                +
                COALESCE(
                    discount_paise,
                    0
                )
            """
        )

        print(
            "Step 61: "
            "old order subtotals backfilled."
        )

    print(
        "Step 61 completed."
    )


# ============================================================
# STEP 62
# PRINTABLE INVOICE
#
# No new database table is required.
# The invoice uses:
#
# orders
# order_items
# users
#
# and the Step 61 money columns.
# ============================================================

def migrate_invoice(
    db,
):

    print()
    print(
        "----------------------------------------"
    )
    print(
        "STEP 62 - PRINTABLE INVOICE"
    )
    print(
        "----------------------------------------"
    )

    require_table(
        db,
        "orders",
    )

    require_table(
        db,
        "order_items",
    )

    required_columns = [
        "subtotal_paise",
        "discount_paise",
        "shipping_paise",
        "tax_paise",
        "total_paise",
    ]

    for column_name in required_columns:

        if not column_exists(
            db,
            "orders",
            column_name,
        ):

            raise RuntimeError(
                (
                    "Step 62 requires "
                    f"orders.{column_name}"
                )
            )

    print(
        "Step 62: "
        "no new table required."
    )

    print(
        "Step 62 completed."
    )


# ============================================================
# STEP 63
# RETURNS
# ============================================================

def migrate_returns(
    db,
):

    print()
    print(
        "----------------------------------------"
    )
    print(
        "STEP 63 - PARTIAL RETURNS"
    )
    print(
        "----------------------------------------"
    )

    # --------------------------------------------------------
    # RETURNS TABLE
    # --------------------------------------------------------

    if not table_exists(
        db,
        "returns",
    ):

        db.execute(
            """
            CREATE TABLE returns
            (
                id INTEGER PRIMARY KEY
                    AUTOINCREMENT,

                order_item_id INTEGER NOT NULL,

                quantity INTEGER NOT NULL
                    CHECK (
                        quantity > 0
                    ),

                reason TEXT NOT NULL,

                status TEXT NOT NULL
                    DEFAULT 'Pending'
                    CHECK (
                        status IN (
                            'Pending',
                            'Approved',
                            'Rejected'
                        )
                    ),

                requested_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                reviewed_at TEXT,

                reviewed_by INTEGER,

                FOREIGN KEY (order_item_id)
                    REFERENCES order_items(id),

                FOREIGN KEY (reviewed_by)
                    REFERENCES users(id)
                    ON DELETE SET NULL
            )
            """
        )

        print(
            "Step 63: "
            "returns table created."
        )

    else:

        print(
            "Step 63: "
            "returns table already exists."
        )

    # --------------------------------------------------------
    # RETURN INDEXES
    # --------------------------------------------------------

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_returns_order_item

        ON returns(
            order_item_id
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_returns_status

        ON returns(
            status
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_returns_reviewed_by

        ON returns(
            reviewed_by
        )
        """
    )

    print(
        "Step 63: "
        "returns indexes ready."
    )


# ============================================================
# STEP 63
# STOCK LOG MUST SUPPORT returned_order
# ============================================================

def migrate_stock_log_for_returns(
    db,
):

    require_table(
        db,
        "stock_log",
    )

    create_sql = get_table_sql(
        db,
        "stock_log",
    )

    # --------------------------------------------------------
    # ALREADY UPGRADED
    # --------------------------------------------------------

    if "returned_order" in create_sql:

        print(
            "Step 63: "
            "stock_log already supports "
            "returned_order."
        )

        return

    print(
        "Step 63: "
        "upgrading stock_log..."
    )

    # --------------------------------------------------------
    # IMPORTANT
    #
    # SQLite cannot directly change an existing CHECK
    # constraint.
    #
    # Rebuild the table while preserving existing rows.
    # --------------------------------------------------------

    if table_exists(
        db,
        "stock_log_old_step63",
    ):

        raise RuntimeError(
            (
                "stock_log_old_step63 already exists. "
                "The previous stock_log migration may "
                "not have completed cleanly."
            )
        )

    # --------------------------------------------------------
    # RENAME OLD TABLE
    # --------------------------------------------------------

    db.execute(
        """
        ALTER TABLE stock_log

        RENAME TO stock_log_old_step63
        """
    )

    # --------------------------------------------------------
    # CREATE NEW TABLE
    # --------------------------------------------------------

    db.execute(
        """
        CREATE TABLE stock_log
        (
            id INTEGER PRIMARY KEY
                AUTOINCREMENT,

            book_id INTEGER NOT NULL,

            change INTEGER NOT NULL,

            reason TEXT NOT NULL
                CHECK (
                    reason IN (
                        'initial_stock',
                        'purchase',
                        'admin_edit',
                        'cancelled_order',
                        'returned_order'
                    )
                ),

            user_id INTEGER,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (book_id)
                REFERENCES books(id),

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )

    # --------------------------------------------------------
    # COPY EXISTING STOCK HISTORY
    # --------------------------------------------------------

    db.execute(
        """
        INSERT INTO stock_log
        (
            id,
            book_id,
            change,
            reason,
            user_id,
            created_at
        )

        SELECT
            id,
            book_id,
            change,
            reason,
            user_id,
            created_at

        FROM stock_log_old_step63

        ORDER BY
            id ASC
        """
    )

    # --------------------------------------------------------
    # VERIFY COPY
    # --------------------------------------------------------

    old_count = db.execute(
        """
        SELECT COUNT(*)

        FROM stock_log_old_step63
        """
    ).fetchone()[0]

    new_count = db.execute(
        """
        SELECT COUNT(*)

        FROM stock_log
        """
    ).fetchone()[0]

    if int(old_count) != int(new_count):

        raise RuntimeError(
            (
                "Stock log migration verification "
                "failed. Old row count does not "
                "match new row count."
            )
        )

    # --------------------------------------------------------
    # REMOVE OLD TABLE
    # --------------------------------------------------------

    db.execute(
        """
        DROP TABLE stock_log_old_step63
        """
    )

    # --------------------------------------------------------
    # RECREATE INDEXES
    # --------------------------------------------------------

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_stock_log_book

        ON stock_log(
            book_id
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_stock_log_created

        ON stock_log(
            created_at
        )
        """
    )

    print(
        "Step 63: "
        "stock_log upgraded successfully."
    )


# ============================================================
# VERIFY FINAL DATABASE
# ============================================================

def verify_migration(
    db,
):

    print()
    print(
        "----------------------------------------"
    )
    print(
        "VERIFYING STEPS 57 - 63"
    )
    print(
        "----------------------------------------"
    )

    # --------------------------------------------------------
    # REQUIRED TABLES
    # --------------------------------------------------------

    required_tables = [
        "order_status_history",
        "coupon_uses",
        "returns",
    ]

    for table_name in required_tables:

        if not table_exists(
            db,
            table_name,
        ):

            raise RuntimeError(
                (
                    "Migration verification failed: "
                    f"{table_name} is missing."
                )
            )

        print(
            "OK table:",
            table_name
        )

    # --------------------------------------------------------
    # COUPON COLUMNS
    # --------------------------------------------------------

    coupon_columns = [
        "usage_limit",
        "minimum_order_paise",
        "max_discount_paise",
        "one_use_per_customer",
        "category_id",
    ]

    for column_name in coupon_columns:

        if not column_exists(
            db,
            "coupons",
            column_name,
        ):

            raise RuntimeError(
                (
                    "Migration verification failed: "
                    f"coupons.{column_name} "
                    "is missing."
                )
            )

        print(
            "OK column:",
            f"coupons.{column_name}"
        )

    # --------------------------------------------------------
    # ORDER MONEY COLUMNS
    # --------------------------------------------------------

    order_columns = [
        "subtotal_paise",
        "shipping_paise",
        "tax_paise",
    ]

    for column_name in order_columns:

        if not column_exists(
            db,
            "orders",
            column_name,
        ):

            raise RuntimeError(
                (
                    "Migration verification failed: "
                    f"orders.{column_name} "
                    "is missing."
                )
            )

        print(
            "OK column:",
            f"orders.{column_name}"
        )

    # --------------------------------------------------------
    # STOCK LOG
    # --------------------------------------------------------

    stock_log_sql = get_table_sql(
        db,
        "stock_log",
    )

    if "returned_order" not in stock_log_sql:

        raise RuntimeError(
            (
                "Migration verification failed: "
                "stock_log does not support "
                "returned_order."
            )
        )

    print(
        "OK:",
        "stock_log supports returned_order"
    )

    print()
    print(
        "Migration verification passed."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "========================================"
    )
    print(
        "PAGE TURNER BOOKS"
    )
    print(
        "STEPS 57 - 63 DATABASE MIGRATION"
    )
    print(
        "========================================"
    )

    print(
        "Database:",
        DATABASE
    )

    # --------------------------------------------------------
    # DATABASE MUST ALREADY EXIST
    #
    # This migration is for your existing PageTurner
    # database. It should NOT silently create a blank DB.
    # --------------------------------------------------------

    if not os.path.exists(
        DATABASE
    ):

        raise FileNotFoundError(
            (
                "pageturner.db was not found at:\n"
                f"{DATABASE}\n\n"
                "Do not continue until the database "
                "path is correct."
            )
        )

    db = sqlite3.connect(
        DATABASE,
        timeout=10,
    )

    try:

        # ----------------------------------------------------
        # DATABASE SETTINGS
        # ----------------------------------------------------

        db.execute(
            "PRAGMA foreign_keys = ON"
        )

        db.execute(
            "PRAGMA busy_timeout = 10000"
        )

        # ----------------------------------------------------
        # CHECK BASE DATABASE
        # ----------------------------------------------------

        validate_base_database(
            db
        )

        # ----------------------------------------------------
        # ONE MIGRATION TRANSACTION
        # ----------------------------------------------------

        db.execute(
            "BEGIN IMMEDIATE"
        )

        # ----------------------------------------------------
        # STEP 57
        # ----------------------------------------------------

        migrate_order_status_history(
            db
        )

        # ----------------------------------------------------
        # STEP 58
        #
        # No DB migration required.
        # Uses order_status_history from Step 57.
        # ----------------------------------------------------

        print()
        print(
            "----------------------------------------"
        )
        print(
            "STEP 58 - ORDER TRACKING"
        )
        print(
            "----------------------------------------"
        )

        print(
            "Step 58: "
            "no database changes required."
        )

        # ----------------------------------------------------
        # STEP 59
        # ----------------------------------------------------

        migrate_coupon_management(
            db
        )

        # ----------------------------------------------------
        # STEP 60
        # ----------------------------------------------------

        migrate_advanced_coupon_rules(
            db
        )

        # ----------------------------------------------------
        # STEP 61
        # ----------------------------------------------------

        migrate_shipping_and_tax(
            db
        )

        # ----------------------------------------------------
        # STEP 62
        # ----------------------------------------------------

        migrate_invoice(
            db
        )

        # ----------------------------------------------------
        # STEP 63
        # ----------------------------------------------------

        migrate_returns(
            db
        )

        migrate_stock_log_for_returns(
            db
        )

        # ----------------------------------------------------
        # VERIFY BEFORE COMMIT
        # ----------------------------------------------------

        verify_migration(
            db
        )

        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        db.commit()

        print()
        print(
            "========================================"
        )
        print(
            "MIGRATION COMPLETED SUCCESSFULLY"
        )
        print(
            "STEPS 57 - 63 DATABASE READY"
        )
        print(
            "========================================"
        )
        print()

    except Exception as exc:

        db.rollback()

        print()
        print(
            "========================================"
        )
        print(
            "MIGRATION FAILED"
        )
        print(
            "========================================"
        )

        print(
            type(exc).__name__ + ":",
            str(exc)
        )

        print(
            "Database transaction rolled back."
        )

        raise

    finally:

        db.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()