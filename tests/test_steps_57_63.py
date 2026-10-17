"""Focused regression tests for the order and money roadmap."""
import sqlite3
from pathlib import Path

from app import app
from shop import ALLOWED_STATUS_MOVES, calculate_order_money


def test_status_transition_dictionary_is_strict():
    assert ALLOWED_STATUS_MOVES["Placed"] == {"Packed", "Cancelled"}
    assert ALLOWED_STATUS_MOVES["Packed"] == {"Shipped"}
    assert ALLOWED_STATUS_MOVES["Shipped"] == {"Delivered"}
    assert ALLOWED_STATUS_MOVES["Delivered"] == set()
    assert "Placed" not in ALLOWED_STATUS_MOVES["Delivered"]


def test_integer_paise_tax_and_shipping_are_consistent():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE shipping_zones(zone_prefix TEXT PRIMARY KEY, price_paise INTEGER NOT NULL);
        INSERT INTO shipping_zones VALUES ('11', 4000), ('DEFAULT', 5000);
        CREATE TABLE site_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO site_settings VALUES ('free_shipping_threshold_paise', '50000');
        CREATE TABLE coupons(id INTEGER PRIMARY KEY, code TEXT, category_id INTEGER);
        CREATE TABLE book_categories(book_id INTEGER, category_id INTEGER);
    """)
    with app.test_request_context("/"):
        summary = calculate_order_money(
            conn,
            [{"id": 1, "quantity": 3, "price_paise": 3333}],
            1000,
            "110001",
        )
    assert summary == {
        "subtotal_paise": 9999,
        "discount_paise": 1000,
        "shipping_paise": 4000,
        "tax_paise": 450,
        "total_paise": 13449,
    }
    conn.close()
