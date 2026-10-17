-- ===========================================================
-- 001_money_to_paise.sql
-- STEP 46
-- Store all money as INTEGER paise.
-- ===========================================================


-- -----------------------------------------------------------
-- BOOK PRICE
-- ₹199.50 becomes 19950
-- -----------------------------------------------------------

ALTER TABLE books
ADD COLUMN price_paise
INTEGER NOT NULL DEFAULT 0;

UPDATE books
SET price_paise =
    CAST(
        ROUND(price * 100)
        AS INTEGER
    );


-- -----------------------------------------------------------
-- ORDER TOTAL
-- -----------------------------------------------------------

ALTER TABLE orders
ADD COLUMN total_paise
INTEGER NOT NULL DEFAULT 0;

UPDATE orders
SET total_paise =
    CAST(
        ROUND(total_amount * 100)
        AS INTEGER
    );


-- -----------------------------------------------------------
-- ORDER DISCOUNT
-- -----------------------------------------------------------

ALTER TABLE orders
ADD COLUMN discount_paise
INTEGER NOT NULL DEFAULT 0;

UPDATE orders
SET discount_paise =
    CAST(
        ROUND(
            COALESCE(
                discount_amount,
                0
            ) * 100
        )
        AS INTEGER
    );


-- -----------------------------------------------------------
-- ORDER ITEM PURCHASE PRICE
-- -----------------------------------------------------------

ALTER TABLE order_items
ADD COLUMN price_at_purchase_paise
INTEGER NOT NULL DEFAULT 0;

UPDATE order_items
SET price_at_purchase_paise =
    CAST(
        ROUND(
            price_at_purchase * 100
        )
        AS INTEGER
    );