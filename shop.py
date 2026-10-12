import sqlite3
from datetime import date

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from werkzeug.security import generate_password_hash

from db import get_db
from security import current_user, login_required


# ============================================================
# SHOP BLUEPRINT
# ============================================================

shop_bp = Blueprint(
    "shop",
    __name__
)


# ============================================================
# CART HELPERS
# ============================================================

def get_cart():
    raw_cart = session.get(
        "cart",
        {}
    )

    clean_cart = {}

    if not isinstance(raw_cart, dict):
        return clean_cart

    for book_id, quantity in raw_cart.items():

        try:
            clean_id = str(
                int(book_id)
            )

            clean_quantity = int(
                quantity
            )

        except (ValueError, TypeError):
            continue

        if clean_quantity > 0:
            clean_cart[
                clean_id
            ] = clean_quantity

    return clean_cart


def save_cart(cart_data):
    session["cart"] = cart_data
    session.modified = True


def get_cart_items():
    """
    Build cart information for display.

    Checkout performs its own stock validation
    inside BEGIN IMMEDIATE.
    """

    cart_data = get_cart()

    if not cart_data:
        return [], 0.0

    db = get_db()

    items = []
    total = 0.0

    for book_id, quantity in cart_data.items():

        book = db.execute(
            """
            SELECT
                id,
                title,
                author,
                category,
                price,
                stock,
                description,
                cover_image
            FROM books
            WHERE id = ?
            """,
            (int(book_id),)
        ).fetchone()

        if book is None:
            continue

        subtotal = (
            float(book["price"])
            * quantity
        )

        items.append({
            "id": book["id"],
            "title": book["title"],
            "author": book["author"],
            "category": book["category"],
            "price": float(
                book["price"]
            ),
            "stock": int(
                book["stock"]
            ),
            "description":
                book["description"],
            "cover_image":
                book["cover_image"],
            "quantity": quantity,
            "subtotal": subtotal,
        })

        total += subtotal

    return items, round(
        total,
        2
    )


# ============================================================
# HOME
# ============================================================

@shop_bp.route("/")
def home():
    db = get_db()

    q = request.args.get(
        "q",
        request.args.get(
            "search",
            ""
        )
    ).strip()

    selected_category = request.args.get(
        "category",
        ""
    ).strip()

    sort = request.args.get(
        "sort",
        "title_asc"
    ).strip()

    try:
        page = max(
            1,
            int(
                request.args.get(
                    "page",
                    1
                )
            )
        )

    except (ValueError, TypeError):
        page = 1

    per_page = 8

    conditions = []
    params = []

    if q:
        conditions.append(
            "(title LIKE ? OR author LIKE ?)"
        )

        params.extend([
            f"%{q}%",
            f"%{q}%"
        ])

    if selected_category:
        conditions.append(
            "category = ?"
        )

        params.append(
            selected_category
        )

    where_sql = ""

    if conditions:
        where_sql = (
            "WHERE "
            + " AND ".join(
                conditions
            )
        )

    allowed_sort = {
        "title_asc":
            "title ASC",
        "title_desc":
            "title DESC",
        "price_asc":
            "price ASC",
        "price_desc":
            "price DESC",
    }

    order_by = allowed_sort.get(
        sort,
        "title ASC"
    )

    total_books = db.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM books
        {where_sql}
        """,
        params
    ).fetchone()["count"]

    total_pages = max(
        1,
        (
            total_books
            + per_page
            - 1
        ) // per_page
    )

    page = min(
        page,
        total_pages
    )

    offset = (
        page - 1
    ) * per_page

    books = db.execute(
        f"""
        SELECT *
        FROM books
        {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        params + [
            per_page,
            offset
        ]
    ).fetchall()

    categories = [
        row["category"]
        for row in db.execute(
            """
            SELECT DISTINCT category
            FROM books
            WHERE category IS NOT NULL
            ORDER BY category
            """
        ).fetchall()
    ]

    return render_template(
        "home.html",
        books=books,
        categories=categories,
        q=q,
        search=q,
        selected_category=
            selected_category,
        sort=sort,
        page=page,
        total_pages=total_pages,
        total_books=total_books
    )


# ============================================================
# STEP 36
# BOOK DETAILS + CUSTOMERS ALSO BOUGHT
# ============================================================

@shop_bp.route(
    "/book/<int:book_id>"
)
def book_detail(book_id):
    db = get_db()

    book = db.execute(
        """
        SELECT
            b.*,
            COUNT(r.id)
                AS review_count,
            COALESCE(
                AVG(r.rating),
                0
            ) AS average_rating

        FROM books b

        LEFT JOIN reviews r
            ON r.book_id = b.id

        WHERE b.id = ?

        GROUP BY b.id
        """,
        (book_id,)
    ).fetchone()

    if book is None:
        abort(404)

    reviews = db.execute(
        """
        SELECT
            r.*,
            u.name AS user_name

        FROM reviews r

        LEFT JOIN users u
            ON u.id = r.user_id

        WHERE r.book_id = ?

        ORDER BY
            r.created_at DESC
        """,
        (book_id,)
    ).fetchall()

    # STEP 36
    # Self-JOIN order_items to find books
    # purchased in the same orders.
    recommendations = db.execute(
        """
        SELECT
            b.id,
            b.title,
            b.author,
            b.category,
            b.price,
            b.stock,
            b.cover_image,

            COUNT(
                DISTINCT mine.order_id
            ) AS together_count

        FROM order_items AS mine

        JOIN order_items AS other
            ON other.order_id =
               mine.order_id
           AND other.book_id !=
               mine.book_id

        JOIN books AS b
            ON b.id =
               other.book_id

        JOIN orders AS o
            ON o.id =
               mine.order_id

        WHERE mine.book_id = ?
          AND o.status != 'Cancelled'

        GROUP BY
            b.id,
            b.title,
            b.author,
            b.category,
            b.price,
            b.stock,
            b.cover_image

        ORDER BY
            together_count DESC,
            b.title ASC

        LIMIT 4
        """,
        (book_id,)
    ).fetchall()

    return render_template(
        "book_detail.html",
        book=book,
        reviews=reviews,
        recommendations=
            recommendations
    )


# ============================================================
# REGISTER
# ============================================================

@shop_bp.route(
    "/register",
    methods=["GET", "POST"]
)
def register():
    if request.method == "GET":
        return render_template(
            "register.html"
        )

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    if (
        not name
        or not email
        or not password
    ):
        flash(
            (
                "Name, email and "
                "password are required."
            ),
            "danger"
        )

        return render_template(
            "register.html"
        )

    if len(password) < 8:
        flash(
            (
                "Password must contain "
                "at least 8 characters."
            ),
            "danger"
        )

        return render_template(
            "register.html"
        )

    if password != confirm_password:
        flash(
            "Passwords do not match.",
            "danger"
        )

        return render_template(
            "register.html"
        )

    db = get_db()

    existing = db.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    if existing:
        flash(
            (
                "An account with this "
                "email already exists."
            ),
            "danger"
        )

        return render_template(
            "register.html"
        )

    try:
        db.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password_hash,
                role
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                email,
                generate_password_hash(
                    password
                ),
                "customer"
            )
        )

        db.commit()

    except sqlite3.IntegrityError:
        db.rollback()

        flash(
            "Unable to create account.",
            "danger"
        )

        return render_template(
            "register.html"
        )

    flash(
        (
            "Registration successful. "
            "Please login."
        ),
        "success"
    )

    return redirect(
        url_for("auth.login")
    )


# ============================================================
# ADD TO CART
# ============================================================

@shop_bp.route(
    "/cart/add/<int:book_id>",
    methods=["POST"]
)
def add_to_cart(book_id):
    try:
        quantity = int(
            request.form.get(
                "quantity",
                1
            )
        )

    except (ValueError, TypeError):
        quantity = 0

    if quantity <= 0:
        flash(
            (
                "Quantity must be "
                "greater than zero."
            ),
            "danger"
        )

        return redirect(
            request.referrer
            or url_for("shop.home")
        )

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
        abort(404)

    if book["stock"] <= 0:
        flash(
            (
                f"'{book['title']}' "
                "is sold out."
            ),
            "danger"
        )

        return redirect(
            request.referrer
            or url_for("shop.home")
        )

    cart_data = get_cart()

    key = str(book_id)

    new_quantity = (
        cart_data.get(
            key,
            0
        )
        + quantity
    )

    if new_quantity > book["stock"]:
        flash(
            (
                f"Only {book['stock']} "
                f"copies of "
                f"'{book['title']}' "
                "are available."
            ),
            "danger"
        )

        return redirect(
            request.referrer
            or url_for("shop.home")
        )

    cart_data[key] = new_quantity

    save_cart(
        cart_data
    )

    flash(
        (
            f"'{book['title']}' "
            "added to your cart."
        ),
        "success"
    )

    return redirect(
        request.referrer
        or url_for("shop.home")
    )


# ============================================================
# CART
# ============================================================

@shop_bp.route("/cart")
def cart():
    items, total = get_cart_items()

    discount = min(
        float(
            session.get(
                "discount_amount",
                0
            ) or 0
        ),
        float(total)
    )

    final_total = max(
        0,
        total - discount
    )

    return render_template(
        "cart.html",
        items=items,
        total=total,
        discount=discount,
        final_total=final_total,
        coupon_code=session.get(
            "coupon_code"
        )
    )


# ============================================================
# UPDATE ONE CART ITEM
# ============================================================

@shop_bp.route(
    "/cart/update/<int:book_id>",
    methods=["POST"]
)
def update_cart(book_id):
    cart_data = get_cart()

    key = str(book_id)

    if key not in cart_data:
        flash(
            "Book is not in your cart.",
            "warning"
        )

        return redirect(
            url_for("shop.cart")
        )

    try:
        quantity = int(
            request.form.get(
                "quantity",
                0
            )
        )

    except (ValueError, TypeError):
        quantity = 0

    if quantity <= 0:
        cart_data.pop(
            key,
            None
        )

        save_cart(
            cart_data
        )

        flash(
            "Book removed from cart.",
            "success"
        )

        return redirect(
            url_for("shop.cart")
        )

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
        cart_data.pop(
            key,
            None
        )

        save_cart(
            cart_data
        )

        abort(404)

    if quantity > book["stock"]:
        flash(
            (
                f"Only {book['stock']} "
                f"copies of "
                f"'{book['title']}' "
                "are available."
            ),
            "danger"
        )

        return redirect(
            url_for("shop.cart")
        )

    cart_data[key] = quantity

    save_cart(
        cart_data
    )

    flash(
        "Cart updated.",
        "success"
    )

    return redirect(
        url_for("shop.cart")
    )


# ============================================================
# REMOVE FROM CART
# ============================================================

@shop_bp.route(
    "/cart/remove/<int:book_id>",
    methods=["POST"]
)
def remove_from_cart(book_id):
    cart_data = get_cart()

    cart_data.pop(
        str(book_id),
        None
    )

    save_cart(
        cart_data
    )

    flash(
        "Book removed from cart.",
        "success"
    )

    return redirect(
        url_for("shop.cart")
    )


# ============================================================
# CLEAR CART
# ============================================================

@shop_bp.route(
    "/cart/clear",
    methods=["POST"]
)
def clear_cart():
    session["cart"] = {}

    session.pop(
        "coupon_code",
        None
    )

    session.pop(
        "discount_amount",
        None
    )

    session.modified = True

    flash(
        "Cart cleared.",
        "success"
    )

    return redirect(
        url_for("shop.cart")
    )


# ============================================================
# APPLY COUPON
# ============================================================

@shop_bp.route(
    "/cart/coupon",
    methods=["POST"]
)
def apply_coupon():
    code = request.form.get(
        "coupon_code",
        ""
    ).strip().upper()

    if not code:
        flash(
            "Please enter a coupon code.",
            "danger"
        )

        return redirect(
            url_for("shop.cart")
        )

    items, total = get_cart_items()

    if not items:
        flash(
            "Your cart is empty.",
            "warning"
        )

        return redirect(
            url_for("shop.cart")
        )

    db = get_db()

    coupon = db.execute(
        """
        SELECT *
        FROM coupons
        WHERE code = ?
          AND active = 1
        """,
        (code,)
    ).fetchone()

    if coupon is None:
        session.pop(
            "coupon_code",
            None
        )

        session.pop(
            "discount_amount",
            None
        )

        flash(
            (
                "Invalid or inactive "
                "coupon code."
            ),
            "danger"
        )

        return redirect(
            url_for("shop.cart")
        )

    expiry_date = coupon[
        "expiry_date"
    ]

    if expiry_date:
        try:
            if (
                date.fromisoformat(
                    expiry_date
                )
                < date.today()
            ):
                session.pop(
                    "coupon_code",
                    None
                )

                session.pop(
                    "discount_amount",
                    None
                )

                flash(
                    "This coupon has expired.",
                    "danger"
                )

                return redirect(
                    url_for("shop.cart")
                )

        except ValueError:
            flash(
                "Invalid coupon expiry date.",
                "danger"
            )

            return redirect(
                url_for("shop.cart")
            )

    percent = float(
        coupon["percent"]
    )

    if not 0 <= percent <= 100:
        flash(
            "Invalid coupon discount.",
            "danger"
        )

        return redirect(
            url_for("shop.cart")
        )

    discount = round(
        total
        * percent
        / 100,
        2
    )

    session[
        "coupon_code"
    ] = code

    session[
        "discount_amount"
    ] = discount

    session.modified = True

    flash(
        f"Coupon {code} applied.",
        "success"
    )

    return redirect(
        url_for("shop.cart")
    )


# ============================================================
# REMOVE COUPON
# ============================================================

@shop_bp.route(
    "/cart/coupon/remove",
    methods=["POST"]
)
def remove_coupon():
    session.pop(
        "coupon_code",
        None
    )

    session.pop(
        "discount_amount",
        None
    )

    session.modified = True

    flash(
        "Coupon removed.",
        "success"
    )

    return redirect(
        url_for("shop.cart")
    )


# ============================================================
# REVIEWS
# ============================================================

@shop_bp.route(
    "/book/<int:book_id>/reviews",
    methods=["POST"]
)
@login_required
def add_review(book_id):
    rating_text = request.form.get(
        "rating",
        ""
    ).strip()

    comment = request.form.get(
        "comment",
        ""
    ).strip()

    try:
        rating = int(
            rating_text
        )

    except (ValueError, TypeError):
        rating = 0

    if not 1 <= rating <= 5:
        flash(
            (
                "Rating must be "
                "between 1 and 5."
            ),
            "danger"
        )

        return redirect(
            url_for(
                "shop.book_detail",
                book_id=book_id
            )
        )

    if not comment:
        flash(
            "Please write a review.",
            "danger"
        )

        return redirect(
            url_for(
                "shop.book_detail",
                book_id=book_id
            )
        )

    db = get_db()

    book = db.execute(
        """
        SELECT id
        FROM books
        WHERE id = ?
        """,
        (book_id,)
    ).fetchone()

    if book is None:
        abort(404)

    db.execute(
        """
        INSERT INTO reviews
        (
            user_id,
            book_id,
            name,
            rating,
            comment
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session["user_id"],
            book_id,
            session.get(
                "user_name",
                "Customer"
            ),
            rating,
            comment
        )
    )

    db.commit()

    flash(
        "Your review was added.",
        "success"
    )

    return redirect(
        url_for(
            "shop.book_detail",
            book_id=book_id
        )
    )


# ============================================================
# WISHLIST
# ============================================================

@shop_bp.route("/wishlist")
@login_required
def wishlist():
    db = get_db()

    books = db.execute(
        """
        SELECT b.*

        FROM wishlist w

        JOIN books b
            ON b.id = w.book_id

        WHERE w.user_id = ?

        ORDER BY
            w.created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    return render_template(
        "wishlist.html",
        books=books
    )


@shop_bp.route(
    "/wishlist/toggle/<int:book_id>",
    methods=["POST"]
)
@login_required
def toggle_wishlist(book_id):
    db = get_db()

    book = db.execute(
        """
        SELECT id, title
        FROM books
        WHERE id = ?
        """,
        (book_id,)
    ).fetchone()

    if book is None:
        abort(404)

    existing = db.execute(
        """
        SELECT id
        FROM wishlist
        WHERE user_id = ?
          AND book_id = ?
        """,
        (
            session["user_id"],
            book_id
        )
    ).fetchone()

    if existing:
        db.execute(
            """
            DELETE FROM wishlist
            WHERE user_id = ?
              AND book_id = ?
            """,
            (
                session["user_id"],
                book_id
            )
        )

        message = (
            f"'{book['title']}' "
            "removed from your wishlist."
        )

        category = "info"

    else:
        db.execute(
            """
            INSERT INTO wishlist
            (
                user_id,
                book_id
            )
            VALUES (?, ?)
            """,
            (
                session["user_id"],
                book_id
            )
        )

        message = (
            f"'{book['title']}' "
            "added to your wishlist."
        )

        category = "success"

    db.commit()

    flash(
        message,
        category
    )

    return redirect(
        request.referrer
        or url_for("shop.home")
    )


# ============================================================
# STEP 28
# ADDRESS BOOK
# ============================================================

@shop_bp.route("/addresses")
@login_required
def addresses():
    db = get_db()

    rows = db.execute(
        """
        SELECT
            id,
            label,
            line1,
            city,
            pincode,
            is_default

        FROM addresses

        WHERE user_id = ?

        ORDER BY
            is_default DESC,
            id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    return render_template(
        "addresses.html",
        addresses=rows
    )


# ============================================================
# ADD ADDRESS
# ============================================================

@shop_bp.route(
    "/addresses/add",
    methods=["GET", "POST"]
)
@login_required
def add_address():
    if request.method == "GET":
        return render_template(
            "address_form.html",
            address=None,
            page_title="Add Address"
        )

    label = request.form.get(
        "label",
        ""
    ).strip()

    line1 = request.form.get(
        "line1",
        ""
    ).strip()

    city = request.form.get(
        "city",
        ""
    ).strip()

    pincode = request.form.get(
        "pincode",
        ""
    ).strip()

    make_default = (
        request.form.get(
            "is_default"
        )
        == "1"
    )

    if not all([
        label,
        line1,
        city,
        pincode
    ]):
        flash(
            (
                "Please complete all "
                "address fields."
            ),
            "danger"
        )

        return render_template(
            "address_form.html",
            address=None,
            page_title="Add Address"
        )

    db = get_db()

    try:
        db.execute(
            "BEGIN IMMEDIATE"
        )

        count = db.execute(
            """
            SELECT COUNT(*) AS count
            FROM addresses
            WHERE user_id = ?
            """,
            (session["user_id"],)
        ).fetchone()["count"]

        should_be_default = (
            count == 0
            or make_default
        )

        if should_be_default:
            db.execute(
                """
                UPDATE addresses
                SET is_default = 0
                WHERE user_id = ?
                """,
                (session["user_id"],)
            )

        db.execute(
            """
            INSERT INTO addresses
            (
                user_id,
                label,
                line1,
                city,
                pincode,
                is_default
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                label,
                line1,
                city,
                pincode,
                1
                if should_be_default
                else 0
            )
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    flash(
        "Address saved.",
        "success"
    )

    return redirect(
        url_for("shop.addresses")
    )


# ============================================================
# EDIT ADDRESS
# ============================================================

@shop_bp.route(
    "/addresses/<int:address_id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_address(address_id):
    db = get_db()

    address = db.execute(
        """
        SELECT *
        FROM addresses
        WHERE id = ?
          AND user_id = ?
        """,
        (
            address_id,
            session["user_id"]
        )
    ).fetchone()

    if address is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "address_form.html",
            address=address,
            page_title="Edit Address"
        )

    label = request.form.get(
        "label",
        ""
    ).strip()

    line1 = request.form.get(
        "line1",
        ""
    ).strip()

    city = request.form.get(
        "city",
        ""
    ).strip()

    pincode = request.form.get(
        "pincode",
        ""
    ).strip()

    make_default = (
        request.form.get(
            "is_default"
        )
        == "1"
    )

    if not all([
        label,
        line1,
        city,
        pincode
    ]):
        flash(
            "Please complete all fields.",
            "danger"
        )

        return redirect(
            url_for(
                "shop.edit_address",
                address_id=address_id
            )
        )

    try:
        db.execute(
            "BEGIN IMMEDIATE"
        )

        if make_default:
            db.execute(
                """
                UPDATE addresses
                SET is_default = 0
                WHERE user_id = ?
                """,
                (session["user_id"],)
            )

        db.execute(
            """
            UPDATE addresses
            SET
                label = ?,
                line1 = ?,
                city = ?,
                pincode = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (
                label,
                line1,
                city,
                pincode,
                address_id,
                session["user_id"]
            )
        )

        if make_default:
            db.execute(
                """
                UPDATE addresses
                SET is_default = 1
                WHERE id = ?
                  AND user_id = ?
                """,
                (
                    address_id,
                    session["user_id"]
                )
            )

        db.commit()

    except Exception:
        db.rollback()
        raise

    flash(
        "Address updated.",
        "success"
    )

    return redirect(
        url_for("shop.addresses")
    )


# ============================================================
# SET DEFAULT ADDRESS
# ============================================================

@shop_bp.route(
    "/addresses/<int:address_id>/default",
    methods=["POST"]
)
@login_required
def set_default_address(address_id):
    db = get_db()

    try:
        db.execute(
            "BEGIN IMMEDIATE"
        )

        address = db.execute(
            """
            SELECT id
            FROM addresses
            WHERE id = ?
              AND user_id = ?
            """,
            (
                address_id,
                session["user_id"]
            )
        ).fetchone()

        if address is None:
            db.rollback()
            abort(404)

        # STEP 28:
        # old default + new default
        # changed in ONE transaction.
        db.execute(
            """
            UPDATE addresses
            SET is_default = 0
            WHERE user_id = ?
            """,
            (session["user_id"],)
        )

        db.execute(
            """
            UPDATE addresses
            SET is_default = 1
            WHERE id = ?
              AND user_id = ?
            """,
            (
                address_id,
                session["user_id"]
            )
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    flash(
        "Default address updated.",
        "success"
    )

    return redirect(
        url_for("shop.addresses")
    )


# ============================================================
# DELETE ADDRESS
# ============================================================

@shop_bp.route(
    "/addresses/<int:address_id>/delete",
    methods=["POST"]
)
@login_required
def delete_address(address_id):
    db = get_db()

    try:
        db.execute(
            "BEGIN IMMEDIATE"
        )

        address = db.execute(
            """
            SELECT
                id,
                is_default
            FROM addresses
            WHERE id = ?
              AND user_id = ?
            """,
            (
                address_id,
                session["user_id"]
            )
        ).fetchone()

        if address is None:
            db.rollback()
            abort(404)

        was_default = bool(
            address["is_default"]
        )

        db.execute(
            """
            DELETE FROM addresses
            WHERE id = ?
              AND user_id = ?
            """,
            (
                address_id,
                session["user_id"]
            )
        )

        if was_default:
            replacement = db.execute(
                """
                SELECT id
                FROM addresses
                WHERE user_id = ?
                ORDER BY id
                LIMIT 1
                """,
                (session["user_id"],)
            ).fetchone()

            if replacement:
                db.execute(
                    """
                    UPDATE addresses
                    SET is_default = 1
                    WHERE id = ?
                    """,
                    (
                        replacement["id"],
                    )
                )

        db.commit()

    except Exception:
        db.rollback()
        raise

    flash(
        "Address deleted.",
        "success"
    )

    return redirect(
        url_for("shop.addresses")
    )


# ============================================================
# STEPS 28, 29, 34
# CHECKOUT
# ============================================================

@shop_bp.route(
    "/checkout",
    methods=["GET", "POST"]
)
@login_required
def checkout():
    raw_cart = get_cart()

    if not raw_cart:
        flash(
            "Your cart is empty.",
            "warning"
        )

        return redirect(
            url_for("shop.cart")
        )

    db = get_db()

    addresses_list = db.execute(
        """
        SELECT *
        FROM addresses
        WHERE user_id = ?
        ORDER BY
            is_default DESC,
            id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    if not addresses_list:
        flash(
            (
                "Please save a shipping "
                "address before checkout."
            ),
            "warning"
        )

        return redirect(
            url_for("shop.add_address")
        )

    display_items, display_total = (
        get_cart_items()
    )

    current_discount = min(
        float(
            session.get(
                "discount_amount",
                0
            ) or 0
        ),
        float(display_total)
    )

    if request.method == "GET":
        return render_template(
            "checkout.html",
            items=display_items,
            total=display_total,
            addresses=addresses_list,
            coupon_code=session.get(
                "coupon_code"
            ),
            discount=current_discount,
            final_total=max(
                0,
                display_total
                - current_discount
            )
        )

    try:
        address_id = int(
            request.form.get(
                "address_id",
                0
            )
        )

    except (ValueError, TypeError):
        address_id = 0

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    if not address_id:
        flash(
            (
                "Please select a "
                "shipping address."
            ),
            "danger"
        )

        return redirect(
            url_for("shop.checkout")
        )

    if not phone:
        flash(
            "Phone number is required.",
            "danger"
        )

        return redirect(
            url_for("shop.checkout")
        )

    try:
        # ====================================================
        # ONE TRANSACTION FOR THE COMPLETE CHECKOUT
        # ====================================================

        db.execute(
            "BEGIN IMMEDIATE"
        )

        user = db.execute(
            """
            SELECT
                id,
                name,
                email
            FROM users
            WHERE id = ?
            """,
            (session["user_id"],)
        ).fetchone()

        if user is None:
            raise ValueError(
                (
                    "Your account could "
                    "not be found."
                )
            )

        address = db.execute(
            """
            SELECT *
            FROM addresses
            WHERE id = ?
              AND user_id = ?
            """,
            (
                address_id,
                session["user_id"]
            )
        ).fetchone()

        if address is None:
            raise ValueError(
                "Invalid shipping address."
            )

        # ====================================================
        # STEP 29
        # Validate ALL cart items before changing anything.
        # ====================================================

        verified_items = []
        subtotal = 0.0

        for (
            book_id_text,
            quantity
        ) in raw_cart.items():

            book_id = int(
                book_id_text
            )

            quantity = int(
                quantity
            )

            if quantity <= 0:
                raise ValueError(
                    "Invalid cart quantity."
                )

            book = db.execute(
                """
                SELECT
                    id,
                    title,
                    price,
                    stock
                FROM books
                WHERE id = ?
                """,
                (book_id,)
            ).fetchone()

            if book is None:
                raise ValueError(
                    (
                        "A book in your cart "
                        "no longer exists."
                    )
                )

            if (
                int(book["stock"])
                < quantity
            ):
                raise ValueError(
                    (
                        f"'{book['title']}' "
                        "does not have enough "
                        "stock. No order was "
                        "created."
                    )
                )

            price = float(
                book["price"]
            )

            subtotal += (
                price * quantity
            )

            verified_items.append({
                "book_id":
                    book["id"],
                "title":
                    book["title"],
                "quantity":
                    quantity,
                "price":
                    price,
            })

        # ====================================================
        # REVALIDATE COUPON
        # ====================================================

        coupon_code = session.get(
            "coupon_code"
        )

        discount = 0.0

        if coupon_code:
            coupon = db.execute(
                """
                SELECT *
                FROM coupons
                WHERE code = ?
                  AND active = 1
                """,
                (coupon_code,)
            ).fetchone()

            if coupon:
                valid_coupon = True

                if coupon["expiry_date"]:
                    try:
                        valid_coupon = (
                            date.fromisoformat(
                                coupon[
                                    "expiry_date"
                                ]
                            )
                            >= date.today()
                        )

                    except ValueError:
                        valid_coupon = False

                if valid_coupon:
                    percent = float(
                        coupon["percent"]
                    )

                    if 0 <= percent <= 100:
                        discount = round(
                            subtotal
                            * percent
                            / 100,
                            2
                        )

        total_amount = round(
            max(
                0,
                subtotal - discount
            ),
            2
        )

        # ====================================================
        # STEP 28
        # COPY address text into the order.
        # ====================================================

        address_snapshot = (
            f"{address['line1']}, "
            f"{address['city']} - "
            f"{address['pincode']}"
        )

        cursor = db.execute(
            """
            INSERT INTO orders
            (
                user_id,
                customer_name,
                email,
                phone,
                address_snapshot,
                total_amount,
                discount_amount,
                coupon_code,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                user["name"],
                user["email"],
                phone,
                address_snapshot,
                total_amount,
                discount,
                coupon_code,
                "Placed"
            )
        )

        order_id = cursor.lastrowid

        # ====================================================
        # STEP 29 + STEP 34
        # Save every item, reduce stock and log stock.
        # ====================================================

        for item in verified_items:

            db.execute(
                """
                INSERT INTO order_items
                (
                    order_id,
                    book_id,
                    quantity,
                    price_at_purchase
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["book_id"],
                    item["quantity"],
                    item["price"]
                )
            )

            update = db.execute(
                """
                UPDATE books
                SET stock = stock - ?
                WHERE id = ?
                  AND stock >= ?
                """,
                (
                    item["quantity"],
                    item["book_id"],
                    item["quantity"]
                )
            )

            if update.rowcount != 1:
                raise ValueError(
                    (
                        f"'{item['title']}' "
                        "became unavailable. "
                        "No order was created."
                    )
                )

            db.execute(
                """
                INSERT INTO stock_log
                (
                    book_id,
                    change,
                    reason,
                    user_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    item["book_id"],
                    -item["quantity"],
                    "purchase",
                    session["user_id"]
                )
            )

        # ONE COMMIT.
        db.commit()

    except ValueError as error:
        db.rollback()

        flash(
            str(error),
            "danger"
        )

        return redirect(
            url_for("shop.cart")
        )

    except sqlite3.Error:
        db.rollback()

        flash(
            (
                "Checkout could not "
                "be completed."
            ),
            "danger"
        )

        return redirect(
            url_for("shop.checkout")
        )

    # Clear cart only AFTER successful commit.
    session["cart"] = {}

    session.pop(
        "coupon_code",
        None
    )

    session.pop(
        "discount_amount",
        None
    )

    session[
        "last_order_id"
    ] = order_id

    session.modified = True

    return redirect(
        url_for(
            "shop.order_confirmation",
            order_id=order_id
        )
    )


# ============================================================
# ORDER DETAILS
# ============================================================

@shop_bp.route(
    "/order/<int:order_id>"
)
@login_required
def order_confirmation(order_id):
    db = get_db()

    order = db.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()

    if order is None:
        abort(404)

    user = current_user()

    if (
        order["user_id"]
        != session["user_id"]
        and user["role"]
        not in {
            "staff",
            "admin"
        }
    ):
        abort(403)

    items = db.execute(
        """
        SELECT
            oi.*,
            b.title,
            b.author,
            b.cover_image,

            (
                oi.quantity
                * oi.price_at_purchase
            ) AS subtotal

        FROM order_items oi

        JOIN books b
            ON b.id =
               oi.book_id

        WHERE oi.order_id = ?

        ORDER BY oi.id
        """,
        (order_id,)
    ).fetchall()

    return render_template(
        "order_confirmation.html",
        order=order,
        items=items
    )


# ============================================================
# ORDER HISTORY
# ============================================================

@shop_bp.route("/orders")
@login_required
def order_history():
    db = get_db()

    orders = db.execute(
        """
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    return render_template(
        "orders.html",
        orders=orders
    )


# ============================================================
# STEP 35
# CANCEL ORDER
# ============================================================

@shop_bp.route(
    "/orders/<int:order_id>/cancel",
    methods=["POST"]
)
@login_required
def cancel_order(order_id):
    db = get_db()

    try:
        db.execute(
            "BEGIN IMMEDIATE"
        )

        order = db.execute(
            """
            SELECT *
            FROM orders
            WHERE id = ?
              AND user_id = ?
            """,
            (
                order_id,
                session["user_id"]
            )
        ).fetchone()

        if order is None:
            db.rollback()
            abort(404)

        if order["status"] != "Placed":
            db.rollback()

            flash(
                (
                    "Only orders with status "
                    "'Placed' can be cancelled."
                ),
                "danger"
            )

            return redirect(
                url_for(
                    "shop.order_history"
                )
            )

        update = db.execute(
            """
            UPDATE orders
            SET status = 'Cancelled'
            WHERE id = ?
              AND user_id = ?
              AND status = 'Placed'
            """,
            (
                order_id,
                session["user_id"]
            )
        )

        if update.rowcount != 1:
            raise ValueError(
                (
                    "This order cannot "
                    "be cancelled."
                )
            )

        items = db.execute(
            """
            SELECT
                book_id,
                quantity
            FROM order_items
            WHERE order_id = ?
            """,
            (order_id,)
        ).fetchall()

        for item in items:

            db.execute(
                """
                UPDATE books
                SET stock = stock + ?
                WHERE id = ?
                """,
                (
                    item["quantity"],
                    item["book_id"]
                )
            )

            db.execute(
                """
                INSERT INTO stock_log
                (
                    book_id,
                    change,
                    reason,
                    user_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    item["book_id"],
                    item["quantity"],
                    "cancelled_order",
                    session["user_id"]
                )
            )

        db.commit()

    except ValueError as error:
        db.rollback()

        flash(
            str(error),
            "danger"
        )

        return redirect(
            url_for(
                "shop.order_history"
            )
        )

    except Exception:
        db.rollback()
        raise

    flash(
        (
            "Order cancelled. "
            "Stock has been restored."
        ),
        "success"
    )

    return redirect(
        url_for(
            "shop.order_history"
        )
    )