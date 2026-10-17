"""Smoke/regression checks for the consolidated Steps 42-74 project."""
import re
import sqlite3
from pathlib import Path

from jinja2 import nodes
from werkzeug.security import generate_password_hash

from app import app as flask_app
from migrate import migrate


def test_fresh_migrations_are_repeatable_and_coupon_rules_exist(tmp_path):
    database = tmp_path / "fresh.db"
    migrate(database)
    conn = sqlite3.connect(database)
    first = conn.execute("SELECT version, filename FROM schema_version ORDER BY version").fetchall()
    assert len(first) == 11
    columns = {row[1] for row in conn.execute("PRAGMA table_info(coupons)")}
    assert {"min_order_paise", "max_discount_paise", "one_use_per_customer", "category_id", "usage_limit"} <= columns
    conn.close()
    migrate(database)
    conn = sqlite3.connect(database)
    second = conn.execute("SELECT version, filename FROM schema_version ORDER BY version").fetchall()
    assert first == second
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


def test_all_template_url_for_endpoints_exist():
    known = {rule.endpoint for rule in flask_app.url_map.iter_rules()}
    for path in Path(flask_app.template_folder).glob("*.html"):
        tree = flask_app.jinja_env.parse(path.read_text(encoding="utf-8"))
        for call in tree.find_all(nodes.Call):
            if (isinstance(call.node, nodes.Name) and call.node.name == "url_for"
                    and call.args and isinstance(call.args[0], nodes.Const)):
                endpoint = call.args[0].value
                assert endpoint == "static" or endpoint in known, f"{path}: missing endpoint {endpoint}"


def test_public_routes_and_json_404(client):
    for path in ("/", "/login", "/register", "/cart", "/contact", "/api/books", "/api/books?q=python"):
        response = client.get(path)
        assert response.status_code < 500, path
    response = client.get("/api/books/987654321")
    assert response.status_code == 404
    assert response.is_json and response.get_json() == {"error": "not found"}


def test_admin_coupon_page_renders_and_advanced_coupon_can_be_created(client):
    flask_app.config.update(TESTING=True, SECRET_KEY="test-secret")
    with flask_app.app_context():
        from db import get_db
        get_db().execute(
            "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'admin')",
            ("Test Admin", "test-admin@example.test", generate_password_hash("StrongPassword!2026")),
        )
        get_db().commit()
    page = client.get("/admin/login")
    token_match = re.search(r'name="_csrf_token"\s+value="([^"]+)"', page.get_data(as_text=True))
    assert token_match
    response = client.post("/admin/login", data={
        "_csrf_token": token_match.group(1),
        "email": "test-admin@example.test",
        "password": "StrongPassword!2026",
    }, follow_redirects=True)
    assert response.status_code == 200
    page = client.get("/admin/coupons")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', html).group(1)
    response = client.post("/admin/coupons", data={
        "csrf_token": token, "action": "create", "code": "TEST15",
        "discount_type": "percentage", "discount_value": "15",
        "min_order_paise": "10000", "max_discount_paise": "2000",
        "usage_limit": "3", "category_id": "", "one_use_per_customer": "1",
        "expires_at": "2099-12-31T23:59",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"TEST15" in response.data
    with flask_app.app_context():
        row = get_db().execute("SELECT percent, discount_value, min_order_paise, max_discount_paise, usage_limit, one_use_per_customer FROM coupons WHERE code='TEST15'").fetchone()
        assert tuple(row) == (15, 15, 10000, 2000, 3, 1)


def test_broken_first_migration_rolls_back_entire_database(tmp_path, monkeypatch):
    import migrate as migration_module
    database = tmp_path / "broken.db"
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "001_broken.sql").write_text(
        "CREATE TABLE should_rollback (id INTEGER PRIMARY KEY);\nTHIS IS NOT SQL;\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(migration_module, "MIGRATIONS_DIR", migration_dir)
    try:
        migration_module.migrate(database)
    except sqlite3.OperationalError:
        pass
    else:
        raise AssertionError("The deliberately broken migration should fail")
    conn = sqlite3.connect(database)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "should_rollback" not in tables
    assert "schema_version" not in tables
    conn.close()


def test_api_rate_limit_returns_json_429(client):
    for _ in range(30):
        response = client.get("/api/books")
        assert response.status_code == 200
    response = client.get("/api/books")
    assert response.status_code == 429
    assert response.is_json
    assert response.get_json()["error"] == "rate limit exceeded"


def test_checkout_places_order_with_phone_from_saved_address(client):
    from db import get_db
    with flask_app.app_context():
        db = get_db()
        user_id = db.execute(
            "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'customer')",
            ("Checkout Customer", "checkout@example.test", generate_password_hash("CustomerPassword!2026")),
        ).lastrowid
        book_id = db.execute(
            "INSERT INTO books(title,author,category,price_paise,stock,description) VALUES(?,?,?,?,?,?)",
            ("Test Book", "Test Author", "Testing", 3333, 3, "Order-flow test book"),
        ).lastrowid
        address_id = db.execute(
            "INSERT INTO addresses(user_id,label,line1,city,pincode,phone,is_default) VALUES(?,?,?,?,?,?,1)",
            (user_id, "Home", "1 Test Street", "Bengaluru", "110001", "9876543210"),
        ).lastrowid
        db.execute("INSERT INTO cart_items(user_id,book_id,quantity) VALUES(?,?,1)", (user_id, book_id))
        db.commit()
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["user_name"] = "Checkout Customer"
        session["user_email"] = "checkout@example.test"
        session["user_role"] = "customer"
    checkout = client.get("/checkout")
    assert checkout.status_code == 200
    assert b"9876543210" in checkout.data
    token = re.search(r'name="_csrf_token"\s+value="([^"]+)"', checkout.get_data(as_text=True)).group(1)
    response = client.post("/checkout/place-order", data={
        "_csrf_token": token,
        "address_id": str(address_id),
    }, follow_redirects=True)
    assert response.status_code == 200
    with flask_app.app_context():
        db = get_db()
        order = db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        assert order is not None
        assert order["total_paise"] == order["subtotal_paise"] + order["shipping_paise"] + order["tax_paise"] - order["discount_paise"]
        item = db.execute("SELECT * FROM order_items WHERE order_id=?", (order["id"],)).fetchone()
        assert item["price_paise"] == 3333
        assert db.execute("SELECT stock FROM books WHERE id=?", (book_id,)).fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM cart_items WHERE user_id=?", (user_id,)).fetchone()[0] == 0


def test_admin_and_shop_share_one_status_transition_dictionary():
    import admin
    import shop
    from order_rules import ALLOWED_STATUS_MOVES
    assert admin.ALLOWED_STATUS_MOVES is ALLOWED_STATUS_MOVES
    assert shop.ALLOWED_STATUS_MOVES is ALLOWED_STATUS_MOVES


def test_tracking_and_invoice_enforce_order_ownership(client):
    from db import get_db
    with flask_app.app_context():
        db = get_db()
        owner_id = db.execute(
            "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'customer')",
            ("Order Owner", "owner@example.test", generate_password_hash("OwnerPassword!2026")),
        ).lastrowid
        other_id = db.execute(
            "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'customer')",
            ("Other Customer", "other@example.test", generate_password_hash("OtherPassword!2026")),
        ).lastrowid
        book_id = db.execute(
            "INSERT INTO books(title,author,category,price_paise,stock) VALUES(?,?,?,?,?)",
            ("Invoice Test Book", "Author", "Testing", 1250, 1),
        ).lastrowid
        order_id = db.execute(
            "INSERT INTO orders(user_id,customer_name,email,phone,address_snapshot,status,total_paise,subtotal_paise,discount_paise,shipping_paise,tax_paise) VALUES(?,?,?,?,?,'Placed',1250,1250,0,0,0)",
            (owner_id, "Order Owner", "owner@example.test", "9876543210", "Home, City, 110001"),
        ).lastrowid
        db.execute("INSERT INTO order_items(order_id,book_id,quantity,price_paise) VALUES(?,?,1,1250)", (order_id, book_id))
        db.execute("INSERT INTO order_status_history(order_id,status,changed_by,note) VALUES(?,'Placed',?,'Order placed')", (order_id, owner_id))
        db.commit()
    with client.session_transaction() as session:
        session["user_id"] = other_id
        session["user_name"] = "Other Customer"
        session["user_email"] = "other@example.test"
        session["user_role"] = "customer"
    assert client.get(f"/orders/{order_id}/tracking").status_code == 404
    assert client.get(f"/order/{order_id}/invoice").status_code in {403, 404}
    with client.session_transaction() as session:
        session["user_id"] = owner_id
        session["user_name"] = "Order Owner"
        session["user_email"] = "owner@example.test"
        session["user_role"] = "customer"
        session.pop("_device_token", None)
    assert client.get(f"/orders/{order_id}/tracking").status_code == 200
    assert client.get(f"/order/{order_id}/invoice").status_code == 200
    assert client.get(f"/orders/{order_id}/invoice").status_code == 200
