-- ===========================================================
-- 002_categories_and_tags.sql
-- STEP 48
-- Many categories and tags per book.
-- ===========================================================


-- -----------------------------------------------------------
-- CATEGORIES
-- -----------------------------------------------------------

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL
        COLLATE NOCASE
        UNIQUE
);


-- -----------------------------------------------------------
-- BOOK <-> CATEGORY
-- -----------------------------------------------------------

CREATE TABLE book_categories (
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


-- -----------------------------------------------------------
-- COPY OLD CATEGORY NAMES
-- -----------------------------------------------------------

INSERT OR IGNORE INTO categories
(
    name
)

SELECT DISTINCT
    TRIM(category)

FROM books

WHERE category IS NOT NULL
  AND TRIM(category) != '';


-- -----------------------------------------------------------
-- CONNECT EXISTING BOOKS TO THEIR OLD CATEGORY
-- -----------------------------------------------------------

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
  AND TRIM(b.category) != '';


-- -----------------------------------------------------------
-- TAGS
-- -----------------------------------------------------------

CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL
        COLLATE NOCASE
        UNIQUE
);


-- -----------------------------------------------------------
-- BOOK <-> TAG
-- -----------------------------------------------------------

CREATE TABLE book_tags (
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


-- -----------------------------------------------------------
-- INDEXES
-- -----------------------------------------------------------

CREATE INDEX
idx_book_categories_book
ON book_categories(book_id);


CREATE INDEX
idx_book_categories_category
ON book_categories(category_id);


CREATE INDEX
idx_book_tags_book
ON book_tags(book_id);


CREATE INDEX
idx_book_tags_tag
ON book_tags(tag_id);