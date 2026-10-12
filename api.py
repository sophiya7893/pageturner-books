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
    """
    Return books as JSON.

    Optional search:
        /api/books?q=python
    """

    db = get_db()

    q = request.args.get(
        "q",
        ""
    ).strip()

    if q:
        books_list = db.execute(
            """
            SELECT
                id,
                title,
                author,
                category,
                price,
                stock,
                cover_image
            FROM books
            WHERE title LIKE ?
               OR author LIKE ?
            ORDER BY title
            """,
            (
                f"%{q}%",
                f"%{q}%"
            )
        ).fetchall()

    else:
        books_list = db.execute(
            """
            SELECT
                id,
                title,
                author,
                category,
                price,
                stock,
                cover_image
            FROM books
            ORDER BY title
            """
        ).fetchall()

    return jsonify([
        dict(book)
        for book in books_list
    ])


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