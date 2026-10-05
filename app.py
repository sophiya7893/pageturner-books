from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)
import sqlite3
import os
from functools import wraps
from werkzeug.utils import secure_filename


app = Flask(__name__)

app.secret_key = "pageturner-secret-key-change-this"

# Keep the admin password in ONE place only
ADMIN_PASSWORD = "admin123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =========================================================
# USE THE EXISTING DATABASE
# =========================================================

DATABASE = os.path.join(
    BASE_DIR,
    "pageturner.db"
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "images",
    "books"
)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def get_db():
    db = sqlite3.connect(DATABASE)

    db.row_factory = sqlite3.Row

    db.execute(
        "PRAGMA foreign_keys = ON"
    )

    return db


def init_db():
    """
    Create the database from schema.sql only when
    pageturner.db does not already exist.
    """

    db = get_db()

    schema_path = os.path.join(
        BASE_DIR,
        "schema.sql"
    )

    with open(
        schema_path,
        "r",
        encoding="utf-8"
    ) as file:
        db.executescript(file.read())

    db.commit()
    db.close()


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


def get_cart():
    return session.get(
        "cart",
        {}
    )


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


def cart_count():
    cart = get_cart()

    return sum(
        int(quantity)
        for quantity in cart.values()
    )


@app.context_processor
def inject_cart_count():
    return {
        "cart_count": cart_count()
    }


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
            SELECT *
            FROM books
            WHERE id = ?
            """,
            (int(book_id),)
        ).fetchone()

        if book is None:
            continue

        quantity = int(quantity)

        subtotal = (
            book["price"] * quantity
        )

        items.append({
            "book": book,
            "quantity": quantity,
            "subtotal": subtotal
        })

        total += subtotal

    db.close()

    return items, total


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

@app.route("/")
def home():

    search = request.args.get(
        "search",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    sort = request.args.get(
        "sort",
        "title"
    )

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

    # Exactly 6 books per page
    per_page = 6

    sort_options = {
        "title": "title COLLATE NOCASE ASC",
        "title_desc": "title COLLATE NOCASE DESC",
        "price": "price ASC",
        "price_desc": "price DESC"
    }

    order_by = sort_options.get(
        sort,
        "title COLLATE NOCASE ASC"
    )

    db = get_db()

    categories = db.execute(
        """
        SELECT DISTINCT category
        FROM books
        WHERE category IS NOT NULL
          AND category != ''
        ORDER BY category
        """
    ).fetchall()

    conditions = []
    params = []

    if search:

        conditions.append(
            """
            (
                title LIKE ?
                OR author LIKE ?
                OR category LIKE ?
            )
            """
        )

        search_value = f"%{search}%"

        params.extend([
            search_value,
            search_value,
            search_value
        ])

    if category:

        conditions.append(
            "category = ?"
        )

        params.append(category)

    where_clause = ""

    if conditions:

        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )

    total_books = db.execute(
        f"""
        SELECT COUNT(*)
        FROM books
        {where_clause}
        """,
        params
    ).fetchone()[0]

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
        SELECT
            books.*,

            ROUND(
                COALESCE(
                    (
                        SELECT AVG(rating)
                        FROM reviews
                        WHERE reviews.book_id = books.id
                    ),
                    0
                ),
                1
            ) AS average_rating,

            (
                SELECT COUNT(*)
                FROM reviews
                WHERE reviews.book_id = books.id
            ) AS review_count

        FROM books

        {where_clause}

        ORDER BY {order_by}

        LIMIT ?
        OFFSET ?
        """,
        params + [
            per_page,
            offset
        ]
    ).fetchall()

    db.close()

    return render_template(
        "home.html",
        books=books,
        categories=categories,
        search=search,
        category=category,
        sort=sort,
        page=page,
        total_pages=total_pages,
        total_books=total_books
    )


# ---------------------------------------------------------
# BOOK DETAIL
# ---------------------------------------------------------

@app.route("/book/<int:book_id>")
def book_detail(book_id):

    db = get_db()

    book = db.execute(
        """
        SELECT
            books.*,

            ROUND(
                COALESCE(
                    AVG(reviews.rating),
                    0
                ),
                1
            ) AS average_rating,

            COUNT(reviews.id)
                AS review_count

        FROM books

        LEFT JOIN reviews
            ON reviews.book_id = books.id

        WHERE books.id = ?

        GROUP BY books.id
        """,
        (book_id,)
    ).fetchone()

    if book is None:

        db.close()

        flash(
            "Book not found.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    reviews = db.execute(
        """
        SELECT *
        FROM reviews
        WHERE book_id = ?
        ORDER BY id DESC
        """,
        (book_id,)
    ).fetchall()

    db.close()

    return render_template(
        "book_detail.html",
        book=book,
        reviews=reviews
    )


# ---------------------------------------------------------
# REVIEWS
# ---------------------------------------------------------

@app.route(
    "/book/<int:book_id>/review",
    methods=["POST"]
)
def add_review(book_id):

    name = request.form.get(
        "name",
        ""
    ).strip()

    comment = request.form.get(
        "comment",
        ""
    ).strip()

    try:
        rating = int(
            request.form.get(
                "rating",
                0
            )
        )
    except ValueError:
        rating = 0

    if not name:

        flash(
            "Please enter your name.",
            "error"
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
            "error"
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
            "error"
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

    if book is None:

        db.close()

        flash(
            "Book not found.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    db.execute(
        """
        INSERT INTO reviews
        (
            book_id,
            name,
            rating,
            comment
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            book_id,
            name,
            rating,
            comment
        )
    )

    db.commit()
    db.close()

    flash(
        "Thank you for your review!",
        "success"
    )

    return redirect(
        url_for(
            "book_detail",
            book_id=book_id
        )
    )


# ---------------------------------------------------------
# CART
# ---------------------------------------------------------

@app.route(
    "/cart/add/<int:book_id>",
    methods=["POST"]
)
def add_to_cart(book_id):

    db = get_db()

    book = db.execute(
        """
        SELECT *
        FROM books
        WHERE id = ?
        """,
        (book_id,)
    ).fetchone()

    db.close()

    if book is None:

        flash(
            "Book not found.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    if book["stock"] <= 0:

        flash(
            "This book is out of stock.",
            "error"
        )

        return redirect(
            request.referrer
            or url_for("home")
        )

    cart = get_cart()

    current_quantity = int(
        cart.get(
            str(book_id),
            0
        )
    )

    if current_quantity >= book["stock"]:

        flash(
            f"Only {book['stock']} copies are available.",
            "error"
        )

        return redirect(
            request.referrer
            or url_for("home")
        )

    cart[str(book_id)] = (
        current_quantity + 1
    )

    save_cart(cart)

    flash(
        f"{book['title']} added to your cart.",
        "success"
    )

    return redirect(
        request.referrer
        or url_for("home")
    )


@app.route("/cart")
def cart_page():

    items, total = get_cart_items()

    return render_template(
        "cart.html",
        items=items,
        total=total
    )


@app.route(
    "/cart/update",
    methods=["POST"]
)
def update_cart():

    cart = get_cart()

    db = get_db()

    for key in list(cart.keys()):

        value = request.form.get(
            f"quantity_{key}",
            "0"
        )

        try:
            quantity = int(value)
        except ValueError:
            quantity = 0

        book = db.execute(
            """
            SELECT stock
            FROM books
            WHERE id = ?
            """,
            (int(key),)
        ).fetchone()

        if book is None or quantity <= 0:

            cart.pop(
                key,
                None
            )

            continue

        if quantity > book["stock"]:
            quantity = book["stock"]

        cart[key] = quantity

    db.close()

    save_cart(cart)

    flash(
        "Cart updated.",
        "success"
    )

    return redirect(
        url_for("cart_page")
    )


@app.route(
    "/cart/remove/<int:book_id>",
    methods=["POST"]
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
        url_for("cart_page")
    )


# ---------------------------------------------------------
# CHECKOUT
# ---------------------------------------------------------

@app.route(
    "/checkout",
    methods=["GET", "POST"]
)
def checkout():

    items, total = get_cart_items()

    if not items:

        flash(
            "Your cart is empty.",
            "error"
        )

        return redirect(
            url_for("cart_page")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        if not name or not phone or not address:

            flash(
                "Please complete all checkout fields.",
                "error"
            )

            return render_template(
                "checkout.html",
                items=items,
                total=total
            )

        db = get_db()

        try:

            # Lock database while checking stock
            db.execute(
                "BEGIN IMMEDIATE"
            )

            cart = get_cart()

            final_total = 0
            checked_items = []

            for book_id, quantity in cart.items():

                quantity = int(quantity)

                book = db.execute(
                    """
                    SELECT *
                    FROM books
                    WHERE id = ?
                    """,
                    (int(book_id),)
                ).fetchone()

                if book is None:

                    raise ValueError(
                        "A book in your cart no longer exists."
                    )

                if quantity <= 0:

                    raise ValueError(
                        f"Invalid quantity for {book['title']}."
                    )

                if book["stock"] < quantity:

                    raise ValueError(
                        f"Only {book['stock']} copies of "
                        f"{book['title']} are available."
                    )

                final_total += (
                    book["price"]
                    * quantity
                )

                checked_items.append(
                    (
                        book,
                        quantity
                    )
                )

            # Create order
            cursor = db.execute(
                """
                INSERT INTO orders
                (
                    name,
                    phone,
                    address,
                    total
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    phone,
                    address,
                    final_total
                )
            )

            order_id = cursor.lastrowid

            # Reduce stock and create order items
            for book, quantity in checked_items:

                updated = db.execute(
                    """
                    UPDATE books

                    SET stock = stock - ?

                    WHERE id = ?
                      AND stock >= ?
                    """,
                    (
                        quantity,
                        book["id"],
                        quantity
                    )
                )

                if updated.rowcount != 1:

                    raise ValueError(
                        f"Stock changed for {book['title']}."
                    )

                db.execute(
                    """
                    INSERT INTO order_items
                    (
                        order_id,
                        book_id,
                        title,
                        price,
                        quantity
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        book["id"],
                        book["title"],
                        book["price"],
                        quantity
                    )
                )

            db.commit()

            save_cart({})

            return redirect(
                url_for(
                    "order_confirmation",
                    order_id=order_id
                )
            )

        except Exception as error:

            db.rollback()

            flash(
                str(error),
                "error"
            )

        finally:

            db.close()

    return render_template(
        "checkout.html",
        items=items,
        total=total
    )


# ---------------------------------------------------------
# ORDER CONFIRMATION
# ---------------------------------------------------------

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

    items = db.execute(
        """
        SELECT *
        FROM order_items
        WHERE order_id = ?
        ORDER BY id
        """,
        (order_id,)
    ).fetchall()

    db.close()

    if order is None:

        flash(
            "Order not found.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    return render_template(
        "order_confirmation.html",
        order=order,
        items=items
    )


# ---------------------------------------------------------
# FIND MY ORDERS
# ---------------------------------------------------------

@app.route(
    "/orders",
    methods=["GET", "POST"]
)
def orders():

    orders = []
    searched = False
    phone = ""

    if request.method == "POST":

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        searched = True

        db = get_db()

        orders = db.execute(
            """
            SELECT
                o.id,
                o.name,
                o.phone,
                o.address,
                o.total,
                o.created_at,
                COUNT(oi.id)
                    AS item_count

            FROM orders AS o

            LEFT JOIN order_items AS oi
                ON oi.order_id = o.id

            WHERE o.phone = ?

            GROUP BY
                o.id,
                o.name,
                o.phone,
                o.address,
                o.total,
                o.created_at

            ORDER BY
                o.created_at DESC
            """,
            (phone,)
        ).fetchall()

        db.close()

    return render_template(
        "orders.html",
        orders=orders,
        searched=searched,
        phone=phone
    )


# ---------------------------------------------------------
# ADMIN AUTH
# ---------------------------------------------------------

def admin_required(view):

    @wraps(view)
    def wrapped_view(
        *args,
        **kwargs
    ):

        if not session.get(
            "admin_logged_in"
        ):

            return redirect(
                url_for(
                    "admin_login",
                    next=request.path
                )
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped_view


@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        if password == ADMIN_PASSWORD:

            session[
                "admin_logged_in"
            ] = True

            next_page = request.args.get(
                "next"
            )

            if next_page:
                return redirect(
                    next_page
                )

            return redirect(
                url_for("admin_page")
            )

        flash(
            "Incorrect admin password.",
            "error"
        )

    return render_template(
        "admin_login.html"
    )


@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    return redirect(
        url_for("home")
    )


# ---------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_page():

    db = get_db()

    books = db.execute(
        """
        SELECT *
        FROM books
        ORDER BY id DESC
        """
    ).fetchall()

    total_books = db.execute(
        """
        SELECT COUNT(*)
        FROM books
        """
    ).fetchone()[0]

    total_stock = db.execute(
        """
        SELECT COALESCE(
            SUM(stock),
            0
        )
        FROM books
        """
    ).fetchone()[0]

    total_orders = db.execute(
        """
        SELECT COUNT(*)
        FROM orders
        """
    ).fetchone()[0]

    total_revenue = db.execute(
        """
        SELECT COALESCE(
            SUM(total),
            0
        )
        FROM orders
        """
    ).fetchone()[0]

    db.close()

    return render_template(
        "admin.html",
        books=books,
        total_books=total_books,
        total_stock=total_stock,
        total_orders=total_orders,
        total_revenue=total_revenue
    )


# ---------------------------------------------------------
# ADMIN ADD BOOK
# ---------------------------------------------------------

@app.route(
    "/admin/books/add",
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

        cover_color = request.form.get(
            "cover_color",
            "#8b5e3c"
        )

        try:

            price = float(
                request.form.get(
                    "price",
                    0
                )
            )

            stock = int(
                request.form.get(
                    "stock",
                    0
                )
            )

        except ValueError:

            flash(
                "Price and stock must be valid numbers.",
                "error"
            )

            return render_template(
                "admin_book_form.html",
                book=None
            )

        cover_image = ""

        file = request.files.get(
            "cover_image"
        )

        if file and file.filename:

            if not allowed_file(
                file.filename
            ):

                flash(
                    "Invalid image type.",
                    "error"
                )

                return render_template(
                    "admin_book_form.html",
                    book=None
                )

            filename = secure_filename(
                file.filename
            )

            file.save(
                os.path.join(
                    app.config[
                        "UPLOAD_FOLDER"
                    ],
                    filename
                )
            )

            cover_image = filename

        db = get_db()

        db.execute(
            """
            INSERT INTO books
            (
                title,
                author,
                category,
                price,
                description,
                stock,
                cover_color,
                cover_image
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                author,
                category,
                price,
                description,
                stock,
                cover_color,
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
            url_for("admin_page")
        )

    return render_template(
        "admin_book_form.html",
        book=None
    )


# ---------------------------------------------------------
# ADMIN EDIT BOOK
# ---------------------------------------------------------

@app.route(
    "/admin/books/edit/<int:book_id>",
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

    if book is None:

        db.close()

        flash(
            "Book not found.",
            "error"
        )

        return redirect(
            url_for("admin_page")
        )

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

        cover_color = request.form.get(
            "cover_color",
            "#8b5e3c"
        )

        try:

            price = float(
                request.form.get(
                    "price",
                    0
                )
            )

            stock = int(
                request.form.get(
                    "stock",
                    0
                )
            )

        except ValueError:

            db.close()

            flash(
                "Price and stock must be valid numbers.",
                "error"
            )

            return redirect(
                url_for(
                    "admin_edit_book",
                    book_id=book_id
                )
            )

        cover_image = book[
            "cover_image"
        ]

        file = request.files.get(
            "cover_image"
        )

        if file and file.filename:

            if not allowed_file(
                file.filename
            ):

                db.close()

                flash(
                    "Invalid image type.",
                    "error"
                )

                return redirect(
                    url_for(
                        "admin_edit_book",
                        book_id=book_id
                    )
                )

            filename = secure_filename(
                file.filename
            )

            file.save(
                os.path.join(
                    app.config[
                        "UPLOAD_FOLDER"
                    ],
                    filename
                )
            )

            cover_image = filename

        db.execute(
            """
            UPDATE books

            SET
                title = ?,
                author = ?,
                category = ?,
                price = ?,
                description = ?,
                stock = ?,
                cover_color = ?,
                cover_image = ?

            WHERE id = ?
            """,
            (
                title,
                author,
                category,
                price,
                description,
                stock,
                cover_color,
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
            url_for("admin_page")
        )

    db.close()

    return render_template(
        "admin_book_form.html",
        book=book
    )


# ---------------------------------------------------------
# ADMIN DELETE BOOK
# ---------------------------------------------------------

@app.route(
    "/admin/books/delete/<int:book_id>",
    methods=["POST"]
)
@admin_required
def admin_delete_book(book_id):

    db = get_db()

    db.execute(
        """
        DELETE FROM books
        WHERE id = ?
        """,
        (book_id,)
    )

    db.commit()
    db.close()

    flash(
        "Book deleted.",
        "success"
    )

    return redirect(
        url_for("admin_page")
    )


# ---------------------------------------------------------
# ADMIN REPORT
# ---------------------------------------------------------

@app.route("/admin/report")
@admin_required
def report():

    db = get_db()

    total_orders = db.execute(
        """
        SELECT COUNT(*)
        FROM orders
        """
    ).fetchone()[0]

    total_revenue = db.execute(
        """
        SELECT COALESCE(
            SUM(total),
            0
        )
        FROM orders
        """
    ).fetchone()[0]

    best_selling = db.execute(
        """
        SELECT
            title,
            SUM(quantity)
                AS total_sold

        FROM order_items

        GROUP BY
            book_id,
            title

        ORDER BY
            total_sold DESC

        LIMIT 10
        """
    ).fetchall()

    category_sales = db.execute(
        """
        SELECT
            b.category,
            SUM(oi.quantity)
                AS units_sold,
            SUM(
                oi.price * oi.quantity
            ) AS revenue

        FROM order_items AS oi

        JOIN books AS b
            ON b.id = oi.book_id

        GROUP BY
            b.category

        ORDER BY
            revenue DESC
        """
    ).fetchall()

    db.close()

    return render_template(
        "report.html",
        total_orders=total_orders,
        total_revenue=total_revenue,
        best_selling=best_selling,
        category_sales=category_sales
    )


# ---------------------------------------------------------
# START APPLICATION
# ---------------------------------------------------------

if __name__ == "__main__":

    # Only create the database if it does not already exist.
    # Your existing pageturner.db will NOT be replaced.
    if not os.path.exists(DATABASE):
        init_db()

    app.run(
        debug=True
    )