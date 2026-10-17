-- Step 48: move legacy single-category values into normalized relations.
INSERT OR IGNORE INTO categories(name)
SELECT DISTINCT TRIM(category)
FROM books
WHERE category IS NOT NULL AND TRIM(category) <> '';

INSERT OR IGNORE INTO book_categories(book_id, category_id)
SELECT b.id, c.id
FROM books AS b
JOIN categories AS c
  ON LOWER(TRIM(b.category)) = LOWER(TRIM(c.name))
WHERE b.category IS NOT NULL AND TRIM(b.category) <> '';

CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name COLLATE NOCASE);
