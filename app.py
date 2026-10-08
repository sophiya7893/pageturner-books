from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    Response,
    abort
)

import sqlite3
import os
import csv
import io

from datetime import date
from pathlib import Path
from functools import wraps

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "pageturner.db"

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

ADMIN_EMAIL = os.environ.get(
    "ADMIN_EMAIL",
    "admin@pageturner.local"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "ChangeThisPassword123!"
)


# =========================================================
# DATABASE
# =========================================================
# =========================================================
# DATABASE
# =========================================================

def get_db():

    db = sqlite3.connect(
        DATABASE
    )

    db.row_factory = sqlite3.Row

    db.execute(
        "PRAGMA foreign_keys = ON"
    )

    db.execute(
        "PRAGMA busy_timeout = 5000"
    )

    return db


def init_db():

    db = get_db()

    # -----------------------------------------------------
    # CREATE TABLES
    # -----------------------------------------------------

    schema_file = BASE_DIR / "schema.sql"

    if schema_file.exists():

        with open(
            schema_file,
            "r",
            encoding="utf-8"
        ) as f:

            db.executescript(
                f.read()
            )


    # -----------------------------------------------------
    # SEED BOOKS
    # -----------------------------------------------------

    book_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM books
        """
    ).fetchone()["count"]

    if book_count == 0:

        seed_file = BASE_DIR / "seed.sql"

        if seed_file.exists():

            with open(
                seed_file,
                "r",
                encoding="utf-8"
            ) as f:

                db.executescript(
                    f.read()
                )


    # -----------------------------------------------------
    # COUPONS
    # -----------------------------------------------------

    db.execute(
        """
        INSERT INTO coupons
        (
            code,
            percent,
            expiry_date,
            active
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(code)
        DO UPDATE SET
            percent = excluded.percent,
            expiry_date = excluded.expiry_date,
            active = excluded.active
        """,
        (
            "WELCOME10",
            10,
            "2099-12-31",
            1
        )
    )

    db.execute(
        """
        INSERT INTO coupons
        (
            code,
            percent,
            expiry_date,
            active
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(code)
        DO UPDATE SET
            percent = excluded.percent,
            expiry_date = excluded.expiry_date,
            active = excluded.active
        """,
        (
            "BOOK20",
            20,
            "2099-12-31",
            1
        )
    )


    # -----------------------------------------------------
    # ADMIN
    # -----------------------------------------------------

    admin = db.execute(
        """
        SELECT id
        FROM admins
        WHERE email = ?
        """,
        (ADMIN_EMAIL,)
    ).fetchone()

    if not admin:

        password_hash = generate_password_hash(
            ADMIN_PASSWORD
        )

        db.execute(
            """
            INSERT INTO admins
            (
                email,
                password_hash
            )
            VALUES (?, ?)
            """,
            (
                ADMIN_EMAIL,
                password_hash
            )
        )


    db.commit()

    db.close()
# =========================================================
# USER HELPERS
# =========================================================

def get_current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    db = get_db()

    user = db.execute(
        """
        SELECT id, name, email
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    db.close()

    return user


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:
            flash(
                "Please login to continue.",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if not session.get("admin_id"):
            return redirect(
                url_for("admin_login")
            )

        return view(*args, **kwargs)

    return wrapped_view


# =========================================================
# TEMPLATE VARIABLES
# =========================================================

@app.context_processor
def inject_user():

    cart = session.get(
        "cart",
        {}
    )

    total_cart_quantity = 0

    for value in cart.values():
        try:
            total_cart_quantity += int(value)
        except (ValueError, TypeError):
            pass

    return {
        "current_user": get_current_user(),
        "cart_count": total_cart_quantity,
        "admin_logged_in": bool(
            session.get("admin_id")
        )
    }


# =========================================================
# HOME
# SEARCH + CATEGORY + SORT + PAGINATION
# =========================================================

@app.route("/")
def home():

    db = get_db()

    q = request.args.get(
        "q",
        ""
    ).strip()

    if not q:
        q = request.args.get(
            "search",
            ""
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
        page = int(
            request.args.get(
                "page",
                1
            )
        )
    except ValueError:
        page = 1

    if page < 1:
        page = 1

    per_page = 8

    conditions = []
    params = []

    if q:
        conditions.append(
            """
            (
                title LIKE ?
                OR author LIKE ?
            )
            """
        )

        search_value = f"%{q}%"

        params.extend([
            search_value,
            search_value
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
            + " AND ".join(conditions)
        )

    allowed_sort = {
        "title_asc": "title ASC",
        "title_desc": "title DESC",
        "price_asc": "price ASC",
        "price_desc": "price DESC"
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

    if page > total_pages:
        page = total_pages

    offset = (
        page - 1
    ) * per_page

    books = db.execute(
        f"""
        SELECT *
        FROM books
        {where_sql}
        ORDER BY {order_by}
        LIMIT ?
        OFFSET ?
        """,
        params + [
            per_page,
            offset
        ]
    ).fetchall()

    # IMPORTANT:
    # Convert sqlite3.Row objects into strings.
    categories = [
        row["category"]
        for row in db.execute(
            """
            SELECT DISTINCT category
            FROM books
            ORDER BY category
            """
        ).fetchall()
    ]

    db.close()

    return render_template(
        "home.html",
        books=books,
        categories=categories,
        q=q,
        search=q,
        selected_category=selected_category,
        sort=sort,
        page=page,
        total_pages=total_pages,
        total_books=total_books
    )


# =========================================================
# BOOK API
# =========================================================

@app.route("/api/books")
def api_books():

    db = get_db()

    q = request.args.get(
        "q",
        ""
    ).strip()

    if q:
        search_value = f"%{q}%"

        books = db.execute(
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
                search_value,
                search_value
            )
        ).fetchall()

    else:
        books = db.execute(
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

    db.close()

    return jsonify([
        dict(book)
        for book in books
    ])


# =========================================================
# BOOK DETAILS
# =========================================================

@app.route("/book/<int:book_id>")
def book_detail(book_id):

    db = get_db()

    book = db.execute(
        """
        SELECT
            b.*,
            COUNT(r.id) AS review_count,
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

    if not book:
        db.close()
        abort(404)

    reviews = db.execute(
        """
        SELECT
            r.*,
            u.name
        FROM reviews r
        LEFT JOIN users u
            ON u.id = r.user_id
        WHERE r.book_id = ?
        ORDER BY r.created_at DESC
        """,
        (book_id,)
    ).fetchall()

    db.close()

    return render_template(
        "book_detail.html",
        book=book,
        reviews=reviews
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

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

        if not name:
            flash(
                "Name is required.",
                "danger"
            )
            return render_template(
                "register.html"
            )

        if not email:
            flash(
                "Email is required.",
                "danger"
            )
            return render_template(
                "register.html"
            )

        if not password:
            flash(
                "Password is required.",
                "danger"
            )
            return render_template(
                "register.html"
            )

        if len(password) < 6:
            flash(
                "Password must contain at least 6 characters.",
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
            db.close()

            flash(
                "An account with this email already exists.",
                "danger"
            )

            return render_template(
                "register.html"
            )

        password_hash = generate_password_hash(
            password
        )

        db.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password_hash
            )
            VALUES (?, ?, ?)
            """,
            (
                name,
                email,
                password_hash
            )
        )

        db.commit()
        db.close()

        flash(
            "Registration successful. Please login.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not email or not password:
            flash(
                "Email and password are required.",
                "danger"
            )

            return render_template(
                "login.html"
            )

        db = get_db()

        user = db.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        db.close()

        if (
            user
            and check_password_hash(
                user["password_hash"],
                password
            )
        ):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]

            flash(
                "Login successful.",
                "success"
            )

            return redirect(
                url_for("home")
            )

        flash(
            "Invalid email or password.",
            "danger"
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.pop(
        "user_id",
        None
    )

    session.pop(
        "user_name",
        None
    )

    session.pop(
        "user_email",
        None
    )

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("home")
    )


# =========================================================
# REVIEWS
# =========================================================

@app.route(
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
        rating = int(rating_text)
    except ValueError:
        flash(
            "Rating must be a number from 1 to 5.",
            "danger"
        )

        return redirect(
            url_for(
                "book_detail",
                book_id=book_id
            )
        )

    if rating < 1 or rating > 5:
        flash(
            "Rating must be between 1 and 5.",
            "danger"
        )

        return redirect(
            url_for(
                "book_detail",
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
                "book_detail",
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

    if not book:
        db.close()
        abort(404)

    db.execute(
        """
        INSERT INTO reviews
        (
            user_id,
            book_id,
            rating,
            comment
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            session["user_id"],
            book_id,
            rating,
            comment
        )
    )

    db.commit()
    db.close()

    flash(
        "Your review was added.",
        "success"
    )

    return redirect(
        url_for(
            "book_detail",
            book_id=book_id
        )
    )


# =========================================================
# CART HELPERS
# =========================================================

def get_cart():

    cart = session.get(
        "cart",
        {}
    )

    clean_cart = {}

    for book_id, quantity in cart.items():

        try:
            book_id = str(
                int(book_id)
            )

            quantity = int(
                quantity
            )

        except (ValueError, TypeError):
            continue

        if quantity > 0:
            clean_cart[book_id] = quantity

    return clean_cart


def save_cart(cart):

    session["cart"] = cart
    session.modified = True


def get_cart_items():

    cart = get_cart()

    if not cart:
        return [], 0

    db = get_db()

    items = []
    total = 0

    for book_id, quantity in cart.items():

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

        if not book:
            continue

        if quantity <= 0:
            continue

        if quantity > book["stock"]:
            quantity = book["stock"]

        if quantity <= 0:
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
            "price": book["price"],
            "stock": book["stock"],
            "description": book["description"],
            "cover_image": book["cover_image"],
            "quantity": quantity,
            "subtotal": subtotal
        })

        total += subtotal

    db.close()

    return items, total


# =========================================================
# ADD TO CART
# =========================================================

@app.route(
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
    except ValueError:
        quantity = 0

    if quantity <= 0:

        message = (
            "Quantity must be greater than zero."
        )

        if request.headers.get(
            "X-Requested-With"
        ) == "XMLHttpRequest":

            return jsonify({
                "success": False,
                "message": message
            }), 400

        flash(
            message,
            "danger"
        )

        return redirect(
            url_for("home")
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

    db.close()

    if not book:
        abort(404)

    if book["stock"] <= 0:

        message = (
            f"'{book['title']}' is currently sold out."
        )

        if request.headers.get(
            "X-Requested-With"
        ) == "XMLHttpRequest":

            return jsonify({
                "success": False,
                "message": message
            }), 400

        flash(
            message,
            "danger"
        )

        return redirect(
            url_for("home")
        )

    cart = get_cart()

    current_quantity = cart.get(
        str(book_id),
        0
    )

    new_quantity = (
        current_quantity
        + quantity
    )

    if new_quantity > book["stock"]:

        message = (
            f"Only {book['stock']} copies "
            f"of '{book['title']}' are available."
        )

        if request.headers.get(
            "X-Requested-With"
        ) == "XMLHttpRequest":

            return jsonify({
                "success": False,
                "message": message
            }), 400

        flash(
            message,
            "danger"
        )

        return redirect(
            url_for("home")
        )

    cart[str(book_id)] = new_quantity

    save_cart(cart)

    if request.headers.get(
        "X-Requested-With"
    ) == "XMLHttpRequest":

        return jsonify({
            "success": True,
            "message": "Book added to cart.",
            "cart_count": sum(
                cart.values()
            )
        })

    flash(
        "Book added to cart.",
        "success"
    )

    return redirect(
        url_for("home")
    )


# =========================================================
# API ADD TO CART
# =========================================================

@app.route(
    "/api/cart/add/<int:book_id>",
    methods=["POST"]
)
def api_add_to_cart(book_id):

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
        return jsonify({
            "success": False,
            "message": "Quantity must be greater than zero."
        }), 400

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

    db.close()

    if not book:
        return jsonify({
            "success": False,
            "message": "Book not found."
        }), 404

    cart = get_cart()

    current_quantity = cart.get(
        str(book_id),
        0
    )

    new_quantity = (
        current_quantity
        + quantity
    )

    if book["stock"] <= 0:
        return jsonify({
            "success": False,
            "message": "This book is sold out."
        }), 400

    if new_quantity > book["stock"]:
        return jsonify({
            "success": False,
            "message": (
                f"Only {book['stock']} copies are available."
            )
        }), 400

    cart[str(book_id)] = new_quantity

    save_cart(cart)

    return jsonify({
        "success": True,
        "message": "Book added to cart.",
        "cart_count": sum(
            cart.values()
        )
    })


# =========================================================
# CART
# =========================================================

@app.route("/cart")
def cart():

    items, total = get_cart_items()

    discount = session.get(
        "discount_amount",
        0
    )

    discount = min(
        float(discount or 0),
        float(total)
    )

    final_total = max(
        0,
        float(total) - discount
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


# =========================================================
# UPDATE CART
# =========================================================

@app.route(
    "/cart/update",
    methods=["POST"]
)
def update_cart():

    cart = get_cart()

    for key in list(cart.keys()):

        try:
            quantity = int(
                request.form.get(
                    f"quantity_{key}",
                    cart[key]
                )
            )
        except ValueError:
            quantity = 0

        if quantity <= 0:
            cart.pop(key, None)
        else:
            cart[key] = quantity

    save_cart(cart)

    flash(
        "Cart updated.",
        "success"
    )

    return redirect(
        url_for("cart")
    )


# =========================================================
# REMOVE CART ITEM
# =========================================================

@app.route(
    "/cart/remove/<int:book_id>",
    methods=["POST", "GET"]
)
def remove_from_cart(book_id):

    cart = get_cart()

    cart.pop(
        str(book_id),
        None
    )

    save_cart(cart)

    flash(
        "Book removed from cart.",
        "success"
    )

    return redirect(
        url_for("cart")
    )


# =========================================================
# CLEAR CART
# =========================================================

@app.route(
    "/cart/clear",
    methods=["POST", "GET"]
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
        url_for("cart")
    )


# =========================================================
# COUPON
# =========================================================

@app.route(
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
            url_for("cart")
        )

    items, total = get_cart_items()

    if not items:
        flash(
            "Your cart is empty.",
            "warning"
        )

        return redirect(
            url_for("cart")
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

    db.close()

    if not coupon:
        session.pop(
            "coupon_code",
            None
        )

        session.pop(
            "discount_amount",
            None
        )

        flash(
            "Invalid or inactive coupon code.",
            "danger"
        )

        return redirect(
            url_for("cart")
        )

    if coupon["expiry_date"]:

        try:
            expiry = date.fromisoformat(
                coupon["expiry_date"]
            )

            if expiry < date.today():

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
                    url_for("cart")
                )

        except ValueError:
            pass

    percent = float(
        coupon["percent"]
    )

    discount = (
        float(total)
        * percent
        / 100
    )

    session["coupon_code"] = code
    session["discount_amount"] = round(
        discount,
        2
    )

    session.modified = True

    flash(
        f"Coupon {code} applied successfully.",
        "success"
    )

    return redirect(
        url_for("cart")
    )


# =========================================================
# REMOVE COUPON
# =========================================================

@app.route(
    "/cart/coupon/remove",
    methods=["POST", "GET"]
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
        url_for("cart")
    )


# =========================================================
# WISHLIST
# =========================================================

@app.route("/wishlist")
@login_required
def wishlist():

    db = get_db()

    books = db.execute(
        """
        SELECT
            b.*
        FROM wishlist w
        JOIN books b
            ON b.id = w.book_id
        WHERE w.user_id = ?
        ORDER BY w.created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    db.close()

    return render_template(
        "wishlist.html",
        books=books
    )


@app.route(
    "/wishlist/toggle/<int:book_id>",
    methods=["POST"]
)
@login_required
def toggle_wishlist(book_id):

    db = get_db()

    book = db.execute(
        """
        SELECT
            id,
            title
        FROM books
        WHERE id = ?
        """,
        (book_id,)
    ).fetchone()

    if not book:
        db.close()

        flash(
            "Book not found.",
            "danger"
        )

        return redirect(
            url_for("home")
        )

    existing = db.execute(
        """
        SELECT
            id
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
    db.close()

    flash(
        message,
        category
    )

    return redirect(
        request.referrer
        or url_for("home")
    )
    
# =========================================================
# CHECKOUT
# =========================================================

@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    items, total = get_cart_items()

    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart"))

    discount = session.get("discount_amount", 0)
    coupon_code = session.get("coupon_code")

    discount = min(float(discount or 0), float(total))
    final_total = max(0, float(total) - discount)

    if request.method == "GET":
        return render_template(
            "checkout.html",
            items=items,
            total=total,
            discount=discount,
            final_total=final_total,
            coupon_code=coupon_code
        )

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    print("CHECKOUT FORM:")
    print("name =", name)
    print("email =", email)
    print("phone =", phone)
    print("address =", address)

    if not name:
        flash("Name is required.", "danger")
        return redirect(url_for("checkout"))

    if not email:
        flash("Email is required.", "danger")
        return redirect(url_for("checkout"))

    if not phone:
        flash("Phone number is required.", "danger")
        return redirect(url_for("checkout"))

    if not address:
        flash("Address is required.", "danger")
        return redirect(url_for("checkout"))

    db = get_db()

    try:

        db.execute("BEGIN IMMEDIATE")

        verified_items = []

        for item in items:

            book_id = item["id"]
            quantity = item["quantity"]

            book = db.execute(
                "SELECT * FROM books WHERE id = ?",
                (book_id,)
            ).fetchone()

            if not book:
                raise ValueError(
                    "One of the books in your cart no longer exists."
                )

            result = db.execute(
                """
                UPDATE books
                SET stock = stock - ?
                WHERE id = ?
                  AND stock >= ?
                """,
                (
                    quantity,
                    book_id,
                    quantity
                )
            )

            if result.rowcount != 1:
                raise ValueError(
                    f"Sorry, '{book['title']}' just sold out or does not have enough stock."
                )

            verified_items.append({
                "book": book,
                "quantity": quantity,
                "subtotal": float(book["price"]) * quantity
            })

        verified_total = sum(
            item["subtotal"]
            for item in verified_items
        )

        verified_discount = min(
            float(discount or 0),
            float(verified_total)
        )

        verified_final_total = max(
            0,
            verified_total - verified_discount
        )

        cursor = db.execute(
            """
            INSERT INTO orders
            (
                user_id,
                customer_name,
                email,
                phone,
                address,
                total_amount,
                discount_amount,
                coupon_code,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.get("user_id"),
                name,
                email,
                phone,
                address,
                verified_final_total,
                verified_discount,
                coupon_code,
                "Placed"
            )
        )

        order_id = cursor.lastrowid

        for item in verified_items:

            db.execute(
                """
                INSERT INTO order_items
                (
                    order_id,
                    book_id,
                    quantity,
                    price
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["book"]["id"],
                    item["quantity"],
                    item["book"]["price"]
                )
            )

        db.commit()

        print("ORDER CREATED:", order_id)

    except ValueError as error:

        db.rollback()
        db.close()

        print("CHECKOUT VALIDATION ERROR:", error)

        flash(str(error), "danger")

        return redirect(url_for("cart"))

    except sqlite3.Error as error:

        db.rollback()
        db.close()

        print("CHECKOUT DATABASE ERROR:", error)

        flash(
            "Checkout could not be completed. Please try again.",
            "danger"
        )

        return redirect(url_for("checkout"))

    except Exception as error:

        db.rollback()
        db.close()

        print("CHECKOUT ERROR:", error)

        flash(
            "An unexpected error occurred while placing your order.",
            "danger"
        )

        return redirect(url_for("checkout"))

    db.close()

    session["cart"] = {}
    session.pop("coupon_code", None)
    session.pop("discount_amount", None)

    session["last_order_id"] = order_id

    session.modified = True

    print("REDIRECTING TO ORDER:", order_id)

    return redirect(
        url_for(
            "order_confirmation",
            order_id=order_id
        )
    )


# =========================================================
# ORDER CONFIRMATION
# =========================================================

@app.route(
    "/order/<int:order_id>"
)
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

    if not order:
        db.close()
        abort(404)

    # Customers can only see their own order.
    if session.get("user_id"):

        if (
            order["user_id"] is not None
            and order["user_id"] != session["user_id"]
            and not session.get("admin_id")
        ):
            db.close()
            abort(403)

    items = db.execute(
        """
        SELECT
            oi.*,
            b.title,
            b.author,
            b.cover_image
        FROM order_items oi
        JOIN books b
            ON b.id = oi.book_id
        WHERE oi.order_id = ?
        """,
        (order_id,)
    ).fetchall()

    db.close()

    return render_template(
        "order_confirmation.html",
        order=order,
        items=items
    )


# =========================================================
# CUSTOMER ORDERS
# =========================================================

@app.route("/orders")
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
        (
            session["user_id"],
        )
    ).fetchall()

    db.close()

    return render_template(
        "orders.html",
        orders=orders
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        db = get_db()

        admin = db.execute(
            """
            SELECT *
            FROM admins
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        db.close()

        if (
            admin
            and check_password_hash(
                admin["password_hash"],
                password
            )
        ):

            session["admin_id"] = admin["id"]
            session["admin_email"] = admin["email"]

            flash(
                "Admin login successful.",
                "success"
            )

            return redirect(
                url_for("admin_dashboard")
            )

        flash(
            "Invalid admin email or password.",
            "danger"
        )

    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_id",
        None
    )

    session.pop(
        "admin_email",
        None
    )

    flash(
        "Admin logged out.",
        "success"
    )

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
@admin_required
def admin_dashboard():

    db = get_db()

    book_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM books
        """
    ).fetchone()["count"]

    order_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        """
    ).fetchone()["count"]

    user_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM users
        """
    ).fetchone()["count"]

    revenue = db.execute(
        """
        SELECT COALESCE(
            SUM(total_amount),
            0
        ) AS total
        FROM orders
        """
    ).fetchone()["total"]

    recent_orders = db.execute(
        """
        SELECT *
        FROM orders
        ORDER BY created_at DESC
        LIMIT 10
        """
    ).fetchall()

    db.close()

    return render_template(
        "admin.html",
        book_count=book_count,
        order_count=order_count,
        user_count=user_count,
        revenue=revenue,
        recent_orders=recent_orders
    )


# =========================================================
# ADMIN BOOK ADD
# =========================================================

@app.route(
    "/admin/book/add",
    methods=["GET", "POST"]
)
@admin_required
def admin_add_book():

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        author = request.form.get(
            "author",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        cover_image = request.form.get(
            "cover_image",
            ""
        ).strip()

        try:
            price = float(
                request.form.get(
                    "price",
                    0
                )
            )
        except ValueError:
            price = -1

        try:
            stock = int(
                request.form.get(
                    "stock",
                    0
                )
            )
        except ValueError:
            stock = -1

        if not title or not author or not category:
            flash(
                "Title, author and category are required.",
                "danger"
            )

            return render_template(
                "admin_book_form.html",
                book=None
            )

        if price < 0:
            flash(
                "Price cannot be negative.",
                "danger"
            )

            return render_template(
                "admin_book_form.html",
                book=None
            )

        if stock < 0:
            flash(
                "Stock cannot be negative.",
                "danger"
            )

            return render_template(
                "admin_book_form.html",
                book=None
            )

        db = get_db()

        db.execute(
            """
            INSERT INTO books
            (
                title,
                author,
                category,
                price,
                stock,
                description,
                cover_image
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                author,
                category,
                price,
                stock,
                description,
                cover_image
            )
        )

        db.commit()
        db.close()

        flash(
            "Book added successfully.",
            "success"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template(
        "admin_book_form.html",
        book=None
    )


# =========================================================
# ADMIN BOOK EDIT
# =========================================================

@app.route(
    "/admin/book/edit/<int:book_id>",
    methods=["GET", "POST"]
)
@admin_required
def admin_edit_book(book_id):

    db = get_db()

    book = db.execute(
        """
        SELECT *
        FROM books
        WHERE id = ?
        """,
        (book_id,)
    ).fetchone()

    if not book:
        db.close()
        abort(404)

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        author = request.form.get(
            "author",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        cover_image = request.form.get(
            "cover_image",
            ""
        ).strip()

        try:
            price = float(
                request.form.get(
                    "price",
                    0
                )
            )
        except ValueError:
            price = -1

        try:
            stock = int(
                request.form.get(
                    "stock",
                    0
                )
            )
        except ValueError:
            stock = -1

        if (
            not title
            or not author
            or not category
        ):
            db.close()

            flash(
                "Title, author and category are required.",
                "danger"
            )

            return render_template(
                "admin_book_form.html",
                book=book
            )

        if price < 0 or stock < 0:
            db.close()

            flash(
                "Price and stock cannot be negative.",
                "danger"
            )

            return render_template(
                "admin_book_form.html",
                book=book
            )

        db.execute(
            """
            UPDATE books
            SET
                title = ?,
                author = ?,
                category = ?,
                price = ?,
                stock = ?,
                description = ?,
                cover_image = ?
            WHERE id = ?
            """,
            (
                title,
                author,
                category,
                price,
                stock,
                description,
                cover_image,
                book_id
            )
        )

        db.commit()
        db.close()

        flash(
            "Book updated successfully.",
            "success"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    db.close()

    return render_template(
        "admin_book_form.html",
        book=book
    )


# =========================================================
# ADMIN BOOK DELETE
# =========================================================

@app.route(
    "/admin/book/delete/<int:book_id>",
    methods=["POST"]
)
@admin_required
def admin_delete_book(book_id):

    db = get_db()

    try:

        db.execute(
            """
            DELETE FROM books
            WHERE id = ?
            """,
            (book_id,)
        )

        db.commit()

        flash(
            "Book deleted successfully.",
            "success"
        )

    except sqlite3.IntegrityError:

        db.rollback()

        flash(
            "This book cannot be deleted because it is used in an order or review.",
            "danger"
        )

    finally:
        db.close()

    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# ADMIN ORDERS
# =========================================================

@app.route("/admin/orders")
@admin_required
def admin_orders():

    db = get_db()

    orders = db.execute(
        """
        SELECT *
        FROM orders
        ORDER BY created_at DESC
        """
    ).fetchall()

    db.close()

    return render_template(
        "admin_orders.html",
        orders=orders
    )


# =========================================================
# ADMIN ORDER STATUS
# =========================================================

@app.route(
    "/admin/orders/<int:order_id>/status",
    methods=["POST"]
)
@admin_required
def admin_update_order_status(order_id):

    status = request.form.get(
        "status",
        ""
    ).strip()

    allowed_statuses = {
        "Placed",
        "Packed",
        "Delivered"
    }

    if status not in allowed_statuses:

        flash(
            "Invalid order status.",
            "danger"
        )

        return redirect(
            url_for("admin_orders")
        )

    db = get_db()

    db.execute(
        """
        UPDATE orders
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            order_id
        )
    )

    db.commit()
    db.close()

    flash(
        "Order status updated.",
        "success"
    )

    return redirect(
        url_for("admin_orders")
    )


# =========================================================
# ADMIN REPORT
# =========================================================

@app.route("/admin/report")
@admin_required
def admin_report():
    db = get_db()

    # Total orders
    total_orders = db.execute("""
        SELECT COUNT(*) AS count
        FROM orders
    """).fetchone()["count"]

    # Total sales
    total_sales = db.execute("""
        SELECT COALESCE(SUM(total_amount), 0) AS total
        FROM orders
    """).fetchone()["total"]

    # Total books sold
    books_sold = db.execute("""
        SELECT COALESCE(SUM(quantity), 0) AS total
        FROM order_items
    """).fetchone()["total"]

    # Top selling books
    top_books = db.execute("""
        SELECT
            b.title,
            b.author,
            SUM(oi.quantity) AS quantity_sold,
            SUM(oi.quantity * oi.price) AS revenue
        FROM order_items oi
        JOIN books b ON b.id = oi.book_id
        JOIN orders o ON o.id = oi.order_id
        GROUP BY oi.book_id
        ORDER BY quantity_sold DESC
        LIMIT 10
    """).fetchall()

    db.close()

    return render_template(
        "report.html",
        total_orders=total_orders,
        total_sales=total_sales,
        books_sold=books_sold,
        top_books=top_books
    )


# =========================================================
# CSV EXPORT
# =========================================================

@app.route("/admin/export")
@admin_required
def admin_export():

    db = get_db()

    orders = db.execute(
        """
        SELECT
            o.id,
            o.customer_name,
            o.email,
            o.phone,
            o.address,
            o.total_amount,
            o.discount_amount,
            o.coupon_code,
            o.status,
            o.created_at
        FROM orders o
        ORDER BY o.created_at DESC
        """
    ).fetchall()

    db.close()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Order ID",
        "Customer Name",
        "Email",
        "Phone",
        "Address",
        "Total",
        "Discount",
        "Coupon",
        "Status",
        "Created At"
    ])

    for order in orders:

        writer.writerow([
            order["id"],
            order["customer_name"],
            order["email"],
            order["phone"],
            order["address"],
            order["total_amount"],
            order["discount_amount"],
            order["coupon_code"],
            order["status"],
            order["created_at"]
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )

    response.headers[
        "Content-Disposition"
    ] = "attachment; filename=orders.csv"

    return response


# =========================================================
# 404 ERROR
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    try:
        return render_template(
            "404.html"
        ), 404
    except Exception:
        return (
            "<h1>404 - Page Not Found</h1>",
            404
        )


# =========================================================
# 500 ERROR
# =========================================================

@app.errorhandler(500)
def internal_server_error(error):

    try:
        return render_template(
            "500.html"
        ), 500
    except Exception:
        return (
            "<h1>500 - Internal Server Error</h1>",
            500
        )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )