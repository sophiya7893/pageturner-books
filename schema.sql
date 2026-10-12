PRAGMA foreign_keys = ON;


-- ============================================================
-- BOOKS
-- ============================================================

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,
    author TEXT NOT NULL,
    category TEXT NOT NULL,

    price REAL NOT NULL
        CHECK (price >= 0),

    stock INTEGER NOT NULL DEFAULT 0
        CHECK (stock >= 0),

    description TEXT,

    cover_image TEXT,

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- USERS
-- Step 30
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    email TEXT NOT NULL
        COLLATE NOCASE
        UNIQUE,

    password_hash TEXT NOT NULL,

    role TEXT NOT NULL
        DEFAULT 'customer'
        CHECK (
            role IN (
                'customer',
                'staff',
                'admin'
            )
        ),

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- ADDRESSES
-- Step 28
-- ============================================================

CREATE TABLE IF NOT EXISTS addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    label TEXT NOT NULL,

    line1 TEXT NOT NULL,

    city TEXT NOT NULL,

    pincode TEXT NOT NULL,

    is_default INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            is_default IN (0, 1)
        ),

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);


CREATE UNIQUE INDEX IF NOT EXISTS
one_default_address_per_user
ON addresses(user_id)
WHERE is_default = 1;


-- ============================================================
-- ORDERS
-- Steps 28, 29, 35
-- ============================================================

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    customer_name TEXT NOT NULL,

    email TEXT NOT NULL,

    phone TEXT,

    address_snapshot TEXT NOT NULL,

    total_amount REAL NOT NULL
        DEFAULT 0,

    discount_amount REAL NOT NULL
        DEFAULT 0,

    coupon_code TEXT,

    status TEXT NOT NULL
        DEFAULT 'Placed'
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
);


-- ============================================================
-- ORDER ITEMS
-- Step 29
-- ============================================================

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    order_id INTEGER NOT NULL,

    book_id INTEGER NOT NULL,

    quantity INTEGER NOT NULL
        CHECK (quantity > 0),

    price_at_purchase REAL NOT NULL
        CHECK (price_at_purchase >= 0),

    FOREIGN KEY (order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE,

    FOREIGN KEY (book_id)
        REFERENCES books(id)
);


-- ============================================================
-- REVIEWS
-- ============================================================

CREATE TABLE IF NOT EXISTS reviews (
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
);


-- ============================================================
-- WISHLIST
-- ============================================================

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
);


-- ============================================================
-- COUPONS
-- ============================================================

CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    code TEXT NOT NULL
        COLLATE NOCASE
        UNIQUE,

    percent REAL NOT NULL
        CHECK (
            percent >= 0
            AND percent <= 100
        ),

    expiry_date TEXT,

    active INTEGER NOT NULL
        DEFAULT 1
        CHECK (
            active IN (0, 1)
        )
);


-- ============================================================
-- RESET TOKENS
-- Step 31
--
-- Store HASH only.
-- Never store readable raw reset token.
-- ============================================================

CREATE TABLE IF NOT EXISTS reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    token_hash TEXT NOT NULL
        UNIQUE,

    expires_at TEXT NOT NULL,

    used INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            used IN (0, 1)
        ),

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);


-- ============================================================
-- LOGIN ATTEMPTS
-- Step 32
-- ============================================================

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    email TEXT NOT NULL
        COLLATE NOCASE,

    attempted_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    success INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            success IN (0, 1)
        )
);


-- ============================================================
-- STOCK LOG
-- Step 34
-- ============================================================

CREATE TABLE IF NOT EXISTS stock_log (
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
);


-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS
idx_addresses_user
ON addresses(user_id);


CREATE INDEX IF NOT EXISTS
idx_orders_user
ON orders(user_id);


CREATE INDEX IF NOT EXISTS
idx_order_items_order
ON order_items(order_id);


CREATE INDEX IF NOT EXISTS
idx_order_items_book
ON order_items(book_id);


CREATE INDEX IF NOT EXISTS
idx_reset_tokens_hash
ON reset_tokens(token_hash);


CREATE INDEX IF NOT EXISTS
idx_login_attempts_email_time
ON login_attempts(
    email,
    attempted_at
);


CREATE INDEX IF NOT EXISTS
idx_stock_log_book
ON stock_log(book_id);