-- Step 64-67: indexes for device lookups, API rate windows, audit history,
-- date-range reporting, and return-value aggregation.
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_last_seen
    ON user_sessions(user_id, last_seen);
CREATE INDEX IF NOT EXISTS idx_api_rate_limits_ip_requested
    ON api_rate_limits(ip, requested_at);
CREATE INDEX IF NOT EXISTS idx_admin_log_user_created
    ON admin_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_created_status
    ON orders(created_at, status);
-- Returns used both created_at (new schema) and requested_at (legacy schema);
-- query code supports both layouts, so no schema-specific index is added here.
CREATE INDEX IF NOT EXISTS idx_return_items_return_item
    ON return_items(return_id, order_item_id);
