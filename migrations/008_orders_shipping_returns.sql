-- Step 57-63 supporting indexes and exact two-digit pincode zones.
CREATE INDEX IF NOT EXISTS idx_order_status_history_order_changed
ON order_status_history(order_id, changed_at);
CREATE INDEX IF NOT EXISTS idx_coupon_uses_coupon_user
ON coupon_uses(coupon_id, user_id);
CREATE INDEX IF NOT EXISTS idx_returns_status
ON returns(status);
CREATE INDEX IF NOT EXISTS idx_return_items_order_item
ON return_items(order_item_id);
INSERT OR IGNORE INTO shipping_zones(zone_prefix, price_paise) VALUES
('10',4000),('11',4000),('12',4000),('13',4000),('14',4000),('15',4000),('16',4000),('17',4000),('18',4000),('19',4000),
('20',4500),('21',4500),('22',4500),('23',4500),('24',4500),('25',4500),('26',4500),('27',4500),('28',4500),('29',4500),
('30',5000),('31',5000),('32',5000),('33',5000),('34',5000),('35',5000),('36',5000),('37',5000),('38',5000),('39',5000),
('40',5500),('41',5500),('42',5500),('43',5500),('44',5500),('45',5500),('46',5500),('47',5500),('48',5500),('49',5500),
('50',6000),('51',6000),('52',6000),('53',6000),('54',6000),('55',6000),('56',6000),('57',6000),('58',6000),('59',6000),
('60',6500),('61',6500),('62',6500),('63',6500),('64',6500),('65',6500),('66',6500),('67',6500),('68',6500),('69',6500),
('70',7000),('71',7000),('72',7000),('73',7000),('74',7000),('75',7000),('76',7000),('77',7000),('78',7000),('79',7000),
('80',7500),('81',7500),('82',7500),('83',7500),('84',7500),('85',7500),('86',7500),('87',7500),('88',7500),('89',7500);

-- Backfill the first known status for pre-existing orders without history.
INSERT INTO order_status_history(order_id, status, changed_by, changed_at, note)
SELECT o.id,
       CASE WHEN o.status='Pending' THEN 'Placed' ELSE o.status END,
       o.user_id, COALESCE(o.created_at, CURRENT_TIMESTAMP),
       'Initial status imported during order history migration.'
FROM orders o JOIN users u ON u.id=o.user_id
WHERE (CASE WHEN o.status='Pending' THEN 'Placed' ELSE o.status END) IN ('Placed','Packed','Shipped','Delivered','Cancelled')
  AND NOT EXISTS (SELECT 1 FROM order_status_history h WHERE h.order_id=o.id);
