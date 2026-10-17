import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "pageturner.db"


# ============================================================
# DATABASE HELPERS
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
        return False

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

    return True


# ============================================================
# BACKUP
# ============================================================

def create_backup():
    if not DATABASE.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE}"
        )

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
        "\nBackup created:"
    )

    print(
        backup
    )

    return backup


# ============================================================
# USERS
# STEP 30
# ============================================================

def migrate_users(db):
    print(
        "\n--- USERS ---"
    )

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
    print(
        "\n--- ADDRESSES ---"
    )

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

            if table_exists(
                db,
                "addresses_old"
            ):
                db.execute(
                    """
                    DROP TABLE addresses_old
                    """
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

            if {
                "user_id",
                "address_line1",
                "city",
                "postal_code",
            }.issubset(
                old_columns
            ):
                if (
                    "is_default"
                    in old_columns
                ):
                    default_expression = (
                        "COALESCE(is_default, 0)"
                    )

                else:
                    default_expression = "0"

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
    # Ensure one default address per user.
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
            SELECT
                id,
                is_default
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
    print(
        "\n--- ORDERS ---"
    )

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

        if "address" in columns:
            db.execute(
                """
                UPDATE orders
                SET address_snapshot = address
                WHERE address_snapshot IS NULL
                   OR address_snapshot = ''
                """
            )

            print(
                "Copied old order addresses "
                "to address_snapshot."
            )

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

        if table_exists(
            db,
            "orders_old"
        ):
            raise RuntimeError(
                "orders_old already exists."
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

        if (
            "address_snapshot"
            in old_columns
        ):
            address_expression = (
                "address_snapshot"
            )

        elif "address" in old_columns:
            address_expression = "address"

        else:
            address_expression = "''"

        if "phone" in old_columns:
            phone_expression = "phone"

        else:
            phone_expression = "''"

        if (
            "discount_amount"
            in old_columns
        ):
            discount_expression = (
                "discount_amount"
            )

        else:
            discount_expression = "0"

        if "coupon_code" in old_columns:
            coupon_expression = (
                "coupon_code"
            )

        else:
            coupon_expression = "NULL"

        if "created_at" in old_columns:
            created_expression = (
                "created_at"
            )

        else:
            created_expression = (
                "CURRENT_TIMESTAMP"
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


# ============================================================
# ORDER ITEMS
# STEP 29
# ============================================================

def migrate_order_items(db):
    print(
        "\n--- ORDER ITEMS ---"
    )

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

        if table_exists(
            db,
            "order_items_old"
        ):
            db.execute(
                """
                DROP TABLE order_items_old
                """
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
            "'price' nor "
            "'price_at_purchase'."
        )

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
    print(
        "\n--- RESET TOKENS ---"
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            token_hash TEXT NOT NULL UNIQUE,

            expires_at TEXT NOT NULL,

            used INTEGER NOT NULL DEFAULT 0
                CHECK (
                    used IN (0, 1)
                ),

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )

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
        }.issubset(
            old_columns
        ):
            if "used_at" in old_columns:
                used_expression = """
                    CASE
                        WHEN used_at IS NULL
                        THEN 0
                        ELSE 1
                    END
                """

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
    print(
        "\n--- LOGIN ATTEMPTS ---"
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            email TEXT NOT NULL,

            attempted_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            success INTEGER NOT NULL DEFAULT 0
                CHECK (
                    success IN (0, 1)
                )
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
    print(
        "\n--- STOCK LOG ---"
    )

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
            "Created stock_log and "
            "initial stock baselines."
        )

        return

    columns = get_columns(
        db,
        "stock_log"
    )

    if {
        "change",
        "reason",
        "user_id",
    }.issubset(
        columns
    ):
        print(
            "stock_log already uses "
            "new format."
        )

        return

    print(
        "Converting old stock_log..."
    )

    if table_exists(
        db,
        "stock_log_old"
    ):
        db.execute(
            """
            DROP TABLE stock_log_old
            """
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
        if "user_id" in old_columns:
            user_expression = "user_id"

        else:
            user_expression = "NULL"

        if "created_at" in old_columns:
            created_expression = (
                "created_at"
            )

        else:
            created_expression = (
                "CURRENT_TIMESTAMP"
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

    books = db.execute(
        """
        SELECT
            id,
            stock
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
# STEP 46
# INTEGER MONEY / PAISE
# ============================================================

def migrate_money_to_paise(db):
    print(
        "\n--- STEP 46: MONEY TO PAISE ---"
    )

    # --------------------------------------------------------
    # BOOKS
    # --------------------------------------------------------

    columns = get_columns(
        db,
        "books"
    )

    if "price_paise" not in columns:
        db.execute(
            """
            ALTER TABLE books
            ADD COLUMN price_paise
            INTEGER NOT NULL DEFAULT 0
            """
        )

        if "price" in columns:
            db.execute(
                """
                UPDATE books
                SET price_paise =
                    CAST(
                        ROUND(price * 100)
                        AS INTEGER
                    )
                """
            )

        print(
            "Added books.price_paise."
        )

    else:
        print(
            "books.price_paise "
            "already exists."
        )

    # --------------------------------------------------------
    # ORDERS
    # --------------------------------------------------------

    columns = get_columns(
        db,
        "orders"
    )

    if "total_paise" not in columns:
        db.execute(
            """
            ALTER TABLE orders
            ADD COLUMN total_paise
            INTEGER NOT NULL DEFAULT 0
            """
        )

        if "total_amount" in columns:
            db.execute(
                """
                UPDATE orders
                SET total_paise =
                    CAST(
                        ROUND(
                            total_amount * 100
                        )
                        AS INTEGER
                    )
                """
            )

        print(
            "Added orders.total_paise."
        )

    else:
        print(
            "orders.total_paise "
            "already exists."
        )

    columns = get_columns(
        db,
        "orders"
    )

    if "discount_paise" not in columns:
        db.execute(
            """
            ALTER TABLE orders
            ADD COLUMN discount_paise
            INTEGER NOT NULL DEFAULT 0
            """
        )

        if (
            "discount_amount"
            in columns
        ):
            db.execute(
                """
                UPDATE orders
                SET discount_paise =
                    CAST(
                        ROUND(
                            discount_amount
                            * 100
                        )
                        AS INTEGER
                    )
                """
            )

        print(
            "Added orders.discount_paise."
        )

    else:
        print(
            "orders.discount_paise "
            "already exists."
        )

    # --------------------------------------------------------
    # ORDER ITEMS
    # --------------------------------------------------------

    columns = get_columns(
        db,
        "order_items"
    )

    if (
        "price_at_purchase_paise"
        not in columns
    ):
        db.execute(
            """
            ALTER TABLE order_items
            ADD COLUMN
                price_at_purchase_paise
                INTEGER NOT NULL DEFAULT 0
            """
        )

        if (
            "price_at_purchase"
            in columns
        ):
            db.execute(
                """
                UPDATE order_items
                SET
                    price_at_purchase_paise =
                    CAST(
                        ROUND(
                            price_at_purchase
                            * 100
                        )
                        AS INTEGER
                    )
                """
            )

        print(
            "Added order_items."
            "price_at_purchase_paise."
        )

    else:
        print(
            "order_items."
            "price_at_purchase_paise "
            "already exists."
        )

    # --------------------------------------------------------
    # COUPONS
    #
    # Coupon percentage is intentionally NOT money.
    # Keep percent as a numeric percentage.
    # --------------------------------------------------------

    print(
        "Money converted to integer paise."
    )


# ============================================================
# STEP 48
# MANY CATEGORIES PER BOOK
# ============================================================

def migrate_categories(db):
    print(
        "\n--- STEP 48: CATEGORIES ---"
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER
                PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL
                COLLATE NOCASE
                UNIQUE
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS book_categories (
            book_id INTEGER NOT NULL,

            category_id INTEGER NOT NULL,

            PRIMARY KEY (
                book_id,
                category_id
            ),

            FOREIGN KEY (book_id)
                REFERENCES books(id)
                ON DELETE CASCADE,

            FOREIGN KEY (category_id)
                REFERENCES categories(id)
                ON DELETE CASCADE
        )
        """
    )

    columns = get_columns(
        db,
        "books"
    )

    # --------------------------------------------------------
    # MOVE OLD books.category DATA AUTOMATICALLY
    # --------------------------------------------------------

    if "category" in columns:
        old_categories = db.execute(
            """
            SELECT DISTINCT
                TRIM(category) AS name

            FROM books

            WHERE category IS NOT NULL
              AND TRIM(category) != ''
            """
        ).fetchall()

        for row in old_categories:
            db.execute(
                """
                INSERT OR IGNORE
                INTO categories(name)
                VALUES (?)
                """,
                (
                    row["name"],
                )
            )

        db.execute(
            """
            INSERT OR IGNORE
            INTO book_categories
            (
                book_id,
                category_id
            )

            SELECT
                b.id,
                c.id

            FROM books AS b

            JOIN categories AS c
                ON c.name =
                   TRIM(b.category)
                   COLLATE NOCASE

            WHERE b.category IS NOT NULL
              AND TRIM(b.category) != ''
            """
        )

        print(
            "Copied books.category "
            "into categories and "
            "book_categories."
        )

    else:
        print(
            "Old books.category column "
            "does not exist."
        )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_book_categories_book
        ON book_categories(book_id)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_book_categories_category
        ON book_categories(category_id)
        """
    )


# ============================================================
# STEP 48
# TAGS
# ============================================================

def migrate_tags(db):
    print(
        "\n--- STEP 48: TAGS ---"
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER
                PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL
                COLLATE NOCASE
                UNIQUE
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS book_tags (
            book_id INTEGER NOT NULL,

            tag_id INTEGER NOT NULL,

            PRIMARY KEY (
                book_id,
                tag_id
            ),

            FOREIGN KEY (book_id)
                REFERENCES books(id)
                ON DELETE CASCADE,

            FOREIGN KEY (tag_id)
                REFERENCES tags(id)
                ON DELETE CASCADE
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_book_tags_book
        ON book_tags(book_id)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_book_tags_tag
        ON book_tags(tag_id)
        """
    )

    print(
        "Tags tables ready."
    )


# ============================================================
# STEP 47
# SCHEMA VERSION TABLE
# ============================================================

def migrate_schema_version(db):
    print(
        "\n--- STEP 47: SCHEMA VERSION ---"
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,

            filename TEXT NOT NULL UNIQUE,

            applied_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    print(
        "schema_version table ready."
    )


# ============================================================
# INDEXES
# ============================================================

def create_indexes(db):
    print(
        "\n--- INDEXES ---"
    )

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

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_books_title
        ON books(title)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_books_author
        ON books(author)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_books_price_paise
        ON books(price_paise)
        """
    )


# ============================================================
# VALIDATION
# ============================================================

def validate_money(db):
    print(
        "\n--- VALIDATE MONEY ---"
    )

    invalid_books = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM books
        WHERE price_paise < 0
           OR typeof(price_paise) != 'integer'
        """
    ).fetchone()["count"]

    invalid_orders = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE total_paise < 0
           OR discount_paise < 0
           OR typeof(total_paise) != 'integer'
           OR typeof(discount_paise) != 'integer'
        """
    ).fetchone()["count"]

    invalid_items = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM order_items
        WHERE price_at_purchase_paise < 0
           OR typeof(
                price_at_purchase_paise
              ) != 'integer'
        """
    ).fetchone()["count"]

    if (
        invalid_books
        or invalid_orders
        or invalid_items
    ):
        raise RuntimeError(
            "Money validation failed."
        )

    print(
        "Money validation: OK"
    )


def validate_categories(db):
    print(
        "\n--- VALIDATE CATEGORIES ---"
    )

    columns = get_columns(
        db,
        "books"
    )

    if "category" not in columns:
        print(
            "No legacy category column "
            "to validate."
        )

        return

    missing = db.execute(
        """
        SELECT COUNT(*) AS count

        FROM books AS b

        WHERE b.category IS NOT NULL
          AND TRIM(b.category) != ''

          AND NOT EXISTS (
              SELECT 1

              FROM book_categories AS bc

              JOIN categories AS c
                  ON c.id =
                     bc.category_id

              WHERE bc.book_id = b.id

                AND c.name =
                    TRIM(b.category)
                    COLLATE NOCASE
          )
        """
    ).fetchone()["count"]

    if missing:
        raise RuntimeError(
            f"{missing} books lost their "
            "old category mapping."
        )

    print(
        "Category migration validation: OK"
    )


def validate_stock(db):
    print(
        "\n--- VALIDATE STOCK ---"
    )

    mismatches = db.execute(
        """
        SELECT
            b.id,
            b.title,
            b.stock,

            COALESCE(
                SUM(sl.change),
                0
            ) AS logged_stock

        FROM books AS b

        LEFT JOIN stock_log AS sl
            ON sl.book_id = b.id

        GROUP BY
            b.id,
            b.title,
            b.stock

        HAVING
            b.stock !=
            COALESCE(
                SUM(sl.change),
                0
            )
        """
    ).fetchall()

    if mismatches:
        raise RuntimeError(
            "Stock log does not match "
            "current book stock."
        )

    print(
        "Stock validation: OK"
    )


# ============================================================
# MIGRATION
# ============================================================

def migrate():
    if not DATABASE.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE}"
        )

    backup = create_backup()

    db = sqlite3.connect(
        str(DATABASE),
        timeout=10
    )

    db.row_factory = sqlite3.Row

    try:
        # ----------------------------------------------------
        # Disable FK enforcement temporarily because some of
        # the old migrations rebuild referenced tables.
        # ----------------------------------------------------

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

        # ====================================================
        # EXISTING PROJECT MIGRATIONS
        # ====================================================

        migrate_users(
            db
        )

        migrate_addresses(
            db
        )

        migrate_orders(
            db
        )

        migrate_order_items(
            db
        )

        migrate_reset_tokens(
            db
        )

        migrate_login_attempts(
            db
        )

        migrate_stock_log(
            db
        )

        # ====================================================
        # STEP 46
        # INTEGER PAISE
        # ====================================================

        migrate_money_to_paise(
            db
        )

        # ====================================================
        # STEP 47
        # VERSION TRACKING TABLE
        # ====================================================

        migrate_schema_version(
            db
        )

        # ====================================================
        # STEP 48
        # MANY CATEGORIES + TAGS
        # ====================================================

        migrate_categories(
            db
        )

        migrate_tags(
            db
        )

        # ====================================================
        # INDEXES
        # ====================================================

        create_indexes(
            db
        )

        # ====================================================
        # VALIDATION BEFORE COMMIT
        # ====================================================

        validate_money(
            db
        )

        validate_categories(
            db
        )

        validate_stock(
            db
        )

        # ====================================================
        # COMMIT EVERYTHING
        # ====================================================

        db.commit()

        # ----------------------------------------------------
        # Turn foreign keys back on after transaction.
        # ----------------------------------------------------

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
                "\nWARNING:"
            )

            print(
                "Foreign key check "
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

        print(
            "\nBackup:"
        )

        print(
            backup
        )

        print(
            "\nNew money columns:"
        )

        print(
            "books.price_paise"
        )

        print(
            "orders.total_paise"
        )

        print(
            "orders.discount_paise"
        )

        print(
            "order_items."
            "price_at_purchase_paise"
        )

        print(
            "\nNew category tables:"
        )

        print(
            "categories"
        )

        print(
            "book_categories"
        )

        print(
            "\nNew tag tables:"
        )

        print(
            "tags"
        )

        print(
            "book_tags"
        )

    except Exception:
        db.rollback()

        print(
            "\n================================"
        )

        print(
            "MIGRATION FAILED"
        )

        print(
            "================================"
        )

        print(
            "\nDatabase transaction "
            "was rolled back."
        )

        print(
            "\nBackup remains available:"
        )

        print(
            backup
        )

        raise

    finally:
        db.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    migrate()