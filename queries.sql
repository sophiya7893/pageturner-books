-- ============================================================
-- 1. FIND BOOKS BY CATEGORY
-- ============================================================

SELECT
    id,
    title,
    author,
    category,
    price,
    stock
FROM books
WHERE category = ?
ORDER BY title;


-- ============================================================
-- 2. SEARCH BOOKS
-- ============================================================

SELECT
    id,
    title,
    author,
    category,
    price,
    stock
FROM books
WHERE title LIKE ?
   OR author LIKE ?
   OR category LIKE ?
ORDER BY title;


-- ============================================================
-- 3. AVERAGE RATING FOR A BOOK
-- ============================================================

SELECT
    book_id,
    ROUND(AVG(rating), 1) AS average_rating,
    COUNT(*) AS review_count
FROM reviews
WHERE book_id = ?
GROUP BY book_id;


-- ============================================================
-- 4. FIND CUSTOMER ORDERS
-- ============================================================

SELECT
    o.id,
    o.name,
    o.phone,
    o.total,
    o.created_at,
    COUNT(oi.id) AS item_count
FROM orders AS o
LEFT JOIN order_items AS oi
    ON oi.order_id = o.id
WHERE o.phone = ?
GROUP BY
    o.id,
    o.name,
    o.phone,
    o.total,
    o.created_at
ORDER BY o.created_at DESC;


-- ============================================================
-- 5. TOTAL ORDERS FROM A GIVEN DATE
-- ============================================================

SELECT
    COUNT(*) AS total_orders
FROM orders
WHERE created_at >= ?;


-- ============================================================
-- 6. TOTAL REVENUE FROM A GIVEN DATE
-- ============================================================

SELECT
    COALESCE(SUM(total), 0) AS total_revenue
FROM orders
WHERE created_at >= ?;


-- ============================================================
-- 7. BEST-SELLING BOOKS
-- ============================================================

SELECT
    book_id,
    title,
    SUM(quantity) AS quantity_sold,
    SUM(price * quantity) AS revenue
FROM order_items
WHERE order_id IN (
    SELECT id
    FROM orders
    WHERE created_at >= ?
)
GROUP BY
    book_id,
    title
ORDER BY quantity_sold DESC;


-- ============================================================
-- 8. ORDERS / SALES BY CATEGORY
-- ============================================================

SELECT
    b.category,
    COUNT(DISTINCT oi.order_id) AS orders_count,
    SUM(oi.quantity) AS items_sold,
    SUM(oi.price * oi.quantity) AS revenue
FROM order_items AS oi
JOIN books AS b
    ON b.id = oi.book_id
JOIN orders AS o
    ON o.id = oi.order_id
WHERE o.created_at >= ?
GROUP BY b.category
ORDER BY revenue DESC;