-- =====================================================
-- PAGETURNER SQL QUERIES
-- 12 REQUIRED QUERIES
-- =====================================================


-- 1. Display all books
SELECT *
FROM books
ORDER BY title;


-- 2. Search books by title or author
SELECT *
FROM books
WHERE title LIKE ?
   OR author LIKE ?
ORDER BY title;


-- 3. Filter books by category
SELECT *
FROM books
WHERE category = ?
ORDER BY title;


-- 4. Find books cheaper than a given price
SELECT *
FROM books
WHERE price <= ?
ORDER BY price ASC;


-- 5. SAFE STOCK UPDATE
-- Used during checkout.
-- The stock is reduced only when enough stock exists.

UPDATE books
SET stock = stock - ?
WHERE id = ?
  AND stock >= ?;


-- 6. Get a customer's orders
SELECT *
FROM orders
WHERE user_id = ?
ORDER BY created_at DESC;


-- 7. Get order items
SELECT
    order_items.*,
    books.title
FROM order_items
JOIN books
    ON books.id = order_items.book_id
WHERE order_items.order_id = ?;


-- 8. Find a wishlist item
SELECT *
FROM wishlist
WHERE user_id = ?
  AND book_id = ?;


-- 9. Add a book to wishlist
INSERT OR IGNORE INTO wishlist
(user_id, book_id)
VALUES (?, ?);


-- 10. Find an active coupon
SELECT *
FROM coupons
WHERE code = ?
  AND active = 1;


-- 11. Update order status
UPDATE orders
SET status = ?
WHERE id = ?;


-- 12. Check the query plan for category filtering
EXPLAIN QUERY PLAN
SELECT *
FROM books
WHERE category = ?;