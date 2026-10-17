CREATE TRIGGER IF NOT EXISTS trg_order_status_notification
AFTER INSERT ON order_status_history
BEGIN
 INSERT INTO notifications(user_id,text,link)
 SELECT user_id, 'Your order #' || NEW.order_id || ' status changed to ' || NEW.status,
        '/orders/' || NEW.order_id || '/tracking'
 FROM orders WHERE id=NEW.order_id AND user_id IS NOT NULL;
END;
CREATE TRIGGER IF NOT EXISTS trg_return_decision_notification
AFTER UPDATE OF status ON returns
WHEN OLD.status <> NEW.status AND NEW.status IN ('Approved','Rejected')
BEGIN
 INSERT INTO notifications(user_id,text,link)
 SELECT o.user_id, 'Your return request #' || NEW.id || ' was ' || lower(NEW.status) || '.', '/orders/' || NEW.order_id || '/returns' FROM orders o WHERE o.id=NEW.order_id AND o.user_id IS NOT NULL;
END;
CREATE TRIGGER IF NOT EXISTS trg_wishlist_restock_notification
AFTER UPDATE OF stock ON books
WHEN OLD.stock <= 0 AND NEW.stock > 0
BEGIN
 INSERT INTO notifications(user_id,text,link)
 SELECT w.user_id, 'A book on your wishlist is back in stock: ' || NEW.title, '/book/' || NEW.id
 FROM wishlist w WHERE w.book_id=NEW.id;
END;
