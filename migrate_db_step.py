import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATABASE = (
    BASE_DIR
    / "pageturner.db"
)

MIGRATIONS_DIR = (
    BASE_DIR
    / "migrations"
)

MIGRATION_NAME = re.compile(
    r"^(\d{3})_[A-Za-z0-9_-]+\.sql$"
)


# ============================================================
# BACKUP
# ============================================================

def create_backup():

    if not DATABASE.exists():

        raise FileNotFoundError(
            f"Database not found: {DATABASE}"
        )

    timestamp = (
        datetime.now()
        .strftime(
            "%Y%m%d-%H%M%S"
        )
    )

    backup = BASE_DIR / (
        f"pageturner-backup-{timestamp}.db"
    )

    shutil.copy2(
        DATABASE,
        backup
    )

    print()
    print(
        "Backup created:"
    )
    print(
        backup
    )

    return backup


# ============================================================
# GENERAL DATABASE HELPERS
# ============================================================

def table_exists(
    db,
    table_name
):

    row = db.execute(
        """
        SELECT
            name

        FROM sqlite_master

        WHERE type = 'table'
          AND name = ?
        """,
        (
            table_name,
        )
    ).fetchone()

    return row is not None


def column_exists(
    db,
    table_name,
    column_name
):

    rows = db.execute(
        f"""
        PRAGMA table_info(
            {table_name}
        )
        """
    ).fetchall()

    return any(
        row["name"] == column_name
        for row in rows
    )


def index_exists(
    db,
    index_name
):

    row = db.execute(
        """
        SELECT
            name

        FROM sqlite_master

        WHERE type = 'index'
          AND name = ?
        """,
        (
            index_name,
        )
    ).fetchone()

    return row is not None


# ============================================================
# SCHEMA VERSION
# ============================================================

def ensure_schema_version(
    db
):

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,

            filename TEXT NOT NULL
                UNIQUE,

            applied_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    db.commit()


# ============================================================
# STEP 51-56 VERSION TABLE
#
# This is separate from your normal migrations/ SQL history.
# It makes the built-in migration safe to run more than once.
# ============================================================

def ensure_feature_migrations(
    db
):

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS feature_migrations (
            name TEXT PRIMARY KEY,

            applied_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    db.commit()


def feature_migration_applied(
    db,
    name
):

    row = db.execute(
        """
        SELECT
            name

        FROM feature_migrations

        WHERE name = ?
        """,
        (
            name,
        )
    ).fetchone()

    return row is not None


# ============================================================
# DISCOVER NORMAL SQL MIGRATIONS
# ============================================================

def discover_migrations():

    # --------------------------------------------------------
    # migrations/ is optional for the Steps 51-56 migration.
    #
    # If it does not exist, we simply have no normal SQL
    # migrations to run.
    # --------------------------------------------------------

    if not MIGRATIONS_DIR.exists():

        return []

    migrations = []

    seen_versions = set()

    for path in MIGRATIONS_DIR.glob(
        "*.sql"
    ):

        match = (
            MIGRATION_NAME.fullmatch(
                path.name
            )
        )

        if not match:

            raise RuntimeError(
                f"Invalid migration filename: "
                f"{path.name}. "
                f"Use NNN_name.sql, for example "
                f"001_base.sql."
            )

        version = int(
            match.group(1)
        )

        if version in seen_versions:

            raise RuntimeError(
                f"Duplicate migration version: "
                f"{version:03d}"
            )

        seen_versions.add(
            version
        )

        migrations.append(
            (
                version,
                path,
            )
        )

    migrations.sort(
        key=lambda item:
            item[0]
    )

    return migrations


# ============================================================
# GET APPLIED NORMAL MIGRATIONS
# ============================================================

def get_applied_migrations(
    db
):

    rows = db.execute(
        """
        SELECT
            version,
            filename

        FROM schema_version

        ORDER BY
            version
        """
    ).fetchall()

    return {
        int(
            row["version"]
        ):
        row["filename"]

        for row in rows
    }


# ============================================================
# VALIDATE NORMAL MIGRATION HISTORY
# ============================================================

def validate_history(
    migrations,
    applied
):

    available = {
        version:
            path.name

        for (
            version,
            path
        ) in migrations
    }

    for (
        version,
        recorded_filename
    ) in applied.items():

        expected_filename = (
            available.get(
                version
            )
        )

        if expected_filename is None:

            raise RuntimeError(
                f"Applied migration "
                f"{version:03d} is missing "
                f"from migrations/."
            )

        if (
            expected_filename
            != recorded_filename
        ):

            raise RuntimeError(
                f"Migration "
                f"{version:03d} filename changed. "
                f"Database has "
                f"{recorded_filename!r}, "
                f"folder has "
                f"{expected_filename!r}."
            )


# ============================================================
# SQL STRING HELPER
# ============================================================

def sql_literal(
    value
):

    return (
        "'"
        + value.replace(
            "'",
            "''"
        )
        + "'"
    )


# ============================================================
# APPLY ONE NORMAL SQL MIGRATION
# ============================================================

def apply_migration(
    db,
    version,
    path
):

    sql = path.read_text(
        encoding="utf-8"
    )

    if not sql.strip():

        raise RuntimeError(
            f"Migration is empty: "
            f"{path.name}"
        )

    print()
    print(
        f"Applying {path.name} ..."
    )

    script = (
        "BEGIN IMMEDIATE;\n"
        + sql
        + "\n"
        + "INSERT INTO schema_version"
        + "(version, filename) VALUES ("
        + str(version)
        + ", "
        + sql_literal(
            path.name
        )
        + ");\n"
        + "COMMIT;\n"
    )

    try:

        db.executescript(
            script
        )

    except Exception:

        if db.in_transaction:

            db.rollback()

        raise

    print(
        f"Applied {path.name}"
    )


# ============================================================
# STEP 46 / 51-56
# MIGRATE BOOK MONEY
#
# OLD:
#     books.price REAL
#
# NEW:
#     books.price_paise INTEGER
#
# We keep price temporarily for compatibility.
# ============================================================

def migrate_books_money(
    db
):

    print()
    print(
        "Checking books.price_paise ..."
    )

    if not table_exists(
        db,
        "books"
    ):

        raise RuntimeError(
            "books table does not exist."
        )

    if not column_exists(
        db,
        "books",
        "price_paise"
    ):

        db.execute(
            """
            ALTER TABLE books

            ADD COLUMN price_paise INTEGER
                NOT NULL
                DEFAULT 0
                CHECK (
                    price_paise >= 0
                )
            """
        )

        print(
            "Added books.price_paise."
        )

    else:

        print(
            "books.price_paise already exists."
        )

    # --------------------------------------------------------
    # ONE-TIME CONVERSION FROM OLD REAL MONEY
    #
    # ROUND is acceptable here because this is converting
    # legacy REAL data once.
    #
    # New application calculations use integer paise.
    # --------------------------------------------------------

    if column_exists(
        db,
        "books",
        "price"
    ):

        db.execute(
            """
            UPDATE books

            SET price_paise =
                CAST(
                    ROUND(
                        price * 100
                    )
                    AS INTEGER
                )

            WHERE price_paise = 0
              AND price > 0
            """
        )

        print(
            "Converted legacy books.price "
            "to books.price_paise."
        )


# ============================================================
# STEP 46 / 51-56
# MIGRATE ORDER MONEY
# ============================================================

def migrate_orders_money(
    db
):

    print()
    print(
        "Checking order paise columns ..."
    )

    if not table_exists(
        db,
        "orders"
    ):

        raise RuntimeError(
            "orders table does not exist."
        )

    # --------------------------------------------------------
    # TOTAL
    # --------------------------------------------------------

    if not column_exists(
        db,
        "orders",
        "total_paise"
    ):

        db.execute(
            """
            ALTER TABLE orders

            ADD COLUMN total_paise INTEGER
                NOT NULL
                DEFAULT 0
                CHECK (
                    total_paise >= 0
                )
            """
        )

        print(
            "Added orders.total_paise."
        )

    else:

        print(
            "orders.total_paise already exists."
        )

    # --------------------------------------------------------
    # DISCOUNT
    # --------------------------------------------------------

    if not column_exists(
        db,
        "orders",
        "discount_paise"
    ):

        db.execute(
            """
            ALTER TABLE orders

            ADD COLUMN discount_paise INTEGER
                NOT NULL
                DEFAULT 0
                CHECK (
                    discount_paise >= 0
                )
            """
        )

        print(
            "Added orders.discount_paise."
        )

    else:

        print(
            "orders.discount_paise already exists."
        )

    # --------------------------------------------------------
    # CONVERT OLD TOTAL
    # --------------------------------------------------------

    if column_exists(
        db,
        "orders",
        "total_amount"
    ):

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

            WHERE total_paise = 0
              AND total_amount > 0
            """
        )

        print(
            "Converted orders.total_amount "
            "to orders.total_paise."
        )

    # --------------------------------------------------------
    # CONVERT OLD DISCOUNT
    # --------------------------------------------------------

    if column_exists(
        db,
        "orders",
        "discount_amount"
    ):

        db.execute(
            """
            UPDATE orders

            SET discount_paise =
                CAST(
                    ROUND(
                        discount_amount * 100
                    )
                    AS INTEGER
                )

            WHERE discount_paise = 0
              AND discount_amount > 0
            """
        )

        print(
            "Converted orders.discount_amount "
            "to orders.discount_paise."
        )


# ============================================================
# STEP 46 / 51-56
# MIGRATE ORDER ITEM MONEY
# ============================================================

def migrate_order_items_money(
    db
):

    print()
    print(
        "Checking order_items.price_paise ..."
    )

    if not table_exists(
        db,
        "order_items"
    ):

        raise RuntimeError(
            "order_items table does not exist."
        )

    if not column_exists(
        db,
        "order_items",
        "price_paise"
    ):

        db.execute(
            """
            ALTER TABLE order_items

            ADD COLUMN price_paise INTEGER
                NOT NULL
                DEFAULT 0
                CHECK (
                    price_paise >= 0
                )
            """
        )

        print(
            "Added order_items.price_paise."
        )

    else:

        print(
            "order_items.price_paise already exists."
        )

    if column_exists(
        db,
        "order_items",
        "price_at_purchase"
    ):

        db.execute(
            """
            UPDATE order_items

            SET price_paise =
                CAST(
                    ROUND(
                        price_at_purchase * 100
                    )
                    AS INTEGER
                )

            WHERE price_paise = 0
              AND price_at_purchase > 0
            """
        )

        print(
            "Converted order_items.price_at_purchase "
            "to order_items.price_paise."
        )


# ============================================================
# STEP 48
# CATEGORIES + TAGS
# ============================================================

def migrate_categories_and_tags(
    db
):

    print()
    print(
        "Checking categories and tags ..."
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL
                COLLATE NOCASE
                UNIQUE,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
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

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL
                COLLATE NOCASE
                UNIQUE,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
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

    # --------------------------------------------------------
    # MIGRATE OLD books.category VALUES
    # --------------------------------------------------------

    if column_exists(
        db,
        "books",
        "category"
    ):

        db.execute(
            """
            INSERT OR IGNORE INTO categories
            (
                name
            )

            SELECT DISTINCT
                TRIM(category)

            FROM books

            WHERE category IS NOT NULL
              AND TRIM(category) != ''
            """
        )

        db.execute(
            """
            INSERT OR IGNORE INTO book_categories
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

    # --------------------------------------------------------
    # INDEXES
    # --------------------------------------------------------

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
        "Categories and tags ready."
    )


# ============================================================
# STEP 52
# WISHLIST
# ============================================================

def migrate_wishlist(
    db
):

    print()
    print(
        "Checking wishlist ..."
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            book_id INTEGER NOT NULL,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (
                user_id,
                book_id
            ),

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            FOREIGN KEY (book_id)
                REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wishlist_user

        ON wishlist(user_id)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_wishlist_book

        ON wishlist(book_id)
        """
    )

    print(
        "Step 52 wishlist ready."
    )


# ============================================================
# STEP 53
# DATABASE CART
# ============================================================

def migrate_cart_items(
    db
):

    print()
    print(
        "Checking cart_items ..."
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            book_id INTEGER NOT NULL,

            quantity INTEGER NOT NULL
                DEFAULT 1
                CHECK (
                    quantity > 0
                ),

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (
                user_id,
                book_id
            ),

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            FOREIGN KEY (book_id)
                REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_cart_items_user

        ON cart_items(user_id)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_cart_items_book

        ON cart_items(book_id)
        """
    )

    print(
        "Step 53 cart_items ready."
    )


# ============================================================
# STEP 54
# RESERVATIONS
# ============================================================

def migrate_reservations(
    db
):

    print()
    print(
        "Checking reservations ..."
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            book_id INTEGER NOT NULL,

            quantity INTEGER NOT NULL
                CHECK (
                    quantity > 0
                ),

            expires_at TEXT NOT NULL,

            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (
                user_id,
                book_id
            ),

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            FOREIGN KEY (book_id)
                REFERENCES books(id)
                ON DELETE CASCADE
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_reservations_book_expiry

        ON reservations(
            book_id,
            expires_at
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_reservations_user

        ON reservations(user_id)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_reservations_expiry

        ON reservations(expires_at)
        """
    )

    print(
        "Step 54 reservations ready."
    )


# ============================================================
# STEP 55
# REVIEWS
# ============================================================

def migrate_reviews(
    db
):

    print()
    print(
        "Checking Step 55 reviews ..."
    )

    if not table_exists(
        db,
        "reviews"
    ):

        db.execute(
            """
            CREATE TABLE reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                book_id INTEGER NOT NULL,

                user_id INTEGER,

                name TEXT NOT NULL,

                rating INTEGER NOT NULL
                    CHECK (
                        rating BETWEEN 1 AND 5
                    ),

                comment TEXT NOT NULL,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (book_id)
                    REFERENCES books(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE SET NULL
            )
            """
        )

    # --------------------------------------------------------
    # REMOVE DUPLICATE LOGGED-IN REVIEWS
    #
    # Keep the oldest review for each:
    #
    #     user_id + book_id
    #
    # Historical rows with NULL user_id are untouched.
    # --------------------------------------------------------

    db.execute(
        """
        DELETE FROM reviews

        WHERE user_id IS NOT NULL

          AND id NOT IN
          (
              SELECT
                  MIN(id)

              FROM reviews

              WHERE user_id IS NOT NULL

              GROUP BY
                  user_id,
                  book_id
          )
        """
    )

    # --------------------------------------------------------
    # DATABASE PROTECTION:
    # ONE REVIEW PER USER PER BOOK
    # --------------------------------------------------------

    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        uq_reviews_user_book

        ON reviews(
            user_id,
            book_id
        )

        WHERE user_id IS NOT NULL
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_reviews_book_created

        ON reviews(
            book_id,
            created_at
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_reviews_user

        ON reviews(user_id)
        """
    )

    print(
        "Step 55 reviews ready."
    )


# ============================================================
# STEP 56
# PROFILE INDEXES
# ============================================================

def migrate_profile_indexes(
    db
):

    print()
    print(
        "Checking Step 56 profile indexes ..."
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_orders_user_created

        ON orders(
            user_id,
            created_at
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_order_items_order_book

        ON order_items(
            order_id,
            book_id
        )
        """
    )

    print(
        "Step 56 profile indexes ready."
    )


# ============================================================
# EXTRA LOOKUP INDEXES
# ============================================================

def create_lookup_indexes(
    db
):

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


# ============================================================
# VERIFY MONEY CONVERSION
# ============================================================

def verify_money_conversion(
    db
):

    print()
    print(
        "Verifying integer-paise data ..."
    )

    # --------------------------------------------------------
    # NEGATIVE VALUES MUST NEVER EXIST
    # --------------------------------------------------------

    bad_books = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM books

        WHERE price_paise < 0
        """
    ).fetchone()

    if int(
        bad_books["total"]
        or 0
    ) > 0:

        raise RuntimeError(
            "Negative books.price_paise "
            "values found."
        )

    bad_orders = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM orders

        WHERE total_paise < 0
           OR discount_paise < 0
        """
    ).fetchone()

    if int(
        bad_orders["total"]
        or 0
    ) > 0:

        raise RuntimeError(
            "Negative order paise values found."
        )

    bad_items = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM order_items

        WHERE price_paise < 0
        """
    ).fetchone()

    if int(
        bad_items["total"]
        or 0
    ) > 0:

        raise RuntimeError(
            "Negative order-item paise "
            "values found."
        )

    # --------------------------------------------------------
    # VERIFY LEGACY -> PAISE CONVERSION
    # --------------------------------------------------------

    if column_exists(
        db,
        "books",
        "price"
    ):

        mismatch = db.execute(
            """
            SELECT
                COUNT(*) AS total

            FROM books

            WHERE price > 0

              AND price_paise !=
                  CAST(
                      ROUND(
                          price * 100
                      )
                      AS INTEGER
                  )
            """
        ).fetchone()

        if int(
            mismatch["total"]
            or 0
        ) > 0:

            raise RuntimeError(
                "Some book prices were not "
                "converted correctly."
            )

    if column_exists(
        db,
        "orders",
        "total_amount"
    ):

        mismatch = db.execute(
            """
            SELECT
                COUNT(*) AS total

            FROM orders

            WHERE total_amount > 0

              AND total_paise !=
                  CAST(
                      ROUND(
                          total_amount * 100
                      )
                      AS INTEGER
                  )
            """
        ).fetchone()

        if int(
            mismatch["total"]
            or 0
        ) > 0:

            raise RuntimeError(
                "Some order totals were not "
                "converted correctly."
            )

    if column_exists(
        db,
        "order_items",
        "price_at_purchase"
    ):

        mismatch = db.execute(
            """
            SELECT
                COUNT(*) AS total

            FROM order_items

            WHERE price_at_purchase > 0

              AND price_paise !=
                  CAST(
                      ROUND(
                          price_at_purchase * 100
                      )
                      AS INTEGER
                  )
            """
        ).fetchone()

        if int(
            mismatch["total"]
            or 0
        ) > 0:

            raise RuntimeError(
                "Some order item prices were not "
                "converted correctly."
            )

    print(
        "Integer-paise verification: OK"
    )


# ============================================================
# RUN BUILT-IN STEPS 51-56 MIGRATION
# ============================================================

def migrate_steps_51_56(
    db
):

    migration_name = (
        "steps_51_56"
    )

    if feature_migration_applied(
        db,
        migration_name
    ):

        print()
        print(
            "Steps 51-56 migration "
            "already applied."
        )

        return False

    print()
    print(
        "========================================"
    )
    print(
        "APPLYING STEPS 51-56 DATABASE MIGRATION"
    )
    print(
        "========================================"
    )

    try:

        db.execute(
            "BEGIN IMMEDIATE"
        )

        migrate_books_money(
            db
        )

        migrate_orders_money(
            db
        )

        migrate_order_items_money(
            db
        )

        migrate_categories_and_tags(
            db
        )

        migrate_wishlist(
            db
        )

        migrate_cart_items(
            db
        )

        migrate_reservations(
            db
        )

        migrate_reviews(
            db
        )

        migrate_profile_indexes(
            db
        )

        create_lookup_indexes(
            db
        )

        verify_money_conversion(
            db
        )

        # ----------------------------------------------------
        # RECORD SUCCESS IN SAME TRANSACTION
        # ----------------------------------------------------

        db.execute(
            """
            INSERT INTO feature_migrations
            (
                name
            )

            VALUES (?)
            """,
            (
                migration_name,
            )
        )

        db.commit()

    except Exception:

        if db.in_transaction:

            db.rollback()

        raise

    print()
    print(
        "Steps 51-56 migration: OK"
    )

    return True


# ============================================================
# FOREIGN KEY VALIDATION
# ============================================================

def validate_foreign_keys(
    db
):

    errors = db.execute(
        """
        PRAGMA foreign_key_check
        """
    ).fetchall()

    if errors:

        details = [
            tuple(row)
            for row in errors
        ]

        raise RuntimeError(
            "Foreign key check failed: "
            + repr(details)
        )

    print()
    print(
        "Foreign key check: OK"
    )


# ============================================================
# SHOW RESULT
# ============================================================

def show_database_status(
    db
):

    print()
    print(
        "========================================"
    )
    print(
        "DATABASE STATUS"
    )
    print(
        "========================================"
    )

    # --------------------------------------------------------
    # BOOKS
    # --------------------------------------------------------

    book_count = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM books
        """
    ).fetchone()

    print(
        "Books:",
        int(
            book_count["total"]
            or 0
        )
    )

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    user_count = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM users
        """
    ).fetchone()

    print(
        "Users:",
        int(
            user_count["total"]
            or 0
        )
    )

    # --------------------------------------------------------
    # ORDERS
    # --------------------------------------------------------

    order_count = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM orders
        """
    ).fetchone()

    print(
        "Orders:",
        int(
            order_count["total"]
            or 0
        )
    )

    # --------------------------------------------------------
    # WISHLIST
    # --------------------------------------------------------

    wishlist_count = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM wishlist
        """
    ).fetchone()

    print(
        "Wishlist rows:",
        int(
            wishlist_count["total"]
            or 0
        )
    )

    # --------------------------------------------------------
    # CART
    # --------------------------------------------------------

    cart_count = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM cart_items
        """
    ).fetchone()

    print(
        "Cart rows:",
        int(
            cart_count["total"]
            or 0
        )
    )

    # --------------------------------------------------------
    # RESERVATIONS
    # --------------------------------------------------------

    reservation_count = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM reservations
        """
    ).fetchone()

    print(
        "Reservation rows:",
        int(
            reservation_count["total"]
            or 0
        )
    )


# ============================================================
# MAIN MIGRATION RUNNER
# ============================================================

def migrate():

    # --------------------------------------------------------
    # DATABASE MUST EXIST
    # --------------------------------------------------------

    if not DATABASE.exists():

        raise FileNotFoundError(
            f"Database not found: "
            f"{DATABASE}"
        )

    # --------------------------------------------------------
    # CONNECT
    # --------------------------------------------------------

    db = sqlite3.connect(
        str(
            DATABASE
        ),
        timeout=10
    )

    db.row_factory = (
        sqlite3.Row
    )

    backup = None

    try:

        # ----------------------------------------------------
        # SQLITE SETTINGS
        # ----------------------------------------------------

        db.execute(
            "PRAGMA foreign_keys = ON"
        )

        db.execute(
            "PRAGMA busy_timeout = 10000"
        )

        # ----------------------------------------------------
        # VERSION TABLES
        # ----------------------------------------------------

        ensure_schema_version(
            db
        )

        ensure_feature_migrations(
            db
        )

        # ----------------------------------------------------
        # NORMAL SQL MIGRATIONS
        # ----------------------------------------------------

        migrations = (
            discover_migrations()
        )

        applied = (
            get_applied_migrations(
                db
            )
        )

        if migrations:

            validate_history(
                migrations,
                applied
            )

        elif applied:

            # ------------------------------------------------
            # Existing database has normal migration history
            # but migrations/ is missing.
            #
            # Do not pretend that history is valid.
            # ------------------------------------------------

            raise RuntimeError(
                "The database contains migration "
                "history, but the migrations folder "
                "is missing or contains no SQL files."
            )

        pending = [
            (
                version,
                path,
            )

            for (
                version,
                path
            ) in migrations

            if version not in applied
        ]

        feature_pending = (
            not feature_migration_applied(
                db,
                "steps_51_56"
            )
        )

        # ----------------------------------------------------
        # NOTHING TO DO
        # ----------------------------------------------------

        if (
            not pending
            and
            not feature_pending
        ):

            print()
            print(
                "No pending migrations."
            )

            print(
                "Database is up to date."
            )

            validate_foreign_keys(
                db
            )

            show_database_status(
                db
            )

            return

        # ----------------------------------------------------
        # SHOW WHAT WILL RUN
        # ----------------------------------------------------

        print()
        print(
            "Pending migrations:"
        )

        if pending:

            for (
                _,
                path
            ) in pending:

                print(
                    f"  - {path.name}"
                )

        if feature_pending:

            print(
                "  - built-in steps_51_56"
            )

        # ----------------------------------------------------
        # ONE BACKUP BEFORE ANY DATABASE CHANGES
        # ----------------------------------------------------

        backup = (
            create_backup()
        )

        # ----------------------------------------------------
        # NORMAL SQL MIGRATIONS FIRST
        # ----------------------------------------------------

        for (
            version,
            path
        ) in pending:

            apply_migration(
                db,
                version,
                path
            )

        # ----------------------------------------------------
        # STEPS 51-56
        # ----------------------------------------------------

        if feature_pending:

            migrate_steps_51_56(
                db
            )

        # ----------------------------------------------------
        # FINAL FOREIGN KEY CHECK
        # ----------------------------------------------------

        validate_foreign_keys(
            db
        )

        # ----------------------------------------------------
        # SHOW FINAL STATUS
        # ----------------------------------------------------

        show_database_status(
            db
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        print()
        print(
            "========================================"
        )
        print(
            "DATABASE MIGRATIONS COMPLETED"
        )
        print(
            "========================================"
        )

        if backup is not None:

            print()
            print(
                "Backup:"
            )
            print(
                backup
            )

        print()
        print(
            "Steps 51-56 database changes "
            "are ready."
        )

    except Exception:

        if db.in_transaction:

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

        print()
        print(
            "The active transaction was "
            "rolled back."
        )

        if backup is not None:

            print()
            print(
                "Backup remains available:"
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
