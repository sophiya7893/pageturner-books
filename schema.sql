PRAGMA foreign_keys = ON;

-- =====================================================
-- BOOKS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,

    author TEXT NOT NULL,

    category TEXT NOT NULL,

    price REAL NOT NULL CHECK (price >= 0),

    stock INTEGER NOT NULL DEFAULT 0
        CHECK (stock >= 0),

    description TEXT,

    cover_image TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =====================================================
-- USERS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    email TEXT NOT NULL UNIQUE,

    password_hash TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =====================================================
-- ADMINS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    email TEXT NOT NULL UNIQUE,

    password_hash TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =====================================================
-- ORDERS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER,

    customer_name TEXT NOT NULL,

    email TEXT NOT NULL,

    phone TEXT NOT NULL,

    address TEXT NOT NULL,

    total_amount REAL NOT NULL
        CHECK (total_amount >= 0),

    discount_amount REAL NOT NULL DEFAULT 0
        CHECK (discount_amount >= 0),

    coupon_code TEXT,

    status TEXT NOT NULL DEFAULT 'Placed'
        CHECK (
            status IN (
                'Placed',
                'Packed',
                'Delivered'
            )
        ),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
);


-- =====================================================
-- ORDER ITEMS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    order_id INTEGER NOT NULL,

    book_id INTEGER NOT NULL,

    quantity INTEGER NOT NULL
        CHECK (quantity > 0),

    price REAL NOT NULL
        CHECK (price >= 0),

    FOREIGN KEY (order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE,

    FOREIGN KEY (book_id)
        REFERENCES books(id)
        ON DELETE RESTRICT
);


-- =====================================================
-- REVIEWS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    book_id INTEGER NOT NULL,

    rating INTEGER NOT NULL
        CHECK (rating >= 1 AND rating <= 5),

    comment TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    FOREIGN KEY (book_id)
        REFERENCES books(id)
        ON DELETE CASCADE
);


-- =====================================================
-- WISHLIST TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS wishlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, book_id),

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    FOREIGN KEY (book_id)
        REFERENCES books(id)
        ON DELETE CASCADE
);


-- =====================================================
-- COUPONS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    code TEXT NOT NULL UNIQUE,

    percent REAL NOT NULL
        CHECK (
            percent > 0
            AND percent <= 100
        ),

    expiry_date DATE,

    active INTEGER NOT NULL DEFAULT 1
        CHECK (active IN (0, 1))
);


-- =====================================================
-- INDEXES
-- =====================================================

-- Step 25:
-- Faster category filtering.

CREATE INDEX IF NOT EXISTS idx_books_category
ON books(category);


-- Faster customer order history.

CREATE INDEX IF NOT EXISTS idx_orders_user_id
ON orders(user_id);


-- Faster book searching.

CREATE INDEX IF NOT EXISTS idx_books_title
ON books(title);


CREATE INDEX IF NOT EXISTS idx_books_author
ON books(author);


-- Faster order-item lookups.

CREATE INDEX IF NOT EXISTS idx_order_items_order_id
ON order_items(order_id);


CREATE INDEX IF NOT EXISTS idx_order_items_book_id
ON order_items(book_id);


-- Faster wishlist lookups.

CREATE INDEX IF NOT EXISTS idx_wishlist_user_id
ON wishlist(user_id);


CREATE INDEX IF NOT EXISTS idx_wishlist_book_id
ON wishlist(book_id);


-- Faster review lookups.

CREATE INDEX IF NOT EXISTS idx_reviews_book_id
ON reviews(book_id);


-- Faster coupon lookup.

CREATE INDEX IF NOT EXISTS idx_coupons_code
ON coupons(code);