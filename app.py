from pathlib import Path
from datetime import datetime
import sqlite3

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "pageturner.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"


def get_db():
    """Open the SQLite database for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    """Close the database after the request finishes."""
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    """Create database tables and insert sample books."""
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")

    schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
    db.executescript(schema)

    book_count = db.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    if book_count == 0:
        seed = (BASE_DIR / "seed.sql").read_text(encoding="utf-8")
        db.executescript(seed)
        db.commit()

    db.close()


def get_cart():
    """Return the cart stored in the Flask session."""
    return session.setdefault("cart", {})


def get_cart_items():
    """Get cart books, quantities, subtotals, and total."""
    items = []
    total = 0

    for book_id_text, quantity in get_cart().items():
        book_id = int(book_id_text)

        book = get_db().execute(
            "SELECT * FROM books WHERE id = ?",
            (book_id,),
        ).fetchone()

        if book is not None and quantity > 0:
            subtotal = book["price"] * quantity

            items.append(
                {
                    "book": book,
                    "quantity": quantity,
                    "subtotal": subtotal,
                }
            )

            total += subtotal

    return items, total


@app.context_processor
def add_cart_count():
    """Make the cart count available on every page."""
    count = sum(get_cart().values())
    return {"cart_count": count}


@app.route("/")
def home():
    """Show all books or filter books by category."""
    category = request.args.get("category", "All")

    if category == "All":
        books = get_db().execute(
            "SELECT * FROM books ORDER BY id"
        ).fetchall()
    else:
        books = get_db().execute(
            """
            SELECT * FROM books
            WHERE category = ?
            ORDER BY id
            """,
            (category,),
        ).fetchall()

    categories = get_db().execute(
        """
        SELECT DISTINCT category
        FROM books
        ORDER BY category
        """
    ).fetchall()

    return render_template(
        "home.html",
        books=books,
        categories=categories,
        active_category=category,
    )


@app.route("/book/<int:book_id>")
def book_detail(book_id):
    """Show one book."""
    book = get_db().execute(
        "SELECT * FROM books WHERE id = ?",
        (book_id,),
    ).fetchone()

    if book is None:
        flash("Book not found.", "error")
        return redirect(url_for("home"))

    return render_template("book_detail.html", book=book)


@app.post("/cart/add/<int:book_id>")
def add_to_cart(book_id):
    """Add one copy of a book to the cart."""
    book = get_db().execute(
        "SELECT id, stock FROM books WHERE id = ?",
        (book_id,),
    ).fetchone()

    if book is None:
        flash("Book not found.", "error")
        return redirect(url_for("home"))

    cart = get_cart()
    key = str(book_id)
    current_quantity = int(cart.get(key, 0))

    if current_quantity >= book["stock"]:
        flash("No more stock is available.", "error")
    else:
        cart[key] = current_quantity + 1
        session.modified = True
        flash("Book added to cart.", "success")

    return redirect(request.referrer or url_for("home"))


@app.route("/cart")
def cart_page():
    """Show the shopping cart."""
    items, total = get_cart_items()

    return render_template(
        "cart.html",
        items=items,
        total=total,
    )


@app.post("/cart/update/<int:book_id>")
def update_cart(book_id):
    """Update the quantity of a cart item."""
    try:
        quantity = int(request.form.get("quantity", 0))
    except ValueError:
        quantity = 0

    book = get_db().execute(
        "SELECT stock FROM books WHERE id = ?",
        (book_id,),
    ).fetchone()

    if book is not None:
        if quantity <= 0:
            get_cart().pop(str(book_id), None)
        else:
            get_cart()[str(book_id)] = min(
                quantity,
                book["stock"],
            )

        session.modified = True

    return redirect(url_for("cart_page"))


@app.post("/cart/remove/<int:book_id>")
def remove_from_cart(book_id):
    """Remove a book from the cart."""
    get_cart().pop(str(book_id), None)
    session.modified = True

    flash("Book removed from cart.", "success")
    return redirect(url_for("cart_page"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    """Show checkout or save a new order."""
    items, total = get_cart_items()

    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        customer_name = request.form.get(
            "customer_name",
            "",
        ).strip()

        phone = request.form.get(
            "phone",
            "",
        ).strip()

        address = request.form.get(
            "address",
            "",
        ).strip()

        # Server-side validation.
        if (
            not customer_name
            or not address
            or not phone.isdigit()
            or len(phone) != 10
        ):
            flash(
                "Enter your name, address, and exactly 10 phone digits.",
                "error",
            )

            return render_template(
                "checkout.html",
                items=items,
                total=total,
            )

        db = get_db()

        cursor = db.execute(
            """
            INSERT INTO orders
            (customer_name, phone, address, total, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                customer_name,
                phone,
                address,
                total,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

        db.commit()

        order_id = cursor.lastrowid

        for item in items:
            db.execute(
                """
                INSERT INTO order_items
                (order_id, book_id, quantity, price)
                VALUES (?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["book"]["id"],
                    item["quantity"],
                    item["book"]["price"],
                ),
            )

            db.commit()

            # Bonus: reduce book stock after an order.
            db.execute(
                """
                UPDATE books
                SET stock = stock - ?
                WHERE id = ?
                """,
                (
                    item["quantity"],
                    item["book"]["id"],
                ),
            )

            db.commit()

        session["cart"] = {}

        return redirect(
            url_for(
                "order_confirmation",
                order_id=order_id,
            )
        )

    return render_template(
        "checkout.html",
        items=items,
        total=total,
    )


@app.route("/order/<int:order_id>")
def order_confirmation(order_id):
    """Show the order confirmation using a JOIN."""
    db = get_db()

    order = db.execute(
        "SELECT * FROM orders WHERE id = ?",
        (order_id,),
    ).fetchone()

    if order is None:
        flash("Order not found.", "error")
        return redirect(url_for("home"))

    order_items = db.execute(
        """
        SELECT
            order_items.quantity,
            order_items.price,
            books.title,
            books.author
        FROM order_items
        JOIN books
            ON books.id = order_items.book_id
        WHERE order_items.order_id = ?
        """,
        (order_id,),
    ).fetchall()

    return render_template(
        "order.html",
        order=order,
        order_items=order_items,
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)