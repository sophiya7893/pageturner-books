-- Step 73: indexes used by ranked title/author/tag search.
CREATE INDEX IF NOT EXISTS idx_books_title_nocase ON books(title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_books_author_nocase ON books(author COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tags_name_nocase ON tags(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_book_tags_tag_book ON book_tags(tag_id, book_id);
CREATE INDEX IF NOT EXISTS idx_book_imports_hash ON book_imports(file_hash);
