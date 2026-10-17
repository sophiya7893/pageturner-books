from flask import (
    Blueprint,
    jsonify,
    request,
)

from db import get_db
from shop import get_cart, save_cart


# ============================================================
# API BLUEPRINT
# ============================================================

api_bp = Blueprint(
    "api",
    __name__,
    url_prefix="/api"
)


# ============================================================
# BOOK API
# ============================================================

@api_bp.route("/books")
def books():
    """Read-only JSON catalogue with ranked title/author/tag search."""
    conn = get_db()
    q = request.args.get("q", "").strip()
    if q:
        term = f"%{q}%"
        rows = conn.execute(
            """SELECT b.id, b.title, b.author, b.category, b.price_paise,
                      b.stock, b.cover_image,
                      CASE WHEN b.title LIKE ? THEN 3
                           WHEN b.author LIKE ? THEN 2
                           WHEN EXISTS (
                               SELECT 1 FROM book_tags bt
                               JOIN tags t ON t.id = bt.tag_id
                               WHERE bt.book_id = b.id AND t.name LIKE ?
                           ) THEN 1 ELSE 0 END AS search_score
               FROM books b
               WHERE b.title LIKE ? OR b.author LIKE ? OR EXISTS (
                   SELECT 1 FROM book_tags bt JOIN tags t ON t.id = bt.tag_id
                   WHERE bt.book_id = b.id AND t.name LIKE ?
               )
               ORDER BY search_score DESC, b.title COLLATE NOCASE ASC
               LIMIT 100""",
            (term, term, term, term, term, term),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, title, author, category, price_paise, stock, cover_image,
                      0 AS search_score
               FROM books ORDER BY title COLLATE NOCASE ASC LIMIT 100"""
        ).fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        paise = int(item.get("price_paise") or 0)
        item["price"] = f"{paise // 100}.{paise % 100:02d}"
        payload.append(item)
    return jsonify(payload)


# ============================================================
# ADD TO CART API
# ============================================================

@api_bp.route(
    "/cart/add/<int:book_id>",
    methods=["POST"]
)
def add_to_cart(book_id):
    """
    Add a book to the session cart using JSON.

    Example JSON:

        {
            "quantity": 1
        }

    CSRF protection still applies.

    The client should send:

        X-CSRF-Token
    """

    data = request.get_json(
        silent=True
    ) or {}

    try:
        quantity = int(
            data.get(
                "quantity",
                1
            )
        )

    except (ValueError, TypeError):
        quantity = 0

    if quantity <= 0:
        return jsonify(
            success=False,
            message=(
                "Quantity must be "
                "greater than zero."
            )
        ), 400

    db = get_db()

    book = db.execute(
        """
        SELECT
            id,
            title,
            stock
        FROM books
        WHERE id = ?
        """,
        (book_id,)
    ).fetchone()

    if book is None:
        return jsonify(
            success=False,
            message="Book not found."
        ), 404

    if int(book["stock"]) <= 0:
        return jsonify(
            success=False,
            message="Book is sold out."
        ), 400

    cart_data = get_cart()

    key = str(book_id)

    new_quantity = (
        cart_data.get(
            key,
            0
        )
        + quantity
    )

    if new_quantity > int(
        book["stock"]
    ):
        return jsonify(
            success=False,
            message=(
                f"Only {book['stock']} "
                "copies are available."
            )
        ), 400

    cart_data[key] = new_quantity

    save_cart(
        cart_data
    )

    return jsonify(
        success=True,
        message=(
            f"'{book['title']}' "
            "added to cart."
        ),
        cart_count=sum(
            cart_data.values()
        )
    )