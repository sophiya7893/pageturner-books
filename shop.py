import sqlite3
from datetime import datetime, timedelta, timezone


from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from db import get_db
from security import login_required
from order_rules import ALLOWED_STATUS_MOVES
from werkzeug.security import generate_password_hash
from werkzeug.exceptions import HTTPException

def _step57_admin_required():
    role = str(session.get("role", "")).lower()

    if role not in {"admin", "staff"}:
        flash("You must be an admin to access this page.", "danger")
        abort(403)
# ============================================================
# SHOP BLUEPRINT
# ============================================================

shop_bp = Blueprint(
    "shop",
    __name__
)
# ============================================================
# CUSTOMER REGISTRATION
# ============================================================

@shop_bp.route(
    "/register",
    methods=["GET", "POST"],
)
def register():

    # --------------------------------------------------------
    # ALREADY LOGGED IN
    # --------------------------------------------------------

    if session.get("user_id"):

        return redirect(
            url_for("shop.home")
        )

    # --------------------------------------------------------
    # SHOW REGISTRATION PAGE
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "register.html"
        )

    # --------------------------------------------------------
    # READ FORM DATA
    # --------------------------------------------------------

    name = request.form.get(
        "name",
        "",
    ).strip()

    email = request.form.get(
        "email",
        "",
    ).strip().lower()

    password = request.form.get(
        "password",
        "",
    )

    confirm_password = request.form.get(
        "confirm_password",
        "",
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not name:

        flash(
            "Please enter your name.",
            "danger",
        )

        return render_template(
            "register.html"
        ), 400

    if not email:

        flash(
            "Please enter your email.",
            "danger",
        )

        return render_template(
            "register.html"
        ), 400

    if len(password) < 8:

        flash(
            "Password must contain at least 8 characters.",
            "danger",
        )

        return render_template(
            "register.html"
        ), 400

    if password != confirm_password:

        flash(
            "Passwords do not match.",
            "danger",
        )

        return render_template(
            "register.html"
        ), 400

    db = get_db()

    # --------------------------------------------------------
    # CHECK EXISTING EMAIL
    # --------------------------------------------------------

    existing_user = db.execute(
        """
        SELECT id
        FROM users
        WHERE LOWER(email) = LOWER(?)
        LIMIT 1
        """,
        (email,),
    ).fetchone()

    if existing_user is not None:

        flash(
            "An account already exists with that email.",
            "danger",
        )

        return render_template(
            "register.html"
        ), 400

    # --------------------------------------------------------
    # HASH PASSWORD
    # --------------------------------------------------------

    password_hash = generate_password_hash(
        password
    )

    # --------------------------------------------------------
    # CREATE CUSTOMER ACCOUNT
    # --------------------------------------------------------

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
                password_hash,
                "customer",
            ),
        )

        db.commit()

    except sqlite3.IntegrityError:

        db.rollback()

        flash(
            "An account already exists with that email.",
            "danger",
        )

        return render_template(
            "register.html"
        ), 400

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    flash(
        "Registration successful. Please log in.",
        "success",
    )

    return redirect(
        url_for("auth.login")
    )

# ============================================================
# STEP 46
# MONEY HELPER
# ============================================================

def money(paise):
    """
    Convert integer paise to display money.

    Example:
        19950 -> ₹199.50

    Money is never converted to float.
    """

    paise = int(
        paise or 0
    )

    sign = (
        "-"
        if paise < 0
        else ""
    )

    paise = abs(
        paise
    )

    rupees, remainder = divmod(
        paise,
        100
    )

    return (
        f"{sign}₹{rupees:,}."
        f"{remainder:02d}"
    )


shop_bp.add_app_template_filter(
    money,
    "money"
)


def coupon_discount_paise(db, code, subtotal_paise, user_id=None, items=None):
    """Validate coupon rules and return integer-paise discount plus a clear error."""
    code = str(code or "").strip().upper()
    subtotal_paise = max(0, int(subtotal_paise or 0))
    if not code:
        return 0, None
    row = db.execute("SELECT * FROM coupons WHERE UPPER(code)=? LIMIT 1", (code,)).fetchone()
    if row is None:
        return 0, "That coupon code was not found."
    keys = set(row.keys())
    def get(name, default=None):
        return row[name] if name in keys else default
    active = get("is_active", get("active", 1))
    if not bool(active):
        return 0, "This coupon is deactivated."
    expiry = get("end_date") or get("expires_at") or get("expiry_date")
    if expiry:
        expiry_text = str(expiry).replace("T", " ")
        now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        if len(expiry_text) == 10:
            expiry_text += " 23:59"
        if expiry_text[:16] < now_text:
            return 0, "This coupon has expired."
    start = get("start_date")
    if start and str(start)[:10] > datetime.now(timezone.utc).strftime("%Y-%m-%d"):
        return 0, "This coupon is not active yet."
    minimum = int(get("min_order_paise", 0) or get("minimum_order_paise", 0) or 0)
    if subtotal_paise < minimum:
        return 0, f"Your order must be at least {money(minimum)} to use this coupon."
    usage_limit = get("usage_limit")
    if usage_limit is not None:
        uses = db.execute("SELECT COUNT(*) AS n FROM coupon_uses WHERE coupon_id=?", (row["id"],)).fetchone()["n"] if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='coupon_uses'").fetchone() else int(get("used_count", 0) or 0)
        uses = max(int(uses or 0), int(get("used_count", 0) or 0))
        if uses >= int(usage_limit):
            return 0, "This coupon has reached its usage limit."
    if user_id and bool(get("one_use_per_customer", 0)):
        if db.execute("SELECT 1 FROM coupon_uses WHERE coupon_id=? AND user_id=? LIMIT 1", (row["id"], user_id)).fetchone():
            return 0, "You have already used this coupon. Each customer can use it once."
    eligible_subtotal = subtotal_paise
    category_id = get("category_id")
    if category_id:
        cart_items = items or []
        eligible_subtotal = 0
        for item in cart_items:
            book_id = int(item["id"] if hasattr(item, "keys") and "id" in item.keys() else item.get("id"))
            quantity = int(item["quantity"])
            price = int(item["price_paise"])
            match = db.execute("SELECT 1 FROM book_categories WHERE book_id=? AND category_id=? LIMIT 1", (book_id, int(category_id))).fetchone() if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='book_categories'").fetchone() else None
            if not match:
                legacy = db.execute("SELECT category FROM books WHERE id=?", (book_id,)).fetchone()
                if legacy and str(legacy["category"] or "").strip().lower() == str(category_id).lower():
                    match = True
            if match:
                eligible_subtotal += quantity * price
        if eligible_subtotal <= 0:
            return 0, "This coupon applies only to a specific category, which is not in your cart."
    discount_type = str(get("discount_type", "percentage") or "percentage").lower()
    discount_value = get("discount_value", 0)
    if discount_type == "fixed" and int(discount_value or 0) > 0:
        discount = int(discount_value)
    else:
        percent = int(discount_value or 0)
        if percent <= 0:
            percent = int(get("percent", 0) or 0)
        if percent <= 0 or percent > 100:
            return 0, "This coupon has an invalid discount value."
        discount = (eligible_subtotal * percent + 50) // 100
    maximum = get("max_discount_paise")
    if maximum is not None:
        discount = min(discount, int(maximum))
    discount = min(eligible_subtotal, max(0, discount))
    if discount <= 0:
        return 0, "This coupon does not apply to the current cart."
    return discount, None


@shop_bp.route("/cart/coupon", methods=["POST"])
def apply_coupon():
    if request.form.get("remove_coupon"):
        session.pop("coupon_code", None)
        flash("Coupon removed.", "success")
        return redirect(url_for("shop.cart"))
    code = request.form.get("coupon_code", "").strip().upper()
    if not code:
        flash("Enter a coupon code or use Remove coupon.", "danger")
        return redirect(url_for("shop.cart"))
    _, error = coupon_discount_paise(get_db(), code, get_cart_items()[1], session.get("user_id"), get_cart_items()[0])
    if error:
        flash(error, "danger")
    else:
        session["coupon_code"] = code
        flash("Coupon applied successfully.", "success")
    return redirect(url_for("shop.cart"))


# ============================================================
# DATE / TIME HELPER
# STEP 54
# ============================================================

def utc_db_timestamp(value=None):

    if value is None:

        value = datetime.now(
            timezone.utc
        )

    return (
        value
        .astimezone(
            timezone.utc
        )
        .strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )


# ============================================================
# CART HELPERS
# STEP 53
# ============================================================

def get_cart():
    """
    Guest:
        Flask session cart.

    Logged-in customer:
        cart_items database table.
    """

    user_id = session.get(
        "user_id"
    )

    # --------------------------------------------------------
    # LOGGED-IN USER
    # --------------------------------------------------------

    if user_id:

        rows = get_db().execute(
            """
            SELECT
                book_id,
                quantity

            FROM cart_items

            WHERE user_id = ?
            """,
            (
                user_id,
            )
        ).fetchall()

        return {
            str(row["book_id"]):
                int(row["quantity"])

            for row in rows
        }

    # --------------------------------------------------------
    # GUEST
    # --------------------------------------------------------

    raw_cart = session.get(
        "cart",
        {}
    )

    clean_cart = {}

    if not isinstance(
        raw_cart,
        dict
    ):

        return clean_cart

    for book_id, quantity in raw_cart.items():

        try:

            clean_id = str(
                int(book_id)
            )

            clean_quantity = int(
                quantity
            )

        except (
            ValueError,
            TypeError
        ):

            continue

        if clean_quantity > 0:

            clean_cart[
                clean_id
            ] = clean_quantity

    return clean_cart


# ============================================================
# SAVE CART
# STEP 53
# ============================================================

def save_cart(cart_data):

    user_id = session.get(
        "user_id"
    )

    # --------------------------------------------------------
    # GUEST
    # --------------------------------------------------------

    if not user_id:

        session["cart"] = (
            cart_data
        )

        session.modified = True

        return

    # --------------------------------------------------------
    # LOGGED-IN CUSTOMER
    # --------------------------------------------------------

    db = get_db()

    db.execute(
        """
        DELETE FROM cart_items

        WHERE user_id = ?
        """,
        (
            user_id,
        )
    )

    for book_id, quantity in cart_data.items():

        quantity = int(
            quantity
        )

        if quantity <= 0:
            continue

        db.execute(
            """
            INSERT INTO cart_items
            (
                user_id,
                book_id,
                quantity
            )

            VALUES (?, ?, ?)
            """,
            (
                user_id,
                int(book_id),
                quantity,
            )
        )

    db.commit()


# ============================================================
# CLEAR CART
# ============================================================

def clear_saved_cart():

    user_id = session.get(
        "user_id"
    )

    if user_id:

        db = get_db()

        db.execute(
            """
            DELETE FROM cart_items

            WHERE user_id = ?
            """,
            (
                user_id,
            )
        )

        db.execute(
            """
            DELETE FROM reservations

            WHERE user_id = ?
            """,
            (
                user_id,
            )
        )

        db.commit()

    session["cart"] = {}

    session.modified = True


# ============================================================
# STEP 54
# ACTIVE RESERVED QUANTITY
# ============================================================

def active_reserved_quantity(
    db,
    book_id,
    exclude_user_id=None
):

    now = utc_db_timestamp()

    if exclude_user_id is None:

        row = db.execute(
            """
            SELECT
                COALESCE(
                    SUM(quantity),
                    0
                ) AS qty

            FROM reservations

            WHERE book_id = ?
              AND expires_at > ?
            """,
            (
                book_id,
                now,
            )
        ).fetchone()

    else:

        row = db.execute(
            """
            SELECT
                COALESCE(
                    SUM(quantity),
                    0
                ) AS qty

            FROM reservations

            WHERE book_id = ?
              AND expires_at > ?
              AND user_id != ?
            """,
            (
                book_id,
                now,
                exclude_user_id,
            )
        ).fetchone()

    return int(
        row["qty"] or 0
    )


# ============================================================
# STEP 54
# AVAILABLE STOCK
# ============================================================

def available_stock(
    db,
    book_id,
    stock,
    exclude_user_id=None
):

    reserved = active_reserved_quantity(
        db,
        book_id,
        exclude_user_id,
    )

    return max(
        0,
        int(stock) - reserved,
    )


# ============================================================
# STEP 54
# RESERVE CUSTOMER CART
# ============================================================

def reserve_cart_for_user(
    db,
    user_id,
    cart_data
):

    expires_at = utc_db_timestamp(
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=10
        )
    )

    now = utc_db_timestamp()

    # --------------------------------------------------------
    # REMOVE OLD RESERVATIONS FOR THIS USER
    # --------------------------------------------------------

    db.execute(
        """
        DELETE FROM reservations

        WHERE user_id = ?
        """,
        (
            user_id,
        )
    )

    # --------------------------------------------------------
    # RESERVE CART
    # --------------------------------------------------------

    for book_id_text, quantity in cart_data.items():

        book_id = int(
            book_id_text
        )

        quantity = int(
            quantity
        )

        if quantity <= 0:
            continue

        book = db.execute(
            """
            SELECT
                id,
                title,
                stock

            FROM books

            WHERE id = ?
            """,
            (
                book_id,
            )
        ).fetchone()

        if book is None:

            raise ValueError(
                "A book in your cart "
                "no longer exists."
            )

        other = db.execute(
            """
            SELECT
                COALESCE(
                    SUM(quantity),
                    0
                ) AS qty

            FROM reservations

            WHERE book_id = ?
              AND expires_at > ?
              AND user_id != ?
            """,
            (
                book_id,
                now,
                user_id,
            )
        ).fetchone()

        other_reserved = int(
            other["qty"] or 0
        )

        available = max(
            0,
            int(book["stock"])
            - other_reserved,
        )

        if quantity > available:

            raise ValueError(
                (
                    f"Only {available} copies of "
                    f"'{book['title']}' are "
                    "currently available."
                )
            )

        db.execute(
            """
            INSERT INTO reservations
            (
                user_id,
                book_id,
                quantity,
                expires_at
            )

            VALUES (?, ?, ?, ?)

            ON CONFLICT(
                user_id,
                book_id
            )

            DO UPDATE SET
                quantity =
                    excluded.quantity,

                expires_at =
                    excluded.expires_at
            """,
            (
                user_id,
                book_id,
                quantity,
                expires_at,
            )
        )

    return expires_at


# ============================================================
# STEP 48
# GET BOOK CATEGORIES
# ============================================================

def get_book_categories(
    db,
    book_id
):

    return db.execute(
        """
        SELECT
            c.id,
            c.name

        FROM categories AS c

        JOIN book_categories AS bc
            ON bc.category_id = c.id

        WHERE bc.book_id = ?

        ORDER BY
            c.name COLLATE NOCASE
        """,
        (
            book_id,
        )
    ).fetchall()


# ============================================================
# STEP 48
# GET BOOK TAGS
# ============================================================

def get_book_tags(
    db,
    book_id
):

    return db.execute(
        """
        SELECT
            t.id,
            t.name

        FROM tags AS t

        JOIN book_tags AS bt
            ON bt.tag_id = t.id

        WHERE bt.book_id = ?

        ORDER BY
            t.name COLLATE NOCASE
        """,
        (
            book_id,
        )
    ).fetchall()


# ============================================================
# STEP 46 + STEP 53
# GET CART ITEMS
# ============================================================

def get_cart_items():

    cart_data = get_cart()

    if not cart_data:

        return (
            [],
            0,
        )

    db = get_db()

    items = []

    total_paise = 0

    for book_id, quantity in cart_data.items():

        book = db.execute(
            """
            SELECT
                id,
                title,
                author,
                price_paise,
                stock,
                description,
                cover_image

            FROM books

            WHERE id = ?
            """,
            (
                int(book_id),
            )
        ).fetchone()

        if book is None:
            continue

        quantity = int(
            quantity
        )

        price_paise = int(
            book["price_paise"]
        )

        subtotal_paise = (
            price_paise
            * quantity
        )

        categories = get_book_categories(
            db,
            book["id"],
        )

        tags = get_book_tags(
            db,
            book["id"],
        )

        items.append(
            {
                "id":
                    book["id"],

                "title":
                    book["title"],

                "author":
                    book["author"],

                "price_paise":
                    price_paise,

                "stock":
                    int(
                        book["stock"]
                    ),

                "description":
                    book["description"],

                "cover_image":
                    book["cover_image"],

                "quantity":
                    quantity,

                "subtotal_paise":
                    subtotal_paise,

                "categories":
                    categories,

                "tags":
                    tags,
            }
        )

        total_paise += (
            subtotal_paise
        )

    return (
        items,
        total_paise,
    )


# ============================================================
# HOME
# STEPS 49, 50, 51, 54, 55
# ============================================================

@shop_bp.route("/")
def home():

    db = get_db()

    user_id = session.get(
        "user_id"
    )

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    q = request.args.get(
        "q",
        ""
    ).strip()

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    # Support one or many selected categories. Repeated query parameters
    # (category=Python&category=Science) are preferred; comma-separated values
    # remain accepted for older bookmarks.
    raw_categories = request.args.getlist("category")
    selected_categories = []
    for raw_category in raw_categories:
        selected_categories.extend(
            part.strip() for part in str(raw_category).split(",") if part.strip()
        )
    # De-duplicate while preserving the user's selection order.
    selected_categories = list(dict.fromkeys(selected_categories))
    selected_category = selected_categories[0] if len(selected_categories) == 1 else ""

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    sort = request.args.get(
        "sort",
        "title_asc"
    ).strip()

    # --------------------------------------------------------
    # PAGE
    # --------------------------------------------------------

    try:

        page = int(
            request.args.get(
                "page",
                1
            )
        )

    except (
        ValueError,
        TypeError
    ):

        page = 1

    if page < 1:
        page = 1

    per_page = 8

    conditions = []

    params = []

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    if q:

        like_term = (
            "%"
            + q
            + "%"
        )

        conditions.append("""(
            b.title LIKE ? OR b.author LIKE ? OR EXISTS (
                SELECT 1 FROM book_tags bt JOIN tags t ON t.id=bt.tag_id
                WHERE bt.book_id=b.id AND t.name LIKE ?
            )
        )""")
        params.extend([like_term, like_term, like_term])

    # --------------------------------------------------------
    # CATEGORY FILTER
    # --------------------------------------------------------

    if selected_categories:
        placeholders = ",".join("?" for _ in selected_categories)
        conditions.append(f"""b.id IN (
            SELECT bc_filter.book_id FROM book_categories AS bc_filter
            JOIN categories AS c_filter ON c_filter.id=bc_filter.category_id
            WHERE c_filter.name IN ({placeholders})
            GROUP BY bc_filter.book_id
            HAVING COUNT(DISTINCT c_filter.id)=?
        )""")
        params.extend(selected_categories)
        params.append(len(selected_categories))

    if conditions:

        where_sql = (
            "WHERE "
            + " AND ".join(
                conditions
            )
        )

    else:

        where_sql = ""

    # --------------------------------------------------------
    # SAFE SORT WHITELIST
    # --------------------------------------------------------

    sort_options = {

        "title_asc":
            "b.title COLLATE NOCASE ASC",

        "title_desc":
            "b.title COLLATE NOCASE DESC",

        "price_asc":
            "b.price_paise ASC",

        "price_desc":
            "b.price_paise DESC",

        "newest":
            "b.created_at DESC, b.id DESC",

        "rating_desc":
            """
            average_rating DESC,
            review_count DESC,
            b.title COLLATE NOCASE ASC
            """
    }

    order_sql = sort_options.get(sort, sort_options["title_asc"])
    order_params = []
    if q and sort == "title_asc":
        # Step 73: rank title matches above author matches, and author above tags.
        # Keep all user-provided values parameterized; only the fixed SQL expression is interpolated.
        order_sql = """CASE
            WHEN b.title LIKE ? THEN 3
            WHEN b.author LIKE ? THEN 2
            WHEN EXISTS (
                SELECT 1 FROM book_tags bt_rank
                JOIN tags t_rank ON t_rank.id = bt_rank.tag_id
                WHERE bt_rank.book_id = b.id AND t_rank.name LIKE ?
            ) THEN 1 ELSE 0 END DESC, b.title COLLATE NOCASE ASC"""
        like_term = "%" + q + "%"
        order_params.extend([like_term, like_term, like_term])

    # --------------------------------------------------------
    # COUNT
    # --------------------------------------------------------

    count_row = db.execute(
        f"""
        SELECT
            COUNT(*) AS total

        FROM books AS b

        {where_sql}
        """,
        params,
    ).fetchone()

    total_books = int(
        count_row["total"]
        or 0
    )

    if total_books == 0:

        total_pages = 1

    else:

        total_pages = (
            total_books
            + per_page
            - 1
        ) // per_page

    if page > total_pages:

        page = total_pages

    offset = (
        page - 1
    ) * per_page

    # --------------------------------------------------------
    # BOOKS + SQL RATING
    # --------------------------------------------------------

    rows = db.execute(
        f"""
        SELECT
            b.id,
            b.title,
            b.author,
            b.price_paise,
            b.stock,
            b.description,
            b.cover_image,
            b.created_at,

            COALESCE(
                AVG(r.rating),
                0
            ) AS average_rating,

            COUNT(
                r.id
            ) AS review_count

        FROM books AS b

        LEFT JOIN reviews AS r
            ON r.book_id = b.id

        {where_sql}

        GROUP BY
            b.id

        ORDER BY
            {order_sql}

        LIMIT ?
        OFFSET ?
        """,
        (
            *params,
            *order_params,
            per_page,
            offset,
        )
    ).fetchall()

    # --------------------------------------------------------
    # STEP 54
    # CUSTOMER-VISIBLE AVAILABLE STOCK
    # --------------------------------------------------------

    books = []

    for row in rows:

        book = dict(
            row
        )

        book["available_stock"] = (
            available_stock(
                db,
                row["id"],
                row["stock"],
                exclude_user_id=user_id,
            )
        )

        books.append(
            book
        )

    # --------------------------------------------------------
    # CATEGORIES
    # --------------------------------------------------------

    categories = db.execute(
        """
        SELECT
            id,
            name

        FROM categories

        ORDER BY
            name COLLATE NOCASE
        """
    ).fetchall()

    # --------------------------------------------------------
    # WISHLIST IDS
    # --------------------------------------------------------

    wishlist_ids = set()

    if user_id:

        wishlist_rows = db.execute(
            """
            SELECT
                book_id

            FROM wishlist

            WHERE user_id = ?
            """,
            (
                user_id,
            )
        ).fetchall()

        wishlist_ids = {
            row["book_id"]
            for row in wishlist_rows
        }

    return render_template(
        "home.html",
        books=books,
        categories=categories,
        selected_category=selected_category,
        selected_categories=selected_categories,
        q=q,
        sort=sort,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_books=total_books,
        wishlist_ids=wishlist_ids,
    )


# ============================================================
# BOOK DETAILS
# STEPS 51 + 54 + 55
# ============================================================

@shop_bp.route(
    "/book/<int:book_id>"
)
def book_detail(book_id):

    db = get_db()

    user_id = session.get(
        "user_id"
    )

    book_row = db.execute(
        """
        SELECT
            b.id,
            b.title,
            b.author,
            b.price_paise,
            b.stock,
            b.description,
            b.cover_image,
            b.created_at,

            COALESCE(
                AVG(r.rating),
                0
            ) AS average_rating,

            COUNT(
                r.id
            ) AS review_count

        FROM books AS b

        LEFT JOIN reviews AS r
            ON r.book_id = b.id

        WHERE b.id = ?

        GROUP BY
            b.id
        """,
        (
            book_id,
        )
    ).fetchone()

    if book_row is None:
        abort(404)

    book = dict(
        book_row
    )

    book["available_stock"] = (
        available_stock(
            db,
            book["id"],
            book["stock"],
            exclude_user_id=user_id,
        )
    )

    categories = get_book_categories(
        db,
        book_id,
    )

    tags = get_book_tags(
        db,
        book_id,
    )

    # --------------------------------------------------------
    # REVIEWS
    #
    # LEFT JOIN preserves historical reviews when user_id
    # becomes NULL.
    # --------------------------------------------------------

    reviews = db.execute(
        """
        SELECT
            r.id,
            r.rating,
            r.comment,
            r.created_at,

            COALESCE(
                u.name,
                r.name
            ) AS user_name

        FROM reviews AS r

        LEFT JOIN users AS u
            ON u.id = r.user_id

        WHERE r.book_id = ?

        ORDER BY
            r.created_at DESC,
            r.id DESC
        """,
        (
            book_id,
        )
    ).fetchall()

    can_review = False

    already_reviewed = False

    in_wishlist = False

    if user_id:

        # ----------------------------------------------------
        # CANCELLED ORDERS DO NOT QUALIFY
        # ----------------------------------------------------

        bought = db.execute(
            """
            SELECT
                1

            FROM orders AS o

            JOIN order_items AS oi
                ON oi.order_id = o.id

            WHERE o.user_id = ?
              AND oi.book_id = ?
              AND o.status != 'Cancelled'

            LIMIT 1
            """,
            (
                user_id,
                book_id,
            )
        ).fetchone()

        existing_review = db.execute(
            """
            SELECT
                id

            FROM reviews

            WHERE user_id = ?
              AND book_id = ?

            LIMIT 1
            """,
            (
                user_id,
                book_id,
            )
        ).fetchone()

        already_reviewed = (
            existing_review
            is not None
        )

        can_review = (
            bought is not None
            and
            not already_reviewed
        )

        wishlist_row = db.execute(
            """
            SELECT
                id

            FROM wishlist

            WHERE user_id = ?
              AND book_id = ?

            LIMIT 1
            """,
            (
                user_id,
                book_id,
            )
        ).fetchone()

        in_wishlist = (
            wishlist_row
            is not None
        )

    return render_template(
        "book_detail.html",
        book=book,
        available_stock=book["available_stock"],
        categories=categories,
        tags=tags,
        reviews=reviews,
        can_review=can_review,
        already_reviewed=already_reviewed,
        in_wishlist=in_wishlist,
    )


# ============================================================
# STEP 52
# TOGGLE WISHLIST
# ============================================================

@shop_bp.route(
    "/wishlist/toggle/<int:book_id>",
    methods=["POST"]
)
@login_required
def toggle_wishlist(book_id):

    db = get_db()

    user_id = session.get(
        "user_id"
    )

    book = db.execute(
        """
        SELECT
            id,
            title

        FROM books

        WHERE id = ?
        """,
        (
            book_id,
        )
    ).fetchone()

    if book is None:
        abort(404)

    existing = db.execute(
        """
        SELECT
            id

        FROM wishlist

        WHERE user_id = ?
          AND book_id = ?

        LIMIT 1
        """,
        (
            user_id,
            book_id,
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
                user_id,
                book_id,
            )
        )

        db.commit()

        flash(
            (
                f"'{book['title']}' "
                "was removed from your wishlist."
            ),
            "success"
        )

    else:

        try:

            db.execute(
                """
                INSERT OR IGNORE INTO wishlist
                (
                    user_id,
                    book_id
                )

                VALUES (?, ?)
                """,
                (
                    user_id,
                    book_id,
                )
            )

            db.commit()

            flash(
                (
                    f"'{book['title']}' "
                    "was added to your wishlist."
                ),
                "success"
            )

        except sqlite3.IntegrityError:

            db.rollback()

            flash(
                "That book is already "
                "in your wishlist.",
                "info"
            )

    return redirect(
        request.referrer
        or url_for(
            "shop.wishlist"
        )
    )


# ============================================================
# STEP 52
# WISHLIST PAGE
# ============================================================

@shop_bp.route(
    "/wishlist"
)
@login_required
def wishlist():

    db = get_db()

    user_id = session.get(
        "user_id"
    )

    rows = db.execute(
        """
        SELECT
            b.id,
            b.title,
            b.author,
            b.price_paise,
            b.stock,
            b.description,
            b.cover_image,

            w.created_at AS
                wishlist_created_at,

            COALESCE(
                AVG(r.rating),
                0
            ) AS average_rating,

            COUNT(
                r.id
            ) AS review_count

        FROM wishlist AS w

        JOIN books AS b
            ON b.id = w.book_id

        LEFT JOIN reviews AS r
            ON r.book_id = b.id

        WHERE w.user_id = ?

        GROUP BY
            w.id,
            b.id

        ORDER BY
            w.created_at DESC,
            w.id DESC
        """,
        (
            user_id,
        )
    ).fetchall()

    books = []

    for row in rows:

        book = dict(
            row
        )

        book["available_stock"] = (
            available_stock(
                db,
                row["id"],
                row["stock"],
                exclude_user_id=user_id,
            )
        )

        books.append(
            book
        )

    return render_template(
        "wishlist.html",
        books=books,
    )


# ============================================================
# STEP 55
# ADD REVIEW
# ============================================================

@shop_bp.route(
    "/book/<int:book_id>/review",
    methods=["POST"]
)
@login_required
def add_review(book_id):

    db = get_db()

    user_id = session.get(
        "user_id"
    )

    book = db.execute(
        """
        SELECT
            id,
            title

        FROM books

        WHERE id = ?
        """,
        (
            book_id,
        )
    ).fetchone()

    if book is None:
        abort(404)

    # --------------------------------------------------------
    # REVIEW NAME SNAPSHOT
    # --------------------------------------------------------

    user = db.execute(
        """
        SELECT
            id,
            name

        FROM users

        WHERE id = ?
        """,
        (
            user_id,
        )
    ).fetchone()

    if user is None:
        abort(403)

    # --------------------------------------------------------
    # INPUT
    # --------------------------------------------------------

    try:

        rating = int(
            request.form.get(
                "rating",
                ""
            )
        )

    except (
        ValueError,
        TypeError
    ):

        rating = 0

    comment = request.form.get(
        "comment",
        ""
    ).strip()

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if rating < 1 or rating > 5:

        flash(
            "Please choose a rating from 1 to 5.",
            "danger"
        )

        return redirect(
            url_for(
                "shop.book_detail",
                book_id=book_id,
            )
        )

    if not comment:

        flash(
            "Please enter a review comment.",
            "danger"
        )

        return redirect(
            url_for(
                "shop.book_detail",
                book_id=book_id,
            )
        )

    # --------------------------------------------------------
    # PURCHASE VERIFICATION
    # --------------------------------------------------------

    bought = db.execute(
        """
        SELECT
            1

        FROM orders AS o

        JOIN order_items AS oi
            ON oi.order_id = o.id

        WHERE o.user_id = ?
          AND oi.book_id = ?
          AND o.status != 'Cancelled'

        LIMIT 1
        """,
        (
            user_id,
            book_id,
        )
    ).fetchone()

    if bought is None:

        flash(
            (
                "You can review this book "
                "only after purchasing it."
            ),
            "danger"
        )

        return redirect(
            url_for(
                "shop.book_detail",
                book_id=book_id,
            )
        )

    # --------------------------------------------------------
    # INSERT
    # --------------------------------------------------------

    try:

        db.execute(
            """
            INSERT INTO reviews
            (
                book_id,
                user_id,
                name,
                rating,
                comment
            )

            VALUES (?, ?, ?, ?, ?)
            """,
            (
                book_id,
                user_id,
                user["name"],
                rating,
                comment,
            )
        )

        db.commit()

    except sqlite3.IntegrityError:

        db.rollback()

        flash(
            (
                "You have already reviewed "
                "this book."
            ),
            "danger"
        )

        return redirect(
            url_for(
                "shop.book_detail",
                book_id=book_id,
            )
        )

    flash(
        (
            f"Your review for "
            f"'{book['title']}' was added."
        ),
        "success"
    )

    return redirect(
        url_for(
            "shop.book_detail",
            book_id=book_id,
        )
    )


# ============================================================
# STEP 51 + STEP 53
# ADD TO CART
# ============================================================

@shop_bp.route(
    "/cart/add/<int:book_id>",
    methods=["POST"]
)
def add_to_cart(book_id):

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
        (
            book_id,
        )
    ).fetchone()

    if book is None:
        abort(404)

    try:

        quantity = int(
            request.form.get(
                "quantity",
                1
            )
        )

    except (
        ValueError,
        TypeError
    ):

        quantity = 1

    if quantity < 1:
        quantity = 1

    if int(
        book["stock"]
    ) <= 0:

        flash(
            (
                f"'{book['title']}' "
                "is out of stock."
            ),
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "shop.home"
            )
        )

    user_id = session.get(
        "user_id"
    )

    available = available_stock(
        db,
        book_id,
        int(book["stock"]),
        exclude_user_id=user_id,
    )

    if available <= 0:

        flash(
            (
                f"'{book['title']}' is currently "
                "reserved by another customer."
            ),
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "shop.home"
            )
        )

    cart_data = get_cart()

    key = str(
        book_id
    )

    current_quantity = int(
        cart_data.get(
            key,
            0
        )
    )

    new_quantity = (
        current_quantity
        + quantity
    )

    if new_quantity > available:

        flash(
            (
                f"Only {available} copies of "
                f"'{book['title']}' are "
                "currently available."
            ),
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "shop.home"
            )
        )

    # --------------------------------------------------------
    # GUEST
    # --------------------------------------------------------

    if not user_id:

        cart_data[
            key
        ] = new_quantity

        save_cart(
            cart_data
        )

    # --------------------------------------------------------
    # LOGGED-IN
    # --------------------------------------------------------

    else:

        db.execute(
            """
            INSERT INTO cart_items
            (
                user_id,
                book_id,
                quantity
            )

            VALUES (?, ?, ?)

            ON CONFLICT(
                user_id,
                book_id
            )

            DO UPDATE SET
                quantity =
                    excluded.quantity,

                updated_at =
                    CURRENT_TIMESTAMP
            """,
            (
                user_id,
                book_id,
                new_quantity,
            )
        )

        db.commit()

    flash(
        (
            f"'{book['title']}' "
            "was added to your cart."
        ),
        "success"
    )

    return redirect(
        request.referrer
        or url_for(
            "shop.cart"
        )
    )


# ============================================================
# STEP 53
# CART PAGE
# ============================================================

@shop_bp.route(
    "/cart"
)
def cart():

    items, total_paise = (
        get_cart_items()
    )

    db = get_db()

    user_id = session.get(
        "user_id"
    )

    display_items = []

    for item in items:

        item_data = dict(
            item
        )

        item_data["available_stock"] = (
            available_stock(
                db,
                item["id"],
                item["stock"],
                exclude_user_id=user_id,
            )
        )

        display_items.append(
            item_data
        )

    coupon_code = session.get("coupon_code", "")
    discount_paise, coupon_error = coupon_discount_paise(db, coupon_code, total_paise, user_id, items)
    if coupon_error:
        flash(coupon_error, "warning")
        session.pop("coupon_code", None)
        coupon_code = ""
        discount_paise = 0
    subtotal_paise = int(total_paise)
    default_address = db.execute("SELECT pincode FROM addresses WHERE user_id=? ORDER BY is_default DESC, id DESC LIMIT 1", (user_id,)).fetchone() if user_id else None
    amounts = calculate_order_money(db, items, discount_paise, default_address["pincode"] if default_address else "")

    return render_template(
        "cart.html",
        items=display_items,
        subtotal_paise=amounts["subtotal_paise"],
        discount_paise=amounts["discount_paise"],
        shipping_paise=amounts["shipping_paise"],
        tax_paise=amounts["tax_paise"],
        coupon_code=coupon_code,
        total_paise=amounts["total_paise"],
    )


# ============================================================
# STEP 51 + STEP 53
# UPDATE CART
# ============================================================

@shop_bp.route(
    "/cart/update/<int:book_id>",
    methods=["POST"]
)
def update_cart(book_id):

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
        (
            book_id,
        )
    ).fetchone()

    if book is None:
        abort(404)

    try:

        quantity = int(
            request.form.get(
                "quantity",
                1
            )
        )

    except (
        ValueError,
        TypeError
    ):

        flash(
            "Please enter a valid quantity.",
            "danger"
        )

        return redirect(
            url_for(
                "shop.cart"
            )
        )

    if quantity <= 0:

        return remove_cart_item(
            book_id
        )

    user_id = session.get(
        "user_id"
    )

    available = available_stock(
        db,
        book_id,
        int(book["stock"]),
        exclude_user_id=user_id,
    )

    if quantity > available:

        flash(
            (
                f"Only {available} copies of "
                f"'{book['title']}' are "
                "currently available."
            ),
            "danger"
        )

        return redirect(
            url_for(
                "shop.cart"
            )
        )

    if not user_id:

        cart_data = get_cart()

        cart_data[
            str(book_id)
        ] = quantity

        save_cart(
            cart_data
        )

    else:

        db.execute(
            """
            INSERT INTO cart_items
            (
                user_id,
                book_id,
                quantity
            )

            VALUES (?, ?, ?)

            ON CONFLICT(
                user_id,
                book_id
            )

            DO UPDATE SET
                quantity =
                    excluded.quantity,

                updated_at =
                    CURRENT_TIMESTAMP
            """,
            (
                user_id,
                book_id,
                quantity,
            )
        )

        db.commit()

    flash(
        (
            f"Quantity for "
            f"'{book['title']}' was updated."
        ),
        "success"
    )

    return redirect(
        url_for(
            "shop.cart"
        )
    )


# ============================================================
# STEP 53
# REMOVE FROM CART
# ============================================================

@shop_bp.route(
    "/cart/remove/<int:book_id>",
    methods=["POST"]
)
def remove_from_cart(book_id):

    return remove_cart_item(
        book_id
    )


# ============================================================
# STEP 53
# REMOVE CART HELPER
# ============================================================

def remove_cart_item(book_id):

    db = get_db()

    user_id = session.get(
        "user_id"
    )

    book = db.execute(
        """
        SELECT
            id,
            title

        FROM books

        WHERE id = ?
        """,
        (
            book_id,
        )
    ).fetchone()

    if not user_id:

        cart_data = get_cart()

        cart_data.pop(
            str(book_id),
            None,
        )

        save_cart(
            cart_data
        )

    else:

        db.execute(
            """
            DELETE FROM cart_items

            WHERE user_id = ?
              AND book_id = ?
            """,
            (
                user_id,
                book_id,
            )
        )

        db.execute(
            """
            DELETE FROM reservations

            WHERE user_id = ?
              AND book_id = ?
            """,
            (
                user_id,
                book_id,
            )
        )

        db.commit()

    if book:

        flash(
            (
                f"'{book['title']}' "
                "was removed from your cart."
            ),
            "success"
        )

    else:

        flash(
            (
                "The item was removed "
                "from your cart."
            ),
            "success"
        )

    return redirect(
        url_for(
            "shop.cart"
        )
    )


# ============================================================
# STEP 53
# MERGE GUEST CART INTO DATABASE CART
# ============================================================

def merge_guest_cart(user_id):

    guest_cart = session.get(
        "cart",
        {}
    )

    if not isinstance(
        guest_cart,
        dict
    ):

        guest_cart = {}

    if not guest_cart:

        session["cart"] = {}

        session.modified = True

        return

    db = get_db()

    try:

        db.execute(
            "BEGIN IMMEDIATE"
        )

        for book_id_text, guest_quantity in guest_cart.items():

            try:

                book_id = int(
                    book_id_text
                )

                guest_quantity = int(
                    guest_quantity
                )

            except (
                ValueError,
                TypeError
            ):

                continue

            if guest_quantity <= 0:
                continue

            book = db.execute(
                """
                SELECT
                    id,
                    stock

                FROM books

                WHERE id = ?
                """,
                (
                    book_id,
                )
            ).fetchone()

            if book is None:
                continue

            existing = db.execute(
                """
                SELECT
                    quantity

                FROM cart_items

                WHERE user_id = ?
                  AND book_id = ?
                """,
                (
                    user_id,
                    book_id,
                )
            ).fetchone()

            database_quantity = (
                int(
                    existing["quantity"]
                )
                if existing
                else 0
            )

            reserved_by_others = (
                active_reserved_quantity(
                    db,
                    book_id,
                    exclude_user_id=user_id,
                )
            )

            available = max(
                0,
                int(book["stock"])
                - reserved_by_others,
            )

            merged_quantity = min(
                database_quantity
                + guest_quantity,
                available,
            )

            if merged_quantity <= 0:
                continue

            db.execute(
                """
                INSERT INTO cart_items
                (
                    user_id,
                    book_id,
                    quantity
                )

                VALUES (?, ?, ?)

                ON CONFLICT(
                    user_id,
                    book_id
                )

                DO UPDATE SET
                    quantity =
                        excluded.quantity,

                    updated_at =
                        CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    book_id,
                    merged_quantity,
                )
            )

        db.commit()

    except Exception:

        db.rollback()

        raise

    session["cart"] = {}

    session.modified = True


# ============================================================
# STEP 54
# CHECKOUT
# ============================================================

@shop_bp.route(
    "/checkout",
    methods=["GET"]
)
@login_required
def checkout():

    user_id = session.get(
        "user_id"
    )

    items, total_paise = (
        get_cart_items()
    )

    if not items:

        flash(
            "Your cart is empty.",
            "danger"
        )

        return redirect(
            url_for(
                "shop.cart"
            )
        )

    db = get_db()

    cart_data = {
        str(item["id"]):
            int(item["quantity"])

        for item in items
    }

    try:

        db.execute(
            "BEGIN IMMEDIATE"
        )

        expires_at = (
            reserve_cart_for_user(
                db,
                user_id,
                cart_data,
            )
        )

        db.commit()

    except ValueError as exc:

        db.rollback()

        flash(
            str(exc),
            "danger"
        )

        return redirect(
            url_for(
                "shop.cart"
            )
        )

    except Exception:

        db.rollback()

        raise

    addresses = db.execute(
        """
        SELECT
            id,
            label,
            line1,
            city,
            pincode,
            phone,
            is_default

        FROM addresses

        WHERE user_id = ?

        ORDER BY
            is_default DESC,
            id DESC
        """,
        (
            user_id,
        )
    ).fetchall()

    coupon_code = session.get("coupon_code", "")
    discount_paise, coupon_error = coupon_discount_paise(db, coupon_code, total_paise, user_id, items)
    if coupon_error:
        flash(coupon_error, "warning")
        session.pop("coupon_code", None)
        coupon_code = ""
        discount_paise = 0
    subtotal_paise = int(total_paise)
    selected_address_id = request.args.get("address_id", type=int)
    selected_address = next((a for a in addresses if selected_address_id and int(a["id"]) == selected_address_id), None)
    if selected_address is None:
        selected_address = next((a for a in addresses if int(a["is_default"] or 0)), addresses[0] if addresses else None)
    estimate = calculate_order_money(db, items, discount_paise, selected_address["pincode"] if selected_address else "")

    return render_template(
        "checkout.html",
        items=items,
        subtotal_paise=estimate["subtotal_paise"],
        discount_paise=estimate["discount_paise"],
        shipping_paise=estimate["shipping_paise"],
        tax_paise=estimate["tax_paise"],
        coupon_code=coupon_code,
        total_paise=estimate["total_paise"],
        addresses=addresses,
        selected_address_id=selected_address["id"] if selected_address else None,
        reservation_expires_at=expires_at,
    )


# ============================================================
# STEP 54
# VALIDATE CHECKOUT RESERVATIONS
# ============================================================

def validate_checkout_reservations(
    db,
    user_id,
    items
):

    now = utc_db_timestamp()

    for item in items:

        reservation = db.execute(
            """
            SELECT
                quantity,
                expires_at

            FROM reservations

            WHERE user_id = ?
              AND book_id = ?
              AND expires_at > ?

            LIMIT 1
            """,
            (
                user_id,
                item["id"],
                now,
            )
        ).fetchone()

        if reservation is None:

            raise ValueError(
                (
                    f"Your reservation for "
                    f"'{item['title']}' expired. "
                    "Please open checkout again."
                )
            )

        if (
            int(
                reservation["quantity"]
            )
            < int(
                item["quantity"]
            )
        ):

            raise ValueError(
                (
                    f"Your reservation for "
                    f"'{item['title']}' is no longer "
                    "large enough for this order."
                )
            )


# ============================================================
# STEP 51 + STEP 54
# FINAL STOCK REDUCTION
# ============================================================

def reduce_stock_for_order(
    db,
    items
):

    for item in items:

        update = db.execute(
            """
            UPDATE books

            SET stock =
                stock - ?

            WHERE id = ?
              AND stock >= ?
            """,
            (
                int(
                    item["quantity"]
                ),
                int(
                    item["id"]
                ),
                int(
                    item["quantity"]
                ),
            )
        )

        if update.rowcount != 1:

            raise ValueError(
                (
                    f"'{item['title']}' became "
                    "unavailable. "
                    "No order was created."
                )
            )


# ============================================================
# STEP 54
# RELEASE RESERVATIONS
# ============================================================

def release_user_reservations(
    db,
    user_id
):

    db.execute(
        """
        DELETE FROM reservations

        WHERE user_id = ?
        """,
        (
            user_id,
        )
    )


# ============================================================
# DATABASE COLUMN HELPER
# ============================================================

def table_columns(
    db,
    table_name
):

    rows = db.execute(
        f"""
        PRAGMA table_info(
            {table_name}
        )
        """
    ).fetchall()

    return {
        row["name"]:
            row

        for row in rows
    }
# ============================================================
# ORDER CONFIRMATION / ORDER DETAILS
# ============================================================

@shop_bp.route("/orders/<int:order_id>")
@login_required
def order_confirmation(order_id):

    user_id = session.get("user_id")
    db = get_db()

    # --------------------------------------------------------
    # GET ORDER
    #
    # IMPORTANT:
    # user_id is included in the WHERE clause so one customer
    # cannot open another customer's order by changing the URL.
    # --------------------------------------------------------

    order = db.execute(
        """
        SELECT
            id,
            user_id,
            customer_name,
            email,
            phone,
            address_snapshot,
            total_paise,
            discount_paise,
            subtotal_paise,
            shipping_paise,
            tax_paise,
            coupon_code,
            status,
            created_at

        FROM orders

        WHERE id = ?
          AND user_id = ?

        LIMIT 1
        """,
        (
            order_id,
            user_id,
        ),
    ).fetchone()

    # --------------------------------------------------------
    # ORDER NOT FOUND / NOT OWNED BY CURRENT USER
    # --------------------------------------------------------

    if order is None:

        flash(
            "Order not found.",
            "danger",
        )

        return redirect(
            url_for("shop.orders")
        )

    # --------------------------------------------------------
    # GET ORDER ITEMS
    # --------------------------------------------------------

    items = db.execute(
        """
        SELECT
            oi.id,
            oi.order_id,
            oi.book_id,
            oi.quantity,
            oi.price_paise,

            b.title,
            b.author,
            b.cover_image

        FROM order_items AS oi

        LEFT JOIN books AS b
            ON b.id = oi.book_id

        WHERE oi.order_id = ?

        ORDER BY oi.id ASC
        """,
        (
            order_id,
        ),
    ).fetchall()

    # --------------------------------------------------------
    # PREPARE ORDER ITEMS
    # --------------------------------------------------------

    order_items = []

    items_subtotal_paise = 0

    for item in items:

        item_data = dict(item)

        quantity = int(
            item["quantity"] or 0
        )

        price_paise = int(
            item["price_paise"] or 0
        )

        subtotal_paise = (
            quantity * price_paise
        )

        item_data["subtotal_paise"] = (
            subtotal_paise
        )

        items_subtotal_paise += (
            subtotal_paise
        )

        order_items.append(
            item_data
        )

    # --------------------------------------------------------
    # PREPARE ORDER DATA
    # --------------------------------------------------------

    order_data = dict(order)

    order_data["items"] = (
        order_items
    )

    order_data["items_subtotal_paise"] = (
        items_subtotal_paise
    )

    order_data["total_paise"] = int(
        order["total_paise"] or 0
    )

    order_data["discount_paise"] = int(
        order["discount_paise"] or 0
    )

    # --------------------------------------------------------
    # RENDER ORDER CONFIRMATION TEMPLATE
    # --------------------------------------------------------

    return render_template(
        "order_confirmation.html",
        order=order_data,
        items=order_items,
    )

# ============================================================
# STEP 51 + STEP 53 + STEP 54
# PLACE ORDER
# ============================================================

@shop_bp.route(
    "/checkout/place-order",
    methods=["POST"]
)
@login_required
def place_order():
    """Create an order safely, reduce stock, and clear the cart."""
    user_id = session.get("user_id")
    if not user_id:
        abort(403)

    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")

        user = db.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            raise ValueError("Please sign in again before placing your order.")

        items, total_paise = get_cart_items()
        if not items:
            raise ValueError("Your cart is empty.")

        address_id = request.form.get("address_id", type=int)
        address = None
        if address_id:
            address = db.execute(
                """
                SELECT label, line1, city, pincode, phone
                FROM addresses
                WHERE id = ? AND user_id = ?
                LIMIT 1
                """,
                (address_id, user_id),
            ).fetchone()
        if address is None:
            address = db.execute(
                """
                SELECT label, line1, city, pincode, phone
                FROM addresses
                WHERE user_id = ?
                ORDER BY is_default DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        if address is None:
            raise ValueError("Please add and select a delivery address before checkout.")

        customer_name = request.form.get("customer_name", "").strip() or user["name"]
        phone = request.form.get("phone", "").strip() or str(address["phone"] or "").strip()
        if not customer_name:
            raise ValueError("Please enter your name.")
        if not phone or not phone.isdigit() or len(phone) != 10:
            raise ValueError("Please enter a valid 10-digit phone number.")

        validate_checkout_reservations(db, user_id, items)
        reduce_stock_for_order(db, items)

        address_snapshot = ", ".join(
            str(address[key]).strip()
            for key in ("label", "line1", "city", "pincode")
            if address[key] is not None and str(address[key]).strip()
        )
        subtotal_paise = int(total_paise)
        coupon_code = session.get("coupon_code", "")
        discount_paise, coupon_error = coupon_discount_paise(db, coupon_code, subtotal_paise, user_id, items)
        if coupon_error:
            raise ValueError(coupon_error)
        amounts = calculate_order_money(db, items, discount_paise, address["pincode"])
        subtotal_paise = amounts["subtotal_paise"]
        discount_paise = amounts["discount_paise"]
        shipping_paise = amounts["shipping_paise"]
        tax_paise = amounts["tax_paise"]
        total_paise = amounts["total_paise"]

        order_columns = table_columns(db, "orders")
        insert_fields = [
            "user_id", "customer_name", "email", "phone",
            "address_snapshot", "total_paise", "discount_paise", "status",
        ]
        insert_values = [
            user_id, customer_name, user["email"], phone,
            address_snapshot, total_paise, discount_paise, "Placed",
        ]
        for field, value in (("subtotal_paise", subtotal_paise), ("shipping_paise", shipping_paise), ("tax_paise", tax_paise)):
            if field in order_columns:
                insert_fields.append(field)
                insert_values.append(value)
        if "coupon_code" in order_columns:
            insert_fields.append("coupon_code")
            insert_values.append(coupon_code or None)
        if "created_at" in order_columns:
            insert_fields.append("created_at")
            insert_values.append(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

        placeholders = ", ".join("?" for _ in insert_fields)
        db.execute(
            f"INSERT INTO orders ({', '.join(insert_fields)}) VALUES ({placeholders})",
            tuple(insert_values),
        )
        order_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        _step57_record_status(db, order_id, "Placed", user_id, "Order placed")

        order_item_columns = {row["name"] for row in db.execute("PRAGMA table_info(order_items)")}
        for item in items:
            item_fields = ["order_id", "book_id", "quantity"]
            item_values = [order_id, int(item["id"]), int(item["quantity"])]
            # Older upgraded databases may keep both integer-paise price fields;
            # a clean migration-created database has only price_paise.
            if "price_paise" in order_item_columns:
                item_fields.append("price_paise")
                item_values.append(int(item["price_paise"]))
            if "price_at_purchase_paise" in order_item_columns:
                item_fields.append("price_at_purchase_paise")
                item_values.append(int(item["price_paise"]))
            item_placeholders = ", ".join("?" for _ in item_fields)
            db.execute(
                f"INSERT INTO order_items ({', '.join(item_fields)}) VALUES ({item_placeholders})",
                tuple(item_values),
            )

        if coupon_code:
            coupon_row = db.execute("SELECT id FROM coupons WHERE UPPER(code)=?", (coupon_code.upper(),)).fetchone()
            if coupon_row:
                db.execute(
                    "INSERT INTO coupon_uses(coupon_id, user_id, order_id) VALUES (?, ?, ?)",
                    (coupon_row["id"], user_id, order_id),
                )
                coupon_columns = {r["name"] for r in db.execute("PRAGMA table_info(coupons)")}
                if "used_count" in coupon_columns:
                    db.execute("UPDATE coupons SET used_count=used_count+1 WHERE id=?", (coupon_row["id"],))

        release_user_reservations(db, user_id)
        db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        db.commit()
        session.pop("coupon_code", None)

    except ValueError as exc:
        db.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("shop.checkout"))
    except sqlite3.IntegrityError:
        db.rollback()
        current_app.logger.exception("Order database constraint failed.")
        flash("The order could not be completed because the data changed. Please review your cart.", "danger")
        return redirect(url_for("shop.cart"))
    except Exception:
        db.rollback()
        current_app.logger.exception("Unexpected checkout error.")
        flash("The order could not be completed. No stock was changed.", "danger")
        return redirect(url_for("shop.checkout"))

    session["cart"] = {}
    session.modified = True
    flash(f"Order #{order_id} was placed successfully.", "success")
    return redirect(url_for("shop.orders"))

# ADDRESS BOOK
# ============================================================

@shop_bp.route("/addresses", methods=["GET"])
@login_required
def addresses():
    db = get_db()

    user_id = session.get("user_id")

    if not user_id:
        flash("Please log in to view your addresses.", "error")
        return redirect(url_for("auth.login"))

    user = db.execute(
        "SELECT id FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        flash("User account not found. Please log in again.", "error")
        return redirect(url_for("auth.login"))

    saved_addresses = db.execute(
        """
        SELECT
            id,
            user_id,
            label,
            line1,
            city,
            pincode,
            phone,
            is_default
        FROM addresses
        WHERE user_id = ?
        ORDER BY is_default DESC, id DESC
        """,
        (user["id"],),
    ).fetchall()

    return render_template(
        "addresses.html",
        addresses=saved_addresses,
    )
# ============================================================
# ADD ADDRESS
# ============================================================

@shop_bp.route(
    "/addresses/add",
    methods=["GET", "POST"],
)
@login_required
def add_address():

    user_id = session.get("user_id")

    if request.method == "GET":

        return render_template(
            "address_form.html",
            address=None,
            form_mode="add",
        )

    label = request.form.get("label", "").strip()
    line1 = request.form.get("line1", "").strip()
    city = request.form.get("city", "").strip()
    pincode = request.form.get("pincode", "").strip()
    phone = request.form.get("phone", "").strip()

    make_default = (
        request.form.get("is_default")
        in {"1", "true", "on", "yes"}
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not label:
        flash(
            "Please enter an address label.",
            "danger",
        )

        return render_template(
            "address_form.html",
            address=None,
            form_mode="add",
        ), 400

    if not line1:
        flash(
            "Please enter your address.",
            "danger",
        )

        return render_template(
            "address_form.html",
            address=None,
            form_mode="add",
        ), 400

    if not city:
        flash(
            "Please enter your city.",
            "danger",
        )

        return render_template(
            "address_form.html",
            address=None,
            form_mode="add",
        ), 400

    if not pincode:
        flash(
            "Please enter your pincode.",
            "danger",
        )

        return render_template(
            "address_form.html",
            address=None,
            form_mode="add",
        ), 400

    if not pincode.isdigit() or len(pincode) != 6:
        flash(
            "Please enter a valid 6-digit pincode.",
            "danger",
        )

        return render_template(
            "address_form.html",
            address=None,
            form_mode="add",
        ), 400

    if not phone.isdigit() or len(phone) != 10:
        flash("Please enter a valid 10-digit phone number.", "danger")
        return render_template("address_form.html", address=None, form_mode="add"), 400

    db = get_db()

    # --------------------------------------------------------
    # FIRST ADDRESS IS ALWAYS DEFAULT
    # --------------------------------------------------------

    existing_count = db.execute(
        """
        SELECT COUNT(*) AS total
        FROM addresses
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    if int(existing_count["total"] or 0) == 0:
        make_default = True

    # --------------------------------------------------------
    # SAVE ADDRESS
    # --------------------------------------------------------

    try:

        db.execute("BEGIN IMMEDIATE")

        if make_default:

            db.execute(
                """
                UPDATE addresses
                SET is_default = 0
                WHERE user_id = ?
                """,
                (user_id,),
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
                phone,
                is_default
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                label,
                line1,
                city,
                pincode,
                phone,
                int(make_default),
            ),
        )

        db.commit()

    except Exception:

        db.rollback()
        raise

    flash(
        "Address added successfully.",
        "success",
    )

    return redirect(
        url_for("shop.addresses")
    )


# ============================================================
# EDIT ADDRESS
# ============================================================

@shop_bp.route(
    "/addresses/<int:address_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_address(address_id):

    user_id = session.get("user_id")
    db = get_db()

    # --------------------------------------------------------
    # GET ADDRESS
    # --------------------------------------------------------

    address = db.execute(
        """
        SELECT
            id,
            user_id,
            label,
            line1,
            city,
            pincode,
            is_default
        FROM addresses
        WHERE id = ?
          AND user_id = ?
        """,
        (
            address_id,
            user_id,
        ),
    ).fetchone()

    if address is None:

        flash(
            "Address not found.",
            "danger",
        )

        return redirect(
            url_for("shop.addresses")
        )

    # --------------------------------------------------------
    # SHOW EDIT FORM
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "address_form.html",
            address=address,
            form_mode="edit",
        )

    # --------------------------------------------------------
    # READ FORM
    # --------------------------------------------------------

    label = request.form.get("label", "").strip()
    line1 = request.form.get("line1", "").strip()
    city = request.form.get("city", "").strip()
    pincode = request.form.get("pincode", "").strip()
    phone = request.form.get("phone", "").strip()

    make_default = (
        request.form.get("is_default")
        in {"1", "true", "on", "yes"}
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not label or not line1 or not city or not pincode:

        flash(
            "Please complete all address fields.",
            "danger",
        )

        return render_template(
            "address_form.html",
            address=address,
            form_mode="edit",
        ), 400

    if not pincode.isdigit() or len(pincode) != 6:

        flash(
            "Please enter a valid 6-digit pincode.",
            "danger",
        )

        return render_template(
            "address_form.html",
            address=address,
            form_mode="edit",
        ), 400

    if not phone.isdigit() or len(phone) != 10:
        flash("Please enter a valid 10-digit phone number.", "danger")
        return render_template("address_form.html", address=address, form_mode="edit"), 400

    # --------------------------------------------------------
    # UPDATE ADDRESS
    # --------------------------------------------------------

    try:

        db.execute("BEGIN IMMEDIATE")

        if make_default:

            db.execute(
                """
                UPDATE addresses
                SET is_default = 0
                WHERE user_id = ?
                """,
                (user_id,),
            )

        # If the edited address was already the default,
        # keep it as default unless another address is
        # explicitly selected as default.

        if make_default:
            final_default = 1
        else:
            final_default = int(
                address["is_default"] or 0
            )

        db.execute(
            """
            UPDATE addresses
            SET
                label = ?,
                line1 = ?,
                city = ?,
                pincode = ?,
                phone = ?,
                is_default = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (
                label,
                line1,
                city,
                pincode,
                phone,
                final_default,
                address_id,
                user_id,
            ),
        )

        db.commit()

    except Exception:

        db.rollback()
        raise

    flash(
        "Address updated successfully.",
        "success",
    )

    return redirect(
        url_for("shop.addresses")
    )


# ============================================================
# SET DEFAULT ADDRESS
# ============================================================

@shop_bp.route(
    "/addresses/<int:address_id>/default",
    methods=["POST"],
)
@login_required
def set_default_address(address_id):

    user_id = session.get("user_id")
    db = get_db()

    # --------------------------------------------------------
    # OWNERSHIP CHECK
    # --------------------------------------------------------

    address = db.execute(
        """
        SELECT id
        FROM addresses
        WHERE id = ?
          AND user_id = ?
        """,
        (
            address_id,
            user_id,
        ),
    ).fetchone()

    if address is None:

        flash(
            "Address not found.",
            "danger",
        )

        return redirect(
            url_for("shop.addresses")
        )

    # --------------------------------------------------------
    # CHANGE DEFAULT
    # --------------------------------------------------------

    try:

        db.execute("BEGIN IMMEDIATE")

        # Remove default from all user's addresses.

        db.execute(
            """
            UPDATE addresses
            SET is_default = 0
            WHERE user_id = ?
            """,
            (user_id,),
        )

        # Make selected address default.

        db.execute(
            """
            UPDATE addresses
            SET is_default = 1
            WHERE id = ?
              AND user_id = ?
            """,
            (
                address_id,
                user_id,
            ),
        )

        db.commit()

    except Exception:

        db.rollback()
        raise

    flash(
        "Default address updated.",
        "success",
    )

    return redirect(
        url_for("shop.addresses")
    )


# ============================================================
# DELETE ADDRESS
# ============================================================

@shop_bp.route(
    "/addresses/<int:address_id>/delete",
    methods=["POST"],
)
@login_required
def delete_address(address_id):

    user_id = session.get("user_id")
    db = get_db()

    # --------------------------------------------------------
    # GET ADDRESS
    # --------------------------------------------------------

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
            user_id,
        ),
    ).fetchone()

    if address is None:

        flash(
            "Address not found.",
            "danger",
        )

        return redirect(
            url_for("shop.addresses")
        )

    # --------------------------------------------------------
    # DELETE
    # --------------------------------------------------------

    try:

        db.execute("BEGIN IMMEDIATE")

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
                user_id,
            ),
        )

        # ----------------------------------------------------
        # IF DEFAULT WAS DELETED
        # SELECT ANOTHER ADDRESS AS DEFAULT
        # ----------------------------------------------------

        if was_default:

            replacement = db.execute(
                """
                SELECT id
                FROM addresses
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()

            if replacement:

                db.execute(
                    """
                    UPDATE addresses
                    SET is_default = 1
                    WHERE id = ?
                      AND user_id = ?
                    """,
                    (
                        replacement["id"],
                        user_id,
                    ),
                )

        db.commit()

    except Exception:

        db.rollback()
        raise

    flash(
        "Address deleted successfully.",
        "success",
    )

    return redirect(
        url_for("shop.addresses")
    )

    
             
        # ----------------------------------------------------
        # MY ORDERS
# ============================================================

@shop_bp.route("/orders")
@login_required
def orders():

    user_id = session.get("user_id")

    db = get_db()

    # --------------------------------------------------------
    # GET ORDERS BELONGING TO CURRENT USER
    # --------------------------------------------------------

    user_orders = db.execute(
        """
        SELECT
            id,
            customer_name,
            email,
            phone,
            address_snapshot,
            total_paise,
            discount_paise,
            status,
            created_at

        FROM orders

        WHERE user_id = ?

        ORDER BY
            created_at DESC,
            id DESC
        """,
        (user_id,),
    ).fetchall()

    # --------------------------------------------------------
    # GET ITEMS FOR EACH ORDER
    # --------------------------------------------------------

    orders_with_items = []

    for order in user_orders:

        items = db.execute(
            """
            SELECT
                oi.id,
                oi.order_id,
                oi.book_id,
                oi.quantity,
                oi.price_paise,

                b.title,
                b.author,
                b.cover_image

            FROM order_items AS oi

            LEFT JOIN books AS b
                ON b.id = oi.book_id

            WHERE oi.order_id = ?

            ORDER BY oi.id ASC
            """,
            (order["id"],),
        ).fetchall()

        order_data = dict(order)

        order_data["items"] = []

        for item in items:

            item_data = dict(item)

            quantity = int(
                item["quantity"] or 0
            )

            price_paise = int(
                item["price_paise"] or 0
            )

            item_data["subtotal_paise"] = (
                quantity * price_paise
            )

            order_data["items"].append(
                item_data
            )

        orders_with_items.append(
            order_data
        )

    # --------------------------------------------------------
    # SHOW orders.html
    # --------------------------------------------------------

    return render_template(
        "orders.html",
        orders=orders_with_items,
    )


# ============================================================
# STEP 56
# CUSTOMER PROFILE
# ============================================================

@shop_bp.route(
    "/profile"
)
@login_required
def profile():

    user_id = session.get(
        "user_id"
    )

    db = get_db()

    user = db.execute(
        """
        SELECT
            id,
            name,
            email,
            created_at

        FROM users

        WHERE id = ?
        """,
        (
            user_id,
        )
    ).fetchone()

    if user is None:

        session.clear()

        flash(
            (
                "Your account could "
                "not be found."
            ),
            "danger"
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # --------------------------------------------------------
    # CANCELLED ORDERS DO NOT COUNT AS MONEY SPENT
    # --------------------------------------------------------

    totals = db.execute(
        """
        SELECT
            COUNT(*) AS order_count,

            COALESCE(
                SUM(total_paise),
                0
            ) AS total_spent_paise

        FROM orders

        WHERE user_id = ?
          AND status != 'Cancelled'
        """,
        (
            user_id,
        )
    ).fetchone()

    return render_template(
        "profile.html",
        user=user,
        order_count=int(
            totals["order_count"]
            or 0
        ),
        total_spent_paise=int(
            totals["total_spent_paise"]
            or 0
        ),
    )
    # ============================================================
# ============================================================
# STEPS 57-63: ORDER STATUS HISTORY, TRACKING, COUPONS,
# SHIPPING/TAX, INVOICES AND PARTIAL RETURNS
# ============================================================

SHIPPING_FREE_THRESHOLD_PAISE = 150000  # ₹1,500; configurable below
SHIPPING_DEFAULT_PAISE = 5000           # ₹50
TAX_RATE_BPS = 500                      # 5%; integer basis points


def shipping_cost_for_pincode(db, pincode, discounted_subtotal_paise):
    """Look up shipping by the first two pincode digits; use legacy first-digit zones as fallback."""
    threshold = SHIPPING_FREE_THRESHOLD_PAISE
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='site_settings'").fetchone():
        configured = db.execute("SELECT value FROM site_settings WHERE key='free_shipping_threshold_paise'").fetchone()
        if configured:
            try:
                threshold = max(0, int(configured["value"]))
            except (ValueError, TypeError):
                pass
    if int(discounted_subtotal_paise or 0) >= threshold:
        return 0
    digits = "".join(ch for ch in str(pincode or "") if ch.isdigit())
    if len(digits) < 2:
        return SHIPPING_DEFAULT_PAISE
    zones = {row["zone_prefix"]: int(row["price_paise"]) for row in db.execute(
        "SELECT zone_prefix, price_paise FROM shipping_zones"
    ).fetchall()} if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='shipping_zones'").fetchone() else {}
    return zones.get(digits[:2], zones.get(digits[0], zones.get("DEFAULT", SHIPPING_DEFAULT_PAISE)))


def calculate_order_money(db, items, discount_paise, pincode):
    """Calculate subtotal, discount, per-line rounded 5% tax, shipping and total in integer paise."""
    line_values = []
    subtotal = 0
    for item in items:
        qty = max(0, int(item.get("quantity", 0)))
        price = max(0, int(item.get("price_paise", 0)))
        amount = qty * price
        subtotal += amount
        line_values.append(amount)
    discount = min(subtotal, max(0, int(discount_paise or 0)))
    # Category-only coupons discount only matching lines; all arithmetic stays in paise.
    category_id = None
    coupon_code = session.get("coupon_code", "")
    if coupon_code:
        coupon_columns = {r["name"] for r in db.execute("PRAGMA table_info(coupons)")}
        if "category_id" in coupon_columns:
            coupon_row = db.execute("SELECT category_id FROM coupons WHERE UPPER(code)=?", (str(coupon_code).upper(),)).fetchone()
            if coupon_row:
                category_id = coupon_row["category_id"]
    eligible_indices = []
    for index, item in enumerate(items):
        if not category_id:
            eligible_indices.append(index)
            continue
        book_id = int(item["id"])
        match = db.execute("SELECT 1 FROM book_categories WHERE book_id=? AND category_id=? LIMIT 1", (book_id, int(category_id))).fetchone() if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='book_categories'").fetchone() else None
        if match:
            eligible_indices.append(index)
    eligible_total = sum(line_values[i] for i in eligible_indices)
    discount = min(discount, eligible_total)
    # Allocate proportionally to eligible line amounts, giving any remainder to the last eligible line.
    allocations = [0] * len(line_values)
    if eligible_total and discount:
        remaining = discount
        nonzero = [i for i in eligible_indices if line_values[i] > 0]
        for i in nonzero[:-1]:
            allocations[i] = (discount * line_values[i]) // eligible_total
            remaining -= allocations[i]
        if nonzero:
            allocations[nonzero[-1]] = remaining
    tax = 0
    for amount, allocated in zip(line_values, allocations):
        taxable_line = max(0, amount - allocated)
        tax += (taxable_line * TAX_RATE_BPS + 5000) // 10000
    discounted_subtotal = subtotal - discount
    shipping = shipping_cost_for_pincode(db, pincode, discounted_subtotal)
    return {"subtotal_paise": subtotal, "discount_paise": discount,
            "shipping_paise": shipping, "tax_paise": tax,
            "total_paise": discounted_subtotal + shipping + tax}


def _step57_admin_required():
    """Require an authenticated admin/staff role; never trust a form flag."""
    user_id = session.get("user_id")
    if not user_id:
        abort(403)
    row = get_db().execute(
        "SELECT role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row or str(row["role"]).lower() not in {"admin", "staff"}:
        abort(403)


def _step57_order_for_user(db, order_id, user_id):
    order = db.execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?",
        (order_id, user_id),
    ).fetchone()
    # Use 404 to avoid disclosing whether another customer's order exists.
    if order is None:
        abort(404)
    return order


def _step57_record_status(db, order_id, status, changed_by, note=None):
    columns = {row["name"] for row in db.execute("PRAGMA table_info(order_status_history)")}
    timestamp_column = "changed_at" if "changed_at" in columns else "created_at"
    fields = ["order_id", "status", "changed_by", "note", timestamp_column]
    db.execute(
        f"INSERT INTO order_status_history ({', '.join(fields)}) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (order_id, status, changed_by, (note or "").strip() or None),
    )


def _step57_price_summary(subtotal_paise, discount_paise, pincode):
    """All amounts are integer paise; tax is rounded half-up to paise."""
    subtotal_paise = max(0, int(subtotal_paise))
    discount_paise = min(subtotal_paise, max(0, int(discount_paise)))
    taxable_paise = subtotal_paise - discount_paise
    prefix = (str(pincode or "").strip()[:3])
    # Pincode-prefix zones can be expanded in configuration without floats.
    remote_prefixes = {"682", "683", "744", "790", "791", "792", "793", "794", "795", "796", "797", "798"}
    shipping_paise = 0 if taxable_paise >= SHIPPING_FREE_THRESHOLD_PAISE else SHIPPING_DEFAULT_PAISE
    if prefix in remote_prefixes and shipping_paise:
        shipping_paise += 2500
    tax_paise = (taxable_paise * TAX_RATE_BPS + 5000) // 10000
    return {
        "subtotal_paise": subtotal_paise,
        "discount_paise": discount_paise,
        "shipping_paise": shipping_paise,
        "tax_paise": tax_paise,
        "total_paise": taxable_paise + shipping_paise + tax_paise,
    }

@shop_bp.route("/orders/<int:order_id>/tracking")
@login_required
def order_tracking(order_id):
    db = get_db()

    order = _step57_order_for_user(
        db,
        order_id,
        session["user_id"]
    )

    history_columns = {row["name"] for row in db.execute("PRAGMA table_info(order_status_history)")}
    history_time_column = "changed_at" if "changed_at" in history_columns else "created_at"
    history = db.execute(
        f"SELECT status, changed_by, note, {history_time_column} AS created_at "
        "FROM order_status_history WHERE order_id = ? ORDER BY id ASC",
        (order_id,),
    ).fetchall()

    items = db.execute(
        """
        SELECT oi.*, b.title, b.author, b.cover_image
        FROM order_items oi
        LEFT JOIN books b ON b.id = oi.book_id
        WHERE oi.order_id = ?
        ORDER BY oi.id
        """,
        (order_id,)
    ).fetchall()

    return render_template(
        "order_tracking.html",
        order=order,
        history=history,
        items=items,
        status_steps=["Placed", "Packed", "Shipped", "Delivered"]
    )


@shop_bp.route("/order/<int:order_id>/invoice")
@shop_bp.route("/orders/<int:order_id>/invoice")
@login_required
def order_invoice(order_id):
    db = get_db()
    user_id = session.get("user_id")
    order = db.execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?",
        (order_id, user_id),
    ).fetchone()
    if order is None:
        # Admin may view invoices for support/reporting.
        _step57_admin_required()
        order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        abort(404)
    items = db.execute(
        """SELECT oi.*, b.title, b.author FROM order_items oi
           LEFT JOIN books b ON b.id = oi.book_id
           WHERE oi.order_id = ? ORDER BY oi.id""", (order_id,),
    ).fetchall()
    subtotal = sum(int(x["quantity"] or 0) * int(x["price_paise"] or 0) for x in items)
    return render_template("order_invoice.html", order=order, items=items, subtotal_paise=subtotal)


@shop_bp.route("/orders/<int:order_id>/returns", methods=["GET", "POST"])
@login_required
def request_order_return(order_id):
    db = get_db()
    user_id = session["user_id"]
    order = _step57_order_for_user(db, order_id, user_id)
    if order["status"] != "Delivered":
        flash("Returns can only be requested for delivered orders.", "danger")
        return redirect(url_for("shop.order_confirmation", order_id=order_id))

    return_columns = {r["name"] for r in db.execute("PRAGMA table_info(returns)")}
    legacy_shape = "order_item_id" in return_columns and "quantity" in return_columns

    def fetch_items():
        if legacy_shape:
            return db.execute("""
                SELECT oi.id AS order_item_id, oi.quantity, oi.price_paise, b.title,
                       COALESCE((SELECT SUM(r.quantity) FROM returns r
                                 WHERE r.order_item_id=oi.id AND r.status!='Rejected'),0) AS already_requested
                FROM order_items oi JOIN books b ON b.id=oi.book_id
                WHERE oi.order_id=? ORDER BY oi.id
            """, (order_id,)).fetchall()
        return db.execute("""
            SELECT oi.id AS order_item_id, oi.quantity, oi.price_paise, b.title,
                   COALESCE((SELECT SUM(ri.quantity) FROM return_items ri JOIN returns r ON r.id=ri.return_id
                             WHERE ri.order_item_id=oi.id AND r.status!='Rejected'),0) AS already_requested
            FROM order_items oi JOIN books b ON b.id=oi.book_id
            WHERE oi.order_id=? ORDER BY oi.id
        """, (order_id,)).fetchall()

    items = fetch_items()
    if request.method == "POST":
        order_item_id = request.form.get("order_item_id", type=int)
        quantity = request.form.get("quantity", type=int)
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("Please provide a reason for the return.", "danger")
            return redirect(url_for("shop.request_order_return", order_id=order_id))
        try:
            db.execute("BEGIN IMMEDIATE")
            # Re-check ownership/status and remaining quantity under the write lock.
            locked_order = db.execute("SELECT status FROM orders WHERE id=? AND user_id=?", (order_id, user_id)).fetchone()
            if not locked_order:
                abort(404)
            if locked_order["status"] != "Delivered":
                raise ValueError("Returns can only be requested for delivered orders.")
            if legacy_shape:
                chosen = db.execute("SELECT oi.id, oi.quantity FROM order_items oi WHERE oi.id=? AND oi.order_id=?", (order_item_id, order_id)).fetchone()
                if not chosen:
                    raise ValueError("Choose an item from this order.")
                prior = db.execute("SELECT COALESCE(SUM(quantity),0) FROM returns WHERE order_item_id=? AND status!='Rejected'", (order_item_id,)).fetchone()[0]
            else:
                chosen = db.execute("SELECT oi.id, oi.quantity FROM order_items oi WHERE oi.id=? AND oi.order_id=?", (order_item_id, order_id)).fetchone()
                if not chosen:
                    raise ValueError("Choose an item from this order.")
                prior = db.execute("SELECT COALESCE(SUM(ri.quantity),0) FROM return_items ri JOIN returns r ON r.id=ri.return_id WHERE ri.order_item_id=? AND r.status!='Rejected'", (order_item_id,)).fetchone()[0]
            remaining = int(chosen["quantity"]) - int(prior or 0)
            if not quantity or quantity < 1 or quantity > remaining:
                raise ValueError(f"Return quantity must be between 1 and {max(0, remaining)}.")
            if legacy_shape:
                db.execute("INSERT INTO returns(order_item_id, quantity, reason, status) VALUES (?, ?, ?, 'Pending')", (order_item_id, quantity, reason))
            else:
                cur = db.execute("INSERT INTO returns(order_id, user_id, status, created_at) VALUES (?, ?, 'Pending', CURRENT_TIMESTAMP)", (order_id, user_id))
                db.execute("INSERT INTO return_items(return_id, order_item_id, quantity, reason) VALUES (?, ?, ?, ?)", (cur.lastrowid, order_item_id, quantity, reason))
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("shop.request_order_return", order_id=order_id))
        except Exception:
            db.rollback()
            current_app.logger.exception("Could not create return request")
            flash("Could not submit the return request. Please try again.", "danger")
            return redirect(url_for("shop.request_order_return", order_id=order_id))
        flash("Your return request was sent to the store for review.", "success")
        return redirect(url_for("shop.order_confirmation", order_id=order_id))
    return render_template("return_request.html", order=order, items=items)

@shop_bp.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@login_required
def admin_update_order_status(order_id):
    _step57_admin_required()
    db = get_db()
    next_status = request.form.get("status", "").strip()
    note = request.form.get("note", "").strip()
    try:
        db.execute("BEGIN IMMEDIATE")
        order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            abort(404)
        old_status = str(order["status"] or "Placed")
        if next_status not in ALLOWED_STATUS_MOVES.get(old_status, set()):
            raise ValueError(f"Status cannot move from {old_status} to {next_status}.")
        if next_status == "Cancelled":
            rows = db.execute("SELECT book_id, quantity FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
            for item in rows:
                db.execute("UPDATE books SET stock = stock + ? WHERE id = ?", (int(item["quantity"]), int(item["book_id"])))
                db.execute("INSERT INTO stock_log(book_id, change, reason, user_id) VALUES (?, ?, 'cancel_restore', ?)", (int(item["book_id"]), int(item["quantity"]), session["user_id"]))
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (next_status, order_id))
        _step57_record_status(db, order_id, next_status, session["user_id"], note)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        flash(str(exc), "danger")
    except Exception:
        db.rollback()
        current_app.logger.exception("Order status update failed")
        flash("Could not update order status.", "danger")
    return redirect(url_for("shop.orders"))


@shop_bp.route("/admin/returns")
@login_required
def admin_returns():
    _step57_admin_required()
    db = get_db()
    cols = {r["name"] for r in db.execute("PRAGMA table_info(returns)")}
    if "order_item_id" in cols and "quantity" in cols:
        rows = db.execute("""
            SELECT r.id, r.order_item_id, r.quantity, r.reason, r.status,
                   r.requested_at AS created_at, r.reviewed_at, r.reviewed_by,
                   oi.order_id, oi.book_id, b.title, o.user_id, o.customer_name, o.email,
                   o.status AS order_status
            FROM returns r JOIN order_items oi ON oi.id=r.order_item_id
            JOIN orders o ON o.id=oi.order_id LEFT JOIN books b ON b.id=oi.book_id
            ORDER BY r.id DESC
        """).fetchall()
    else:
        rows = db.execute("""
            SELECT r.id, ri.order_item_id, ri.quantity, ri.reason, r.status,
                   r.created_at, r.reviewed_at, r.reviewed_by, oi.order_id, oi.book_id,
                   b.title, o.user_id, o.customer_name, o.email, o.status AS order_status
            FROM returns r JOIN return_items ri ON ri.return_id=r.id
            JOIN order_items oi ON oi.id=ri.order_item_id JOIN orders o ON o.id=oi.order_id
            LEFT JOIN books b ON b.id=oi.book_id ORDER BY r.id DESC
        """).fetchall()
    return render_template("admin_returns.html", returns=rows)


@shop_bp.route("/admin/returns/<int:return_id>/<action>", methods=["POST"])
@login_required
def admin_decide_return(return_id, action):
    _step57_admin_required()
    if action not in {"approve", "reject"}:
        abort(404)
    db = get_db()
    cols = {r["name"] for r in db.execute("PRAGMA table_info(returns)")}
    legacy_shape = "order_item_id" in cols and "quantity" in cols
    try:
        db.execute("BEGIN IMMEDIATE")
        ret = db.execute("SELECT * FROM returns WHERE id=?", (return_id,)).fetchone()
        if not ret:
            abort(404)
        if ret["status"] != "Pending":
            raise ValueError("This return request has already been reviewed.")
        if action == "approve":
            if legacy_shape:
                items = db.execute("SELECT oi.book_id, r.quantity FROM returns r JOIN order_items oi ON oi.id=r.order_item_id WHERE r.id=?", (return_id,)).fetchall()
            else:
                items = db.execute("SELECT oi.book_id, ri.quantity FROM return_items ri JOIN order_items oi ON oi.id=ri.order_item_id WHERE ri.return_id=?", (return_id,)).fetchall()
            for item in items:
                db.execute("UPDATE books SET stock=stock+? WHERE id=?", (int(item["quantity"]), int(item["book_id"])))
                db.execute("INSERT INTO stock_log(book_id, change, reason, user_id) VALUES (?, ?, 'returned_order', ?)", (int(item["book_id"]), int(item["quantity"]), session["user_id"]))
        updates = ["status=?"]
        values = ["Approved" if action == "approve" else "Rejected"]
        if "reviewed_by" in cols:
            updates.append("reviewed_by=?"); values.append(session["user_id"])
        if "reviewed_at" in cols:
            updates.append("reviewed_at=CURRENT_TIMESTAMP")
        values.append(return_id)
        db.execute(f"UPDATE returns SET {', '.join(updates)} WHERE id=? AND status='Pending'", values)
        if db.execute("SELECT changes()").fetchone()[0] != 1:
            raise ValueError("This return request has already been reviewed.")
        db.commit()
        flash("Return request " + ("approved; stock restored." if action == "approve" else "rejected."), "success")
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback(); flash(str(exc), "warning")
    except Exception:
        db.rollback(); current_app.logger.exception("Return review failed")
        flash("Could not review the return request.", "danger")
    return redirect(url_for("shop.admin_returns"))


# ============================================================
# COUPON MANAGEMENT
# ============================================================

def migrate_coupon_columns(db):
    """Create the coupons table and add missing columns."""

    db.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            discount_type TEXT NOT NULL DEFAULT 'percentage',
            discount_value INTEGER NOT NULL DEFAULT 0,
            min_order_paise INTEGER NOT NULL DEFAULT 0,
            max_discount_paise INTEGER,
            start_date TEXT,
            end_date TEXT,
            usage_limit INTEGER,
            used_count INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT
        )
    """)

    cursor = db.execute("PRAGMA table_info(coupons)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    columns = {
        "discount_type": "TEXT NOT NULL DEFAULT 'percentage'",
        "discount_value": "INTEGER NOT NULL DEFAULT 0",
        "min_order_paise": "INTEGER NOT NULL DEFAULT 0",
        "max_discount_paise": "INTEGER",
        "start_date": "TEXT",
        "end_date": "TEXT",
        "usage_limit": "INTEGER",
        "used_count": "INTEGER NOT NULL DEFAULT 0",
        "is_active": "INTEGER NOT NULL DEFAULT 1",
        "created_at": "TEXT",
        "one_use_per_customer": "INTEGER NOT NULL DEFAULT 0",
        "category_id": "INTEGER",
        "expires_at": "TEXT",
        "expiry_date": "TEXT",
        "active": "INTEGER NOT NULL DEFAULT 1",
    }

    for name, definition in columns.items():
        if name not in existing_columns:
            db.execute(
                f"ALTER TABLE coupons ADD COLUMN {name} {definition}"
            )


@shop_bp.route("/admin/coupons", methods=["GET", "POST"])
@login_required
def admin_coupons():
    _step57_admin_required()
    db = get_db()

    try:
        migrate_coupon_columns(db)

        if request.method == "POST":
            action = request.form.get("action", "create").strip().lower()

            # Create a new coupon
            if action == "create":
                code = request.form.get("code", "").strip().upper()
                discount_type = request.form.get(
                    "discount_type", "percentage"
                ).strip().lower()

                if not code:
                    raise ValueError("Coupon code is required.")

                if discount_type not in {"percentage", "fixed"}:
                    raise ValueError("Invalid discount type.")

                try:
                    discount_value = int(request.form.get("discount_value", "0"))
                    min_order_paise = int(request.form.get("min_order_paise", "0") or 0)
                    max_discount_text = request.form.get("max_discount_paise", "").strip()
                    max_discount_paise = int(max_discount_text) if max_discount_text else None
                    usage_limit_text = request.form.get("usage_limit", "").strip()
                    usage_limit = int(usage_limit_text) if usage_limit_text else None
                except (ValueError, TypeError):
                    raise ValueError("Enter whole-number paise values and valid coupon limits.")

                if discount_value <= 0:
                    raise ValueError("Discount value must be greater than zero.")

                if discount_type == "percentage" and discount_value > 100:
                    raise ValueError("Percentage discount cannot exceed 100.")

                if min_order_paise < 0:
                    raise ValueError("Minimum order amount cannot be negative.")

                if max_discount_paise is not None and max_discount_paise < 0:
                    raise ValueError("Maximum discount cannot be negative.")

                if usage_limit is not None and usage_limit < 1:
                    raise ValueError("Usage limit must be at least 1.")

                start_date = request.form.get("start_date", "").strip() or None
                end_date = (request.form.get("end_date", "").strip()
                            or request.form.get("expires_at", "").strip() or None)
                category_text = request.form.get("category_id", "").strip()
                category_id = int(category_text) if category_text else None
                one_use_per_customer = 1 if request.form.get("one_use_per_customer") in {"1", "on", "true"} else 0

                if start_date and end_date and start_date > end_date:
                    raise ValueError(
                        "End date cannot be earlier than start date."
                    )

                legacy_percent = discount_value if discount_type == "percentage" else 0
                db.execute("""
                    INSERT INTO coupons (
                        code, percent, expiry_date, active, discount_type, discount_value,
                        min_order_paise, max_discount_paise, start_date, end_date,
                        usage_limit, used_count, is_active, created_at, category_id,
                        one_use_per_customer
                    )
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, 0, 1, CURRENT_TIMESTAMP, ?, ?)
                """, (
                    code,
                    legacy_percent,
                    end_date,
                    discount_type,
                    discount_value,
                    min_order_paise,
                    max_discount_paise,
                    start_date,
                    end_date,
                    usage_limit,
                    category_id,
                    one_use_per_customer,
                ))

                db.commit()
                flash("Coupon created successfully.", "success")

            # Activate or deactivate a coupon
            elif action in {"toggle", "activate", "deactivate"}:
                coupon_id = request.form.get("coupon_id", type=int)

                if not coupon_id:
                    raise ValueError("Invalid coupon ID.")

                if action == "toggle":
                    db.execute("""
                        UPDATE coupons
                        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
                            active = CASE WHEN active = 1 THEN 0 ELSE 1 END
                        WHERE id = ?
                    """, (coupon_id,))
                else:
                    active = 1 if action == "activate" else 0
                    db.execute("UPDATE coupons SET is_active=?, active=? WHERE id=?", (active, active, coupon_id))

                if db.execute("SELECT changes()").fetchone()[0] == 0:
                    raise ValueError("Coupon not found.")

                db.commit()
                flash("Coupon status updated successfully.", "success")

            # Delete a coupon
            elif action == "delete":
                coupon_id = request.form.get("coupon_id", type=int)

                if not coupon_id:
                    raise ValueError("Invalid coupon ID.")

                db.execute("DELETE FROM coupons WHERE id = ?", (coupon_id,))

                if db.execute("SELECT changes()").fetchone()[0] == 0:
                    raise ValueError("Coupon not found.")

                db.commit()
                flash("Coupon deleted successfully.", "success")

            else:
                raise ValueError("Invalid coupon action.")

            if request.method == "POST":
                return redirect(url_for("shop.admin_coupons"))

    except ValueError as exc:
        db.rollback()
        flash(str(exc), "danger")

    except sqlite3.IntegrityError:
        db.rollback()
        flash(
            "This coupon code already exists. Please use a different code.",
            "danger",
        )

    except sqlite3.Error:
        db.rollback()
        current_app.logger.exception("Coupon action failed.")
        flash("Could not update the coupons.", "danger")

    coupons = db.execute("""
        SELECT *
        FROM coupons
        ORDER BY id DESC
    """).fetchall()
    categories = db.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE").fetchall()

    return render_template("admin_coupons.html", coupons=coupons, categories=categories)
