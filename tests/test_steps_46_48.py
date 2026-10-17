import sqlite3

from shop import coupon_discount_paise, money


def test_money_helper_formats_integer_paise_without_float_math():
    assert money(3333) == "₹33.33"
    assert money(9999) == "₹99.99"
    assert money(-5) == "-₹0.05"


def test_three_books_and_ten_percent_coupon_round_consistently():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE coupons (code TEXT, percent INTEGER, active INTEGER, expiry_date TEXT)"
    )
    connection.execute(
        "INSERT INTO coupons(code, percent, active, expiry_date) VALUES (?, ?, ?, ?)",
        ("TENOFF", 10, 1, "2099-12-31"),
    )

    subtotal_paise = 3 * 3333
    discount_paise, error = coupon_discount_paise(connection, "TENOFF", subtotal_paise)
    total_paise = subtotal_paise - discount_paise

    assert error is None
    assert subtotal_paise == 9999
    assert discount_paise == 1000
    assert total_paise == 8999
    assert money(total_paise) == "₹89.99"
    connection.close()


def test_money_columns_are_integer_types_in_current_schema():
    connection = sqlite3.connect("pageturner.db")
    try:
        bad_columns = []
        for (table_name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall():
            for column in connection.execute(
                f'PRAGMA table_info("{table_name}")'
            ).fetchall():
                name, declared_type = column[1], (column[2] or "").upper()
                if any(word in name.lower() for word in (
                    "price", "total", "discount", "refund", "shipping", "tax", "amount", "paise"
                )) and any(word in declared_type for word in ("REAL", "FLOAT", "DOUBLE")):
                    bad_columns.append((table_name, name, declared_type))
        assert bad_columns == []
    finally:
        connection.close()
