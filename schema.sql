
PRAGMA foreign_keys = ON;


-- ============================================================
-- PAGE TURNER BOOKS
-- FULL DATABASE SCHEMA
--
-- STEPS 1 - 56
--
-- IMPORTANT:
-- All money values use INTEGER PAISE.
--
-- Examples:
-- ₹199.00 = 19900
-- ₹499.50 = 49950
--
-- Do NOT use REAL / FLOAT for new money columns.
-- ============================================================



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
-- BOOKS
-- Step 46
--
-- Money is INTEGER PAISE.
-- ============================================================

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,

    author TEXT NOT NULL,

    -- Legacy/simple category text can remain useful
    -- for compatibility with older PageTurner code.
    category TEXT NOT NULL
        DEFAULT '',

    price_paise INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            price_paise >= 0
        ),

    stock INTEGER NOT NULL
        DEFAULT 0
        CHECK (
            stock >= 0
        ),

    description TEXT,

    cover_image TEXT,

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);



-- ============================================================
-- CATEGORIES
-- Step 48
-- ============================================================

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL
        COLLATE NOCASE
        UNIQUE,

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);



-- ============================================================
-- BOOK CATEGORIES
-- Step 48
--
-- A book may belong to multiple categories.
-- ============================================================

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
);



-- ============================================================
-- TAGS
-- Step 48
-- ============================================================

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL
        COLLATE NOCASE
        UNIQUE,

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);



-- ============================================================
-- BOOK TAGS
-- Step 48
-- ============================================================

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
);



-- ============================================================
-- ADDRESSES
-- Step 28
--
-- A customer can have multiple addresses.
-- Exactly one address can be default.
-- ============================================================
-- ============================================================
-- ADDRESSES
-- Step 28
--
-- A customer can have multiple addresses.
-- Exactly one address can be default.
-- Phone is stored with each delivery address.
-- ============================================================
CREATE TABLE IF NOT EXISTS addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    label TEXT NOT NULL,

    line1 TEXT NOT NULL,

    city TEXT NOT NULL,

    pincode TEXT NOT NULL,

    phone TEXT,

    is_default INTEGER NOT NULL
        DEFAULT 0
        CHECK (is_default IN (0, 1)),

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);
-- Orders table: all new monetary fields are integer paise.
CREATE TABLE IF NOT EXISTS orders (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, customer_name TEXT, email TEXT, phone TEXT, address_snapshot TEXT,
 subtotal_paise INTEGER NOT NULL DEFAULT 0, discount_paise INTEGER NOT NULL DEFAULT 0, shipping_paise INTEGER NOT NULL DEFAULT 0, tax_paise INTEGER NOT NULL DEFAULT 0, total_paise INTEGER NOT NULL DEFAULT 0,
 coupon_code TEXT, status TEXT NOT NULL DEFAULT 'Placed', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- ORDERS
-- Steps 28, 29, 35, 46
--
-- IMPORTANT:
-- address_snapshot stores a COPY of the address.
--
-- If the customer later edits their saved address,
-- old orders remain unchanged.
--
-- Money uses INTEGER PAISE.
-- ============================================================

CREATE TABLE IF NOT EXISTS order_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

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
);



-- ============================================================
-- ORDER ITEMS
-- Steps 29 + 46
--
-- price_paise is copied at purchase time.
--
-- Future changes to books.price_paise therefore do not
-- change old orders.
-- ============================================================

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    order_id INTEGER NOT NULL,

    book_id INTEGER NOT NULL,

    quantity INTEGER NOT NULL
        CHECK (
            quantity > 0
        ),

    price_paise INTEGER NOT NULL
        CHECK (
            price_paise >= 0
        ),

    FOREIGN KEY (order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE,

    FOREIGN KEY (book_id)
        REFERENCES books(id)
);



-- ============================================================
-- REVIEWS
-- Step 55
--
-- Only one review per user per book.
--
-- Application code must ALSO verify that the customer
-- actually purchased the book.
-- ============================================================

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    book_id INTEGER NOT NULL,

    user_id INTEGER,

    -- Kept for compatibility / historical display.
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


-- ------------------------------------------------------------
-- STEP 55
-- One logged-in customer can review a book only once.
--
-- Partial index permits historical reviews where user_id
-- may be NULL.
-- ------------------------------------------------------------

CREATE UNIQUE INDEX IF NOT EXISTS
uq_reviews_user_book
ON reviews(
    user_id,
    book_id
)
WHERE user_id IS NOT NULL;



-- ============================================================
-- WISHLIST
-- Step 52
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
-- DATABASE CART
-- Step 53
--
-- Logged-in users use this table.
-- Guests continue using Flask session.
-- ============================================================

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
);



-- ============================================================
-- TEMPORARY STOCK RESERVATIONS
-- Step 54
--
-- Opening checkout reserves cart stock for ten minutes.
--
-- Expired reservations do not need to be deleted
-- immediately. Application queries ignore rows whose
-- expires_at is in the past.
-- ============================================================

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
);



-- ============================================================
-- COUPONS
-- Existing coupon support
--
-- Advanced coupon fields for Steps 59/60 can be added
-- later through migrations.
-- ============================================================

CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    code TEXT NOT NULL
        COLLATE NOCASE
        UNIQUE,

    percent INTEGER NOT NULL
        CHECK (
            percent >= 0
            AND percent <= 100
        ),

    expiry_date TEXT,

    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    discount_type TEXT NOT NULL DEFAULT 'percentage',
    discount_value INTEGER NOT NULL DEFAULT 0,
    min_order_paise INTEGER NOT NULL DEFAULT 0 CHECK (min_order_paise >= 0),
    max_discount_paise INTEGER CHECK (max_discount_paise IS NULL OR max_discount_paise >= 0),
    start_date TEXT,
    end_date TEXT,
    usage_limit INTEGER CHECK (usage_limit IS NULL OR usage_limit > 0),
    used_count INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    one_use_per_customer INTEGER NOT NULL DEFAULT 0 CHECK (one_use_per_customer IN (0, 1)),
    category_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);



-- ============================================================
-- RESET TOKENS
-- Step 31
--
-- IMPORTANT:
-- Store only the HASH of the reset token.
-- Never store the readable/raw token.
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
--
-- Records inventory changes.
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


-- ------------------------------------------------------------
-- ADDRESSES
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_addresses_user
ON addresses(user_id);



-- ------------------------------------------------------------
-- ORDERS
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_orders_user
ON orders(user_id);


CREATE INDEX IF NOT EXISTS
idx_orders_user_created
ON orders(
    user_id,
    created_at
);


CREATE INDEX IF NOT EXISTS
idx_orders_status
ON orders(status);



-- ------------------------------------------------------------
-- ORDER ITEMS
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_order_items_order
ON order_items(order_id);


CREATE INDEX IF NOT EXISTS
idx_order_items_book
ON order_items(book_id);


CREATE INDEX IF NOT EXISTS
idx_order_items_order_book
ON order_items(
    order_id,
    book_id
);



-- ------------------------------------------------------------
-- CATEGORIES
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_book_categories_book
ON book_categories(book_id);


CREATE INDEX IF NOT EXISTS
idx_book_categories_category
ON book_categories(category_id);



-- ------------------------------------------------------------
-- TAGS
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_book_tags_book
ON book_tags(book_id);


CREATE INDEX IF NOT EXISTS
idx_book_tags_tag
ON book_tags(tag_id);



-- ------------------------------------------------------------
-- REVIEWS
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_reviews_book_created
ON reviews(
    book_id,
    created_at
);


CREATE INDEX IF NOT EXISTS
idx_reviews_user
ON reviews(user_id);



-- ------------------------------------------------------------
-- WISHLIST
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_wishlist_user
ON wishlist(user_id);


CREATE INDEX IF NOT EXISTS
idx_wishlist_book
ON wishlist(book_id);



-- ------------------------------------------------------------
-- CART
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_cart_items_user
ON cart_items(user_id);


CREATE INDEX IF NOT EXISTS
idx_cart_items_book
ON cart_items(book_id);



-- ------------------------------------------------------------
-- RESERVATIONS
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_reservations_book_expiry
ON reservations(
    book_id,
    expires_at
);


CREATE INDEX IF NOT EXISTS
idx_reservations_user
ON reservations(user_id);


CREATE INDEX IF NOT EXISTS
idx_reservations_expiry
ON reservations(expires_at);



-- ------------------------------------------------------------
-- PASSWORD RESET
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_reset_tokens_hash
ON reset_tokens(token_hash);


CREATE INDEX IF NOT EXISTS
idx_reset_tokens_user
ON reset_tokens(user_id);



-- ------------------------------------------------------------
-- LOGIN ATTEMPTS
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_login_attempts_email_time
ON login_attempts(
    email,
    attempted_at
);



-- ------------------------------------------------------------
-- STOCK LOG
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS
idx_stock_log_book
ON stock_log(book_id);


CREATE INDEX IF NOT EXISTS
idx_stock_log_created
ON stock_log(created_at);

-- COUPON USAGE HISTORY
CREATE TABLE IF NOT EXISTS coupon_uses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coupon_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    order_id INTEGER,
    used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (coupon_id) REFERENCES coupons(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

-- RETURNS
CREATE TABLE IF NOT EXISTS returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending', 'Approved', 'Rejected')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by INTEGER,
    reviewed_at TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (reviewed_by) REFERENCES users(id)
);

-- RETURN ITEMS
CREATE TABLE IF NOT EXISTS return_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id INTEGER NOT NULL,
    order_item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    reason TEXT NOT NULL,
    FOREIGN KEY (return_id) REFERENCES returns(id) ON DELETE CASCADE,
    FOREIGN KEY (order_item_id) REFERENCES order_items(id)
);

-- Customer return requests
CREATE TABLE IF NOT EXISTS returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending', 'Approved', 'Rejected')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by INTEGER,
    reviewed_at TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (reviewed_by) REFERENCES users(id)
);

-- Items included in each return request
CREATE TABLE IF NOT EXISTS return_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id INTEGER NOT NULL,
    order_item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    reason TEXT,
    FOREIGN KEY (return_id) REFERENCES returns(id) ON DELETE CASCADE,
    FOREIGN KEY (order_item_id) REFERENCES order_items(id)
);

CREATE INDEX IF NOT EXISTS idx_returns_order_id
    ON returns(order_id);

CREATE INDEX IF NOT EXISTS idx_returns_status
    ON returns(status);

CREATE INDEX IF NOT EXISTS idx_return_items_return_id
    ON return_items(return_id);
