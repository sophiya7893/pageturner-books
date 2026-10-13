import csv
import io
import secrets
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    Response,
    session,
    url_for,
)

from werkzeug.utils import secure_filename

from db import get_db
from security import (
    admin_required,
    staff_or_admin_required,
)


# ============================================================
# ADMIN BLUEPRINT
# ============================================================

admin_bp = Blueprint(
    "admin",
    __name__
)


# ============================================================
# ADMIN LOGIN COMPATIBILITY
# ============================================================

# ============================================================
# ADMIN LOGIN
# ============================================================

@admin_bp.route("/admin/login", methods=["GET"])
def admin_login():
    return render_template("admin_login.html")


@admin_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("admin.admin_login"))


    
    # Allow only customer accounts on User Login.
    if user and user["role"] != "customer":
        flash(
            "This login is for customers only. Please use the appropriate login page.",
            "danger"
        )
        return render_template("403.html"), 403


# ============================================================
# STEP 37
# ADMIN DASHBOARD
# ============================================================

@admin_bp.route("/admin")
@admin_bp.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()

    # --------------------------------------------------------
    # ALL BOOKS
    # --------------------------------------------------------

    books = db.execute(
        """
        SELECT *
        FROM books
        ORDER BY title
        """
    ).fetchall()

    book_count = len(books)

    # --------------------------------------------------------
    # TOTAL ORDERS
    # --------------------------------------------------------

    total_orders = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE status != 'Cancelled'
        """
    ).fetchone()["count"]

    # --------------------------------------------------------
    # TOTAL REVENUE
    # --------------------------------------------------------

    total_revenue = db.execute(
        """
        SELECT
            COALESCE(
                SUM(total_amount),
                0
            ) AS total
        FROM orders
        WHERE status != 'Cancelled'
        """
    ).fetchone()["total"]

    total_revenue = float(
        total_revenue or 0
    )

    # --------------------------------------------------------
    # USER COUNT
    # --------------------------------------------------------

    user_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM users
        """
    ).fetchone()["count"]

    # --------------------------------------------------------
    # LOW STOCK
    # --------------------------------------------------------

    low_stock = db.execute(
        """
        SELECT
            id,
            title,
            author,
            stock
        FROM books
        WHERE stock < 5
        ORDER BY
            stock ASC,
            title ASC
        """
    ).fetchall()

    # --------------------------------------------------------
    # ORDER STATUS COUNTS
    # --------------------------------------------------------

    status_counts = db.execute(
        """
        SELECT
            status,
            COUNT(*) AS count
        FROM orders
        GROUP BY status
        ORDER BY status
        """
    ).fetchall()

    # --------------------------------------------------------
    # TOP 5 BOOKS
    # --------------------------------------------------------

    top_books = db.execute(
        """
        SELECT
            b.id,
            b.title,
            b.author,

            COALESCE(
                SUM(oi.quantity),
                0
            ) AS units,

            ROUND(
                COALESCE(
                    SUM(
                        oi.quantity
                        * oi.price_at_purchase
                    ),
                    0
                ),
                2
            ) AS revenue

        FROM order_items oi

        JOIN orders o
            ON o.id = oi.order_id

        JOIN books b
            ON b.id = oi.book_id

        WHERE o.status != 'Cancelled'

        GROUP BY
            b.id,
            b.title,
            b.author

        ORDER BY
            units DESC,
            revenue DESC,
            b.title ASC

        LIMIT 5
        """
    ).fetchall()

    # --------------------------------------------------------
    # RECENT ORDERS
    # --------------------------------------------------------

    recent_orders = db.execute(
        """
        SELECT *
        FROM orders
        ORDER BY created_at DESC
        LIMIT 10
        """
    ).fetchall()

    # --------------------------------------------------------
    # REVENUE - LAST 7 DAYS
    #
    # SQL does the aggregate.
    # Python fills dates with zero revenue.
    # --------------------------------------------------------

    revenue_rows = db.execute(
        """
        SELECT
            date(created_at) AS day,

            ROUND(
                SUM(total_amount),
                2
            ) AS revenue

        FROM orders

        WHERE status != 'Cancelled'
          AND date(created_at)
              >= date(
                  'now',
                  '-6 days'
              )

        GROUP BY
            date(created_at)

        ORDER BY day
        """
    ).fetchall()

    revenue_lookup = {
        row["day"]:
            float(
                row["revenue"] or 0
            )
        for row in revenue_rows
    }

    today = date.today()

    revenue_by_day = []

    for offset in range(6, -1, -1):
        day = (
            today
            - timedelta(
                days=offset
            )
        )

        day_text = day.isoformat()

        revenue_by_day.append({
            "day": day_text,
            "revenue":
                revenue_lookup.get(
                    day_text,
                    0.0
                )
        })
        
        max_revenue = max(
        (
            float(row["revenue"] or 0)
            for row in revenue_by_day
        ),
        default=0
    )

    # Calculate each day's bar width.
    for row in revenue_by_day:
        revenue = float(row["revenue"] or 0)

        row["percentage"] = (
            (revenue / max_revenue) * 100
            if max_revenue > 0
            else 0
        )

    # Pass data to the dashboard template.
    return render_template(
        "admin.html",
        books=books,
        book_count=book_count,
        total_orders=total_orders,
        order_count=total_orders,
        total_revenue=total_revenue,
        revenue=total_revenue,
        user_count=user_count,
        low_stock=low_stock,
        status_counts=status_counts,
        order_status_counts=status_counts,
        top_books=top_books,
        recent_orders=recent_orders,
        revenue_by_day=revenue_by_day,
        max_revenue=max_revenue
    )




    
# ============================================================
# STEP 38
# IMAGE CONTENT DETECTION
# ============================================================

def detect_image_type(data):
    """
    Check actual file bytes rather than trusting
    the filename extension.

    Returns:
        jpg
        png
        webp
        None
    """

    if (
        len(data) >= 3
        and data[:3]
        == b"\xff\xd8\xff"
    ):
        return "jpg"

    if (
        len(data) >= 8
        and data[:8]
        == b"\x89PNG\r\n\x1a\n"
    ):
        return "png"

    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
    ):
        return "webp"

    return None


# ============================================================
# STEP 38
# SAVE IMAGE
# ============================================================

def save_uploaded_image(file):
    """
    Validate and save an uploaded cover image.

    Security:
    - secure_filename()
    - extension allowlist
    - maximum 1 MB
    - actual file signature checked
    - random server-generated filename
    - only filename returned for database storage
    """

    if (
        file is None
        or not file.filename
    ):
        return None

    original_name = secure_filename(
        file.filename
    )

    if "." not in original_name:
        raise ValueError(
            (
                "Image must be JPG, "
                "PNG or WebP."
            )
        )

    extension = (
        original_name
        .rsplit(".", 1)[1]
        .lower()
    )

    allowed_extensions = (
        current_app.config[
            "ALLOWED_IMAGE_EXTENSIONS"
        ]
    )

    if extension not in allowed_extensions:
        raise ValueError(
            (
                "Only JPG, JPEG, PNG "
                "and WebP images are allowed."
            )
        )

    max_size = current_app.config[
        "MAX_IMAGE_SIZE"
    ]

    # Read one byte over the limit.
    # This allows us to detect an oversized file.
    data = file.read(
        max_size + 1
    )

    if len(data) > max_size:
        raise ValueError(
            "Image must be 1 MB or smaller."
        )

    detected = detect_image_type(
        data
    )

    if detected is None:
        raise ValueError(
            (
                "The uploaded file is "
                "not a valid image."
            )
        )

    expected = (
        "jpg"
        if extension in {
            "jpg",
            "jpeg"
        }
        else extension
    )

    if detected != expected:
        raise ValueError(
            (
                "The image extension does "
                "not match the actual "
                "file type."
            )
        )

    upload_folder = Path(
        current_app.config[
            "UPLOAD_FOLDER"
        ]
    )

    upload_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    # Generate our own filename.
    # Never trust the original filename
    # as the saved filename.
    while True:
        new_filename = (
            secrets.token_hex(16)
            + "."
            + detected
        )

        destination = (
            upload_folder
            / new_filename
        )

        if not destination.exists():
            break

    with open(
        destination,
        "wb"
    ) as output_file:
        output_file.write(
            data
        )

    return new_filename


# ============================================================
# ADMIN ADD BOOK
# STEP 34 + STEP 38
# ============================================================

@admin_bp.route(
    "/admin/book/add",
    methods=["GET", "POST"]
)
@admin_required
def admin_add_book():
    if request.method == "GET":
        return render_template(
            "admin_book_form.html",
            book=None
        )

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

    except (ValueError, TypeError):
        flash(
            (
                "Enter a valid price "
                "and stock."
            ),
            "danger"
        )

        return render_template(
            "admin_book_form.html",
            book=None
        )

    if (
        not title
        or not author
        or not category
    ):
        flash(
            (
                "Title, author and category "
                "are required."
            ),
            "danger"
        )

        return render_template(
            "admin_book_form.html",
            book=None
        )

    if price < 0 or stock < 0:
        flash(
            (
                "Price and stock "
                "cannot be negative."
            ),
            "danger"
        )

        return render_template(
            "admin_book_form.html",
            book=None
        )

    try:
        cover_image = save_uploaded_image(
            request.files.get(
                "cover_image_file"
            )
        )

    except ValueError as error:
        flash(
            str(error),
            "danger"
        )

        return render_template(
            "admin_book_form.html",
            book=None
        )

    # Compatibility with existing books/forms.
    if not cover_image:
        cover_image = (
            request.form.get(
                "cover_image",
                ""
            ).strip()
            or None
        )

    db = get_db()

    try:
        db.execute(
            "BEGIN IMMEDIATE"
        )

        cursor = db.execute(
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

        book_id = cursor.lastrowid

        # STEP 34:
        # Starting inventory is represented
        # in stock_log.
        if stock != 0:
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
                    book_id,
                    stock,
                    "initial_stock",
                    session["user_id"]
                )
            )

        db.commit()

    except Exception:
        db.rollback()
        raise

    flash(
        "Book added successfully.",
        "success"
    )

    return redirect(
        url_for(
            "admin.admin_dashboard"
        )
    )


# ============================================================
# ADMIN EDIT BOOK
# STEP 34 + STEP 38
# ============================================================

@admin_bp.route(
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

    if book is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "admin_book_form.html",
            book=book
        )

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

    try:
        price = float(
            request.form.get(
                "price",
                0
            )
        )

        new_stock = int(
            request.form.get(
                "stock",
                0
            )
        )

    except (ValueError, TypeError):
        flash(
            (
                "Enter a valid price "
                "and stock."
            ),
            "danger"
        )

        return redirect(
            url_for(
                "admin.admin_edit_book",
                book_id=book_id
            )
        )

    if (
        not title
        or not author
        or not category
    ):
        flash(
            (
                "Title, author and category "
                "are required."
            ),
            "danger"
        )

        return redirect(
            url_for(
                "admin.admin_edit_book",
                book_id=book_id
            )
        )

    if price < 0 or new_stock < 0:
        flash(
            (
                "Price and stock "
                "cannot be negative."
            ),
            "danger"
        )

        return redirect(
            url_for(
                "admin.admin_edit_book",
                book_id=book_id
            )
        )

    try:
        uploaded_image = save_uploaded_image(
            request.files.get(
                "cover_image_file"
            )
        )

    except ValueError as error:
        flash(
            str(error),
            "danger"
        )

        return redirect(
            url_for(
                "admin.admin_edit_book",
                book_id=book_id
            )
        )

    cover_image = (
        uploaded_image
        or request.form.get(
            "cover_image",
            ""
        ).strip()
        or book["cover_image"]
    )

    old_stock = int(
        book["stock"]
    )

    stock_change = (
        new_stock
        - old_stock
    )

    try:
        db.execute(
            "BEGIN IMMEDIATE"
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
                new_stock,
                description,
                cover_image,
                book_id
            )
        )

        # STEP 34
        if stock_change != 0:
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
                    book_id,
                    stock_change,
                    "admin_edit",
                    session["user_id"]
                )
            )

        db.commit()

    except Exception:
        db.rollback()
        raise

    flash(
        "Book updated successfully.",
        "success"
    )

    return redirect(
        url_for(
            "admin.admin_dashboard"
        )
    )


# ============================================================
# STEP 30
# ADMIN DELETE BOOK
# ============================================================

@admin_bp.route(
    "/admin/book/delete/<int:book_id>",
    methods=["POST"]
)
@admin_bp.route(
    "/admin/delete/<int:book_id>",
    methods=["GET", "POST"]
)
@admin_required
def admin_delete_book(book_id):
    """
    Staff cannot enter this function because
    @admin_required returns HTTP 403 first.

    The compatibility GET route exists so:
        staff GET /admin/delete/1
    produces 403 instead of 405.

    An admin must still use POST to actually delete.
    """

    if request.method == "GET":
        abort(405)

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
            (
                "This book cannot be deleted "
                "because existing records "
                "reference it."
            ),
            "danger"
        )

    return redirect(
        url_for(
            "admin.admin_dashboard"
        )
    )


# ============================================================
# ADMIN ORDERS
# STAFF + ADMIN
# ============================================================

@admin_bp.route("/admin/orders")
@staff_or_admin_required
def admin_orders():
    db = get_db()

    orders = db.execute(
        """
        SELECT *
        FROM orders
        ORDER BY created_at DESC
        """
    ).fetchall()

    return render_template(
        "admin_orders.html",
        orders=orders
    )


# ============================================================
# STEP 30
# STAFF MAY CHANGE ORDER STATUS
# ============================================================

@admin_bp.route(
    "/admin/orders/<int:order_id>/status",
    methods=["POST"]
)
@staff_or_admin_required
def admin_update_order_status(order_id):
    new_status = request.form.get(
        "status",
        ""
    ).strip()

    allowed_statuses = {
        "Placed",
        "Packed",
        "Delivered",
        "Cancelled",
    }

    if new_status not in allowed_statuses:
        flash(
            "Invalid order status.",
            "danger"
        )

        return redirect(
            url_for(
                "admin.admin_orders"
            )
        )

    db = get_db()

    try:
        db.execute(
            "BEGIN IMMEDIATE"
        )

        order = db.execute(
            """
            SELECT
                id,
                status
            FROM orders
            WHERE id = ?
            """,
            (order_id,)
        ).fetchone()

        if order is None:
            db.rollback()

            flash(
                "Order not found.",
                "warning"
            )

            return redirect(
                url_for(
                    "admin.admin_orders"
                )
            )

        old_status = order["status"]

        # If admin/staff changes Placed -> Cancelled,
        # restore stock exactly once.
        if (
            old_status == "Placed"
            and new_status == "Cancelled"
        ):
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

        db.execute(
            """
            UPDATE orders
            SET status = ?
            WHERE id = ?
            """,
            (
                new_status,
                order_id
            )
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    flash(
        "Order status updated.",
        "success"
    )

    return redirect(
        url_for(
            "admin.admin_orders"
        )
    )


# ============================================================
# SALES REPORT
# ============================================================

@admin_bp.route("/admin/report")
@admin_required
def admin_report():
    db = get_db()

    total_orders = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE status != 'Cancelled'
        """
    ).fetchone()["count"]

    total_sales = db.execute(
        """
        SELECT
            COALESCE(
                SUM(total_amount),
                0
            ) AS total
        FROM orders
        WHERE status != 'Cancelled'
        """
    ).fetchone()["total"]

    books_sold = db.execute(
        """
        SELECT
            COALESCE(
                SUM(oi.quantity),
                0
            ) AS total

        FROM order_items oi

        JOIN orders o
            ON o.id = oi.order_id

        WHERE o.status != 'Cancelled'
        """
    ).fetchone()["total"]

    top_books = db.execute(
        """
        SELECT
            b.title,
            b.author,

            SUM(
                oi.quantity
            ) AS quantity_sold,

            ROUND(
                SUM(
                    oi.quantity
                    * oi.price_at_purchase
                ),
                2
            ) AS revenue

        FROM order_items oi

        JOIN books b
            ON b.id = oi.book_id

        JOIN orders o
            ON o.id = oi.order_id

        WHERE o.status != 'Cancelled'

        GROUP BY
            b.id,
            b.title,
            b.author

        ORDER BY
            quantity_sold DESC,
            revenue DESC

        LIMIT 10
        """
    ).fetchall()

    return render_template(
        "report.html",
        total_orders=total_orders,
        total_sales=total_sales,
        books_sold=books_sold,
        top_books=top_books
    )


# ============================================================
# CSV EXPORT
# ADMIN ONLY
# ============================================================

@admin_bp.route("/admin/export")
@admin_required
def admin_export():
    db = get_db()

    orders = db.execute(
        """
        SELECT
            id,
            customer_name,
            email,
            phone,
            address_snapshot,
            total_amount,
            discount_amount,
            coupon_code,
            status,
            created_at

        FROM orders

        ORDER BY
            created_at DESC
        """
    ).fetchall()

    output = io.StringIO()

    writer = csv.writer(
        output
    )

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
        "Created At",
    ])

    for order in orders:
        writer.writerow([
            order["id"],
            order["customer_name"],
            order["email"],
            order["phone"],
            order["address_snapshot"],
            order["total_amount"],
            order["discount_amount"],
            order["coupon_code"],
            order["status"],
            order["created_at"],
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )

    response.headers[
        "Content-Disposition"
    ] = (
        "attachment; "
        "filename=orders.csv"
    )

    return response