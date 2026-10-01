-- 1. All books cheaper than 500
SELECT *
FROM books
WHERE price < 500;


-- 2. Technology books sorted by price,
-- highest price first
SELECT *
FROM books
WHERE category = 'Technology'
ORDER BY price DESC;


-- 3. Number of books in each category
SELECT category, COUNT(*) AS book_count
FROM books
GROUP BY category;


-- 4. Most expensive book
SELECT *
FROM books
ORDER BY price DESC
LIMIT 1;


-- 5. Each order with customer name and total
SELECT id, customer_name, total, created_at
FROM orders
ORDER BY created_at DESC;