import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "pageturner.db"


# ============================================================
# HELPERS
# ============================================================

def table_exists(db, table_name):
    row = db.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,)
    ).fetchone()

    return row is not None


def get_columns(db, table_name):
    if not table_exists(db, table_name):
        return set()

    rows = db.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return {
        row["name"]
        for row in rows
    }


def add_column_if_missing(
    db,
    table_name,
    column_name,
    definition
):
    columns = get_columns(
        db,
        table_name
    )

    if column_name in columns:
        print(
            f"Already exists: "
            f"{table_name}.{column_name}"
        )
        return

    db.execute(
        f"""
        ALTER TABLE "{table_name}"
        ADD COLUMN "{column_name}"
        {definition}
        """
    )

    print(
        f"Added: "
        f"{table_name}.{column_name}"
    )


# ============================================================
# BACKUP
# ============================================================

def create_backup():
    timestamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup = BASE_DIR / (
        "pageturner-backup-"
        + timestamp
        + ".db"
    )

    shutil.copy2(
        DATABASE,
        backup
    )

    print(
        f"Backup created:\n{backup}"
    )

    return backup


# ============================================================
# USERS
# STEP 30
# ============================================================

def migrate_users(db):
    print("\n--- USERS ---")

    add_column_if_missing(
        db,
        "users",
        "role",
        "TEXT NOT NULL DEFAULT 'customer'"
    )

    db.execute(
        """
        UPDATE users
        SET role = 'customer'
        WHERE role IS NULL
           OR role NOT IN (
               'customer',
               'staff',
               'admin'
           )
        """
    )


# ============================================================
# ADDRESSES
# STEP 28
# ============================================================

def migrate_addresses(db):
    print("\n--- ADDRESSES ---")

    if not table_exists(
        db,
        "addresses"
    ):
        db.execute(
            """
            CREATE TABLE addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                label TEXT NOT NULL,

                line1 TEXT NOT NULL,

                city TEXT NOT NULL,

                pincode TEXT NOT NULL,

                is_default INTEGER NOT NULL DEFAULT 0
                    CHECK (
                        is_default IN (0, 1)
                    ),

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """
        )

        print(
            "Created addresses table."
        )

    else:
        columns = get_columns(
            db,
            "addresses"
        )

        required = {
            "id",
            "user_id",
            "label",
            "line1",
            "city",
            "pincode",
            "is_default",
        }

        if not required.issubset(
            columns
        ):
            print(
                "Converting old addresses table..."
            )

            db.execute(
                """
                ALTER TABLE addresses
                RENAME TO addresses_old
                """
            )

            db.execute(
                """
                CREATE TABLE addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL,

                    label TEXT NOT NULL,

                    line1 TEXT NOT NULL,

                    city TEXT NOT NULL,

                    pincode TEXT NOT NULL,

                    is_default INTEGER NOT NULL DEFAULT 0
                        CHECK (
                            is_default IN (0, 1)
                        ),

                    FOREIGN KEY (user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE
                )
                """
            )

            old_columns = get_columns(
                db,
                "addresses_old"
            )

            # Map the old assignment/project
            # address structure to the new one.
            if {
                "user_id",
                "address_line1",
                "city",
                "postal_code",
            }.issubset(old_columns):

                default_expression = (
                    "COALESCE(is_default, 0)"
                    if "is_default"
                    in old_columns
                    else "0"
                )

                db.execute(
                    f"""
                    INSERT INTO addresses
                    (
                        user_id,
                        label,
                        line1,
                        city,
                        pincode,
                        is_default
                    )

                    SELECT
                        user_id,
                        'Home',
                        address_line1,
                        city,
                        postal_code,
                        {default_expression}

                    FROM addresses_old
                    """
                )

            db.execute(
                """
                DROP TABLE addresses_old
                """
            )

    # --------------------------------------------------------
    # Make sure no user has multiple default addresses.
    # Keep only the lowest-ID default.
    # --------------------------------------------------------

    users = db.execute(
        """
        SELECT DISTINCT user_id
        FROM addresses
        """
    ).fetchall()

    for user in users:
        user_id = user["user_id"]

        addresses = db.execute(
            """
            SELECT id, is_default
            FROM addresses
            WHERE user_id = ?
            ORDER BY id
            """,
            (user_id,)
        ).fetchall()

        if not addresses:
            continue

        default_ids = [
            row["id"]
            for row in addresses
            if row["is_default"] == 1
        ]

        if default_ids:
            keep_id = default_ids[0]
        else:
            keep_id = addresses[0]["id"]

        db.execute(
            """
            UPDATE addresses
            SET is_default = 0
            WHERE user_id = ?
            """,
            (user_id,)
        )

        db.execute(
            """
            UPDATE addresses
            SET is_default = 1
            WHERE id = ?
            """,
            (keep_id,)
        )

    # SQLite partial unique index:
    # one default address maximum per user.
    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_addresses_one_default
        ON addresses(user_id)
        WHERE is_default = 1
        """
    )


# ============================================================
# ORDERS
# STEPS 28, 29, 35
# ============================================================

def migrate_orders(db):
    print("\n--- ORDERS ---")

    columns = get_columns(
        db,
        "orders"
    )

    if "address_snapshot" not in columns:
        add_column_if_missing(
            db,
            "orders",
            "address_snapshot",
            "TEXT NOT NULL DEFAULT ''"
        )

        columns = get_columns(
            db,
            "orders"
        )

        # Preserve the old order address.
        if "address" in columns:
            db.execute(
                """
                UPDATE orders
                SET address_snapshot = address
                WHERE (
                    address_snapshot IS NULL
                    OR address_snapshot = ''
                )
                """
            )

            print(
                "Copied old order addresses "
                "to address_snapshot."
            )

    # --------------------------------------------------------
    # Important:
    # Old orders table may have:
    #
    # CHECK(status IN ('Placed','Packed','Delivered'))
    #
    # ALTER TABLE cannot modify that constraint.
    # Rebuild only if Cancelled isn't allowed.
    # --------------------------------------------------------

    table_sql_row = db.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'orders'
        """
    ).fetchone()

    table_sql = (
        table_sql_row["sql"]
        if table_sql_row
        else ""
    )

    if (
        table_sql
        and "Cancelled"
        not in table_sql
    ):
        print(
            "Rebuilding orders table "
            "to support Cancelled..."
        )

        columns = get_columns(
            db,
            "orders"
        )

        db.execute(
            """
            ALTER TABLE orders
            RENAME TO orders_old
            """
        )

        db.execute(
            """
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER,

                customer_name TEXT NOT NULL,

                email TEXT NOT NULL,

                phone TEXT NOT NULL DEFAULT '',

                address_snapshot TEXT NOT NULL,

                total_amount REAL NOT NULL DEFAULT 0,

                discount_amount REAL NOT NULL DEFAULT 0,

                coupon_code TEXT,

                status TEXT NOT NULL DEFAULT 'Placed'
                    CHECK (
                        status IN (
                            'Placed',
                            'Packed',
                            'Delivered',
                            'Cancelled'
                        )
                    ),

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE SET NULL
            )
            """
        )

        old_columns = get_columns(
            db,
            "orders_old"
        )

        address_expression = (
            "address_snapshot"
            if "address_snapshot"
            in old_columns
            else (
                "address"
                if "address"
                in old_columns
                else "''"
            )
        )

        phone_expression = (
            "phone"
            if "phone" in old_columns
            else "''"
        )

        discount_expression = (
            "discount_amount"
            if "discount_amount"
            in old_columns
            else "0"
        )

        coupon_expression = (
            "coupon_code"
            if "coupon_code"
            in old_columns
            else "NULL"
        )

        created_expression = (
            "created_at"
            if "created_at"
            in old_columns
            else "CURRENT_TIMESTAMP"
        )

        db.execute(
            f"""
            INSERT INTO orders
            (
                id,
                user_id,
                customer_name,
                email,
                phone,
                address_snapshot,
                total_amount,
                discount_amount,
                coupon_code,
                status,
                created_at
            )

            SELECT
                id,
                user_id,
                customer_name,
                email,
                {phone_expression},
                {address_expression},
                total_amount,
                {discount_expression},
                {coupon_expression},
                status,
                {created_expression}

            FROM orders_old
            """
        )

        # Do not drop orders_old yet.
        #
        # order_items may still reference it while
        # foreign keys are disabled during migration.


# ============================================================
# ORDER ITEMS
# STEP 29
# ============================================================

def migrate_order_items(db):
    print("\n--- ORDER ITEMS ---")

    columns = get_columns(
        db,
        "order_items"
    )

    if (
        "price_at_purchase"
        in columns
    ):
        print(
            "price_at_purchase already exists."
        )

    elif "price" in columns:
        print(
            "Converting order_items.price "
            "to price_at_purchase..."
        )

        db.execute(
            """
            ALTER TABLE order_items
            RENAME TO order_items_old
            """
        )

        db.execute(
            """
            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                order_id INTEGER NOT NULL,

                book_id INTEGER NOT NULL,

                quantity INTEGER NOT NULL
                    CHECK (quantity > 0),

                price_at_purchase REAL NOT NULL,

                FOREIGN KEY (order_id)
                    REFERENCES orders(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (book_id)
                    REFERENCES books(id)
            )
            """
        )

        db.execute(
            """
            INSERT INTO order_items
            (
                id,
                order_id,
                book_id,
                quantity,
                price_at_purchase
            )

            SELECT
                id,
                order_id,
                book_id,
                quantity,
                price

            FROM order_items_old
            """
        )

        db.execute(
            """
            DROP TABLE order_items_old
            """
        )

    else:
        raise RuntimeError(
            "order_items has neither "
            "'price' nor 'price_at_purchase'."
        )

    # Safe now that order_items points to new orders.
    if table_exists(
        db,
        "orders_old"
    ):
        db.execute(
            """
            DROP TABLE orders_old
            """
        )


# ============================================================
# STEP 31
# PASSWORD RESET TOKENS
# ============================================================

def migrate_reset_tokens(db):
    print("\n--- RESET TOKENS ---")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            token_hash TEXT NOT NULL UNIQUE,

            expires_at TEXT NOT NULL,

            used INTEGER NOT NULL DEFAULT 0
                CHECK (used IN (0, 1)),

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )

    # Copy old password reset data if present.
    if table_exists(
        db,
        "password_reset_tokens"
    ):
        old_columns = get_columns(
            db,
            "password_reset_tokens"
        )

        if {
            "user_id",
            "token_hash",
            "expires_at",
        }.issubset(old_columns):

            if "used_at" in old_columns:
                used_expression = (
                    "CASE "
                    "WHEN used_at IS NULL "
                    "THEN 0 ELSE 1 END"
                )

            elif "used" in old_columns:
                used_expression = (
                    "COALESCE(used, 0)"
                )

            else:
                used_expression = "0"

            db.execute(
                f"""
                INSERT OR IGNORE INTO reset_tokens
                (
                    user_id,
                    token_hash,
                    expires_at,
                    used
                )

                SELECT
                    user_id,
                    token_hash,
                    expires_at,
                    {used_expression}

                FROM password_reset_tokens
                """
            )


# ============================================================
# STEP 32
# LOGIN ATTEMPTS
# ============================================================

def migrate_login_attempts(db):
    print("\n--- LOGIN ATTEMPTS ---")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            email TEXT NOT NULL,

            attempted_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            success INTEGER NOT NULL DEFAULT 0
                CHECK (success IN (0, 1))
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_login_attempts_email_time
        ON login_attempts(
            email,
            attempted_at
        )
        """
    )


# ============================================================
# STEP 34
# STOCK HISTORY
# ============================================================

def migrate_stock_log(db):
    print("\n--- STOCK LOG ---")

    if not table_exists(
        db,
        "stock_log"
    ):
        db.execute(
            """
            CREATE TABLE stock_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                book_id INTEGER NOT NULL,

                change INTEGER NOT NULL,

                reason TEXT NOT NULL
                    CHECK (
                        reason IN (
                            'initial_stock',
                            'purchase',
                            'admin_edit',
                            'cancelled_order'
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

        # Current stock becomes initial baseline.
        db.execute(
            """
            INSERT INTO stock_log
            (
                book_id,
                change,
                reason,
                user_id
            )

            SELECT
                id,
                stock,
                'initial_stock',
                NULL

            FROM books
            """
        )

        print(
            "Created stock_log and initial "
            "stock baselines."
        )

        return

    columns = get_columns(
        db,
        "stock_log"
    )

    # Already new format.
    if {
        "change",
        "reason",
        "user_id",
    }.issubset(columns):
        print(
            "stock_log already uses new format."
        )
        return

    print(
        "Converting old stock_log..."
    )

    db.execute(
        """
        ALTER TABLE stock_log
        RENAME TO stock_log_old
        """
    )

    db.execute(
        """
        CREATE TABLE stock_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            book_id INTEGER NOT NULL,

            change INTEGER NOT NULL,

            reason TEXT NOT NULL
                CHECK (
                    reason IN (
                        'initial_stock',
                        'purchase',
                        'admin_edit',
                        'cancelled_order'
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

    old_columns = get_columns(
        db,
        "stock_log_old"
    )

    if (
        "book_id" in old_columns
        and "change_amount"
        in old_columns
    ):
        user_expression = (
            "user_id"
            if "user_id" in old_columns
            else "NULL"
        )

        created_expression = (
            "created_at"
            if "created_at" in old_columns
            else "CURRENT_TIMESTAMP"
        )

        reason_expression = """
            CASE reason
                WHEN 'initial_stock'
                    THEN 'initial_stock'

                WHEN 'purchase'
                    THEN 'purchase'

                WHEN 'cancellation'
                    THEN 'cancelled_order'

                WHEN 'cancelled_order'
                    THEN 'cancelled_order'

                WHEN 'admin_adjustment'
                    THEN 'admin_edit'

                WHEN 'restock'
                    THEN 'admin_edit'

                WHEN 'admin_edit'
                    THEN 'admin_edit'

                ELSE 'admin_edit'
            END
        """

        db.execute(
            f"""
            INSERT INTO stock_log
            (
                book_id,
                change,
                reason,
                user_id,
                created_at
            )

            SELECT
                book_id,
                change_amount,
                {reason_expression},
                {user_expression},
                {created_expression}

            FROM stock_log_old
            """
        )

    db.execute(
        """
        DROP TABLE stock_log_old
        """
    )

    # --------------------------------------------------------
    # Reconcile history.
    #
    # Requirement:
    #
    # SUM(stock_log.change) == books.stock
    #
    # Add an initial_stock adjustment if old history does
    # not currently reconcile.
    # --------------------------------------------------------

    books = db.execute(
        """
        SELECT id, stock
        FROM books
        """
    ).fetchall()

    for book in books:
        logged = db.execute(
            """
            SELECT
                COALESCE(
                    SUM(change),
                    0
                ) AS total
            FROM stock_log
            WHERE book_id = ?
            """,
            (book["id"],)
        ).fetchone()["total"]

        difference = (
            int(book["stock"])
            - int(logged)
        )

        if difference != 0:
            db.execute(
                """
                INSERT INTO stock_log
                (
                    book_id,
                    change,
                    reason,
                    user_id
                )
                VALUES (?, ?, ?, NULL)
                """,
                (
                    book["id"],
                    difference,
                    "initial_stock"
                )
            )


# ============================================================
# INDEXES
# ============================================================

def create_indexes(db):
    print("\n--- INDEXES ---")

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_order_items_order
        ON order_items(order_id)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_order_items_book
        ON order_items(book_id)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_orders_user
        ON orders(user_id)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_stock_log_book
        ON stock_log(book_id)
        """
    )


# ============================================================
# MIGRATION
# ============================================================

def migrate():
    if not DATABASE.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE}"
        )

    create_backup()

    db = sqlite3.connect(
        str(DATABASE),
        timeout=10
    )

    db.row_factory = sqlite3.Row

    try:
        # Foreign keys must be disabled before
        # rebuilding referenced SQLite tables.
        db.execute(
            "PRAGMA foreign_keys = OFF"
        )

        db.execute(
            "BEGIN IMMEDIATE"
        )

        required_tables = {
            "users",
            "books",
            "orders",
            "order_items",
        }

        existing_tables = {
            row["name"]
            for row in db.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        missing = (
            required_tables
            - existing_tables
        )

        if missing:
            raise RuntimeError(
                "Missing required tables: "
                + ", ".join(
                    sorted(missing)
                )
            )

        migrate_users(db)

        migrate_addresses(db)

        migrate_orders(db)

        migrate_order_items(db)

        migrate_reset_tokens(db)

        migrate_login_attempts(db)

        migrate_stock_log(db)

        create_indexes(db)

        db.commit()

        db.execute(
            "PRAGMA foreign_keys = ON"
        )

        foreign_key_errors = db.execute(
            """
            PRAGMA foreign_key_check
            """
        ).fetchall()

        if foreign_key_errors:
            print(
                "\nWARNING: Foreign key check "
                "reported problems:"
            )

            for row in foreign_key_errors:
                print(
                    tuple(row)
                )

        else:
            print(
                "\nForeign key check: OK"
            )

        print(
            "\n================================"
        )

        print(
            "DATABASE MIGRATION COMPLETED"
        )

        print(
            "================================"
        )

    except Exception:
        db.rollback()

        print(
            "\nMigration failed."
        )

        print(
            "Your backup was not changed."
        )

        raise

    finally:
        db.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    migrate()