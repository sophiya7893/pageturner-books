
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
from security import admin_required, staff_or_admin_required


admin_bp = Blueprint("admin", __name__)


from order_rules import ALLOWED_STATUS_MOVES

# ============================================================
# DATABASE HELPERS
# ============================================================

def table_exists(db, table_name):
    return db.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone() is not None


def table_columns(db, table_name):
    if not table_exists(db, table_name):
        return set()

    return {
        row["name"]
        for row in db.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    }


def require_table(db, table_name):
    if not table_exists(db, table_name):
        abort(500, description=f"Required database table '{table_name}' is missing.")


def money_text(paise):
    paise = int(paise or 0)
    sign = "-" if paise < 0 else ""
    rupees, remainder = divmod(abs(paise), 100)
    return f"{sign}{rupees}.{remainder:02d}"


def parse_rupees_to_paise(value):
    value = str(value or "").strip()

    if not value:
        raise ValueError("Price is required.")

    if value.startswith("-"):
        raise ValueError("Price cannot be negative.")

    parts = value.split(".")

    if len(parts) > 2:
        raise ValueError("Enter a valid price.")

    rupees = parts[0] or "0"
    paise = parts[1] if len(parts) == 2 else ""

    if not rupees.isdigit():
        raise ValueError("Enter a valid price.")

    if paise and not paise.isdigit():
        raise ValueError("Enter a valid price.")

    if len(paise) > 2:
        raise ValueError("Price can have at most 2 decimal places.")

    return int(rupees) * 100 + int(paise.ljust(2, "0") or "0")


def clean_names(values):
    result = []
    seen = set()

    for value in values:
        name = str(value or "").strip()
        key = name.casefold()

        if name and key not in seen:
            seen.add(key)
            result.append(name)

    return result


def get_form_names(field_name):
    values = request.form.getlist(field_name)
    names = []

    for value in values:
        names.extend(value.split(","))

    return clean_names(names)


def get_book_category_names(db, book_id):
    if not table_exists(db, "book_categories"):
        return []

    return [
        row["name"]
        for row in db.execute(
            """
            SELECT c.name
            FROM categories c
            JOIN book_categories bc ON bc.category_id = c.id
            WHERE bc.book_id = ?
            ORDER BY c.name
            """,
            (book_id,),
        ).fetchall()
    ]


def get_book_tag_names(db, book_id):
    if not table_exists(db, "book_tags"):
        return []

    return [
        row["name"]
        for row in db.execute(
            """
            SELECT t.name
            FROM tags t
            JOIN book_tags bt ON bt.tag_id = t.id
            WHERE bt.book_id = ?
            ORDER BY t.name
            """,
            (book_id,),
        ).fetchall()
    ]


def set_book_categories(db, book_id, names):
    if not table_exists(db, "categories") or not table_exists(db, "book_categories"):
        return

    db.execute("DELETE FROM book_categories WHERE book_id = ?", (book_id,))

    for name in names:
        db.execute(
            "INSERT OR IGNORE INTO categories(name) VALUES (?)",
            (name,),
        )

        category = db.execute(
            "SELECT id FROM categories WHERE name = ? COLLATE NOCASE",
            (name,),
        ).fetchone()

        if category:
            db.execute(
                """
                INSERT OR IGNORE INTO book_categories(book_id, category_id)
                VALUES (?, ?)
                """,
                (book_id, category["id"]),
            )


def set_book_tags(db, book_id, names):
    if not table_exists(db, "tags") or not table_exists(db, "book_tags"):
        return

    db.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))

    for name in names:
        db.execute(
            "INSERT OR IGNORE INTO tags(name) VALUES (?)",
            (name,),
        )

        tag = db.execute(
            "SELECT id FROM tags WHERE name = ? COLLATE NOCASE",
            (name,),
        ).fetchone()

        if tag:
            db.execute(
                """
                INSERT OR IGNORE INTO book_tags(book_id, tag_id)
                VALUES (?, ?)
                """,
                (book_id, tag["id"]),
            )


# ============================================================
# ADMIN LOGIN / LOGOUT
# ============================================================

@admin_bp.route("/admin/login", methods=["GET"])
def admin_login():
    return render_template("admin_login.html")


@admin_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin.admin_login"))


# ============================================================
# DASHBOARD
# ============================================================

@admin_bp.route("/admin")
@admin_bp.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    require_table(db, "books")
    require_table(db, "orders")
    require_table(db, "users")

    book_columns = table_columns(db, "books")
    order_columns = table_columns(db, "orders")
    item_columns = table_columns(db, "order_items")

    if table_exists(db, "book_categories") and table_exists(db, "categories"):
        books = db.execute(
            """
            SELECT b.*,
                   COALESCE(GROUP_CONCAT(DISTINCT c.name), '') AS category_names
            FROM books b
            LEFT JOIN book_categories bc ON bc.book_id = b.id
            LEFT JOIN categories c ON c.id = bc.category_id
            GROUP BY b.id
            ORDER BY b.title
            """
        ).fetchall()
    else:
        books = db.execute("SELECT * FROM books ORDER BY title").fetchall()

    book_count = len(books)

    total_orders = db.execute(
        "SELECT COUNT(*) AS count FROM orders WHERE status != 'Cancelled'"
    ).fetchone()["count"]

    total_revenue_paise = db.execute(
        """
        SELECT COALESCE(SUM(total_paise), 0) AS total
        FROM orders
        WHERE status != 'Cancelled'
        """
    ).fetchone()["total"] if "total_paise" in order_columns else 0

    user_count = db.execute(
        "SELECT COUNT(*) AS count FROM users"
    ).fetchone()["count"]

    low_stock = db.execute(
        """
        SELECT id, title, author, stock
        FROM books
        WHERE stock < 5
        ORDER BY stock, title
        """
    ).fetchall() if "stock" in book_columns else []

    status_counts = db.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM orders
        GROUP BY status
        ORDER BY status
        """
    ).fetchall() if "status" in order_columns else []

    top_books = []

    if (
        table_exists(db, "order_items")
        and "price_paise" in item_columns
        and {"order_id", "book_id", "quantity", "price_paise"}.issubset(item_columns)
    ):
        top_books = db.execute(
            """
            SELECT b.id, b.title, b.author,
                   COALESCE(SUM(oi.quantity), 0) AS units,
                   COALESCE(SUM(oi.quantity * oi.price_paise), 0) AS revenue_paise
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN books b ON b.id = oi.book_id
            WHERE o.status != 'Cancelled'
            GROUP BY b.id, b.title, b.author
            ORDER BY units DESC, revenue_paise DESC, b.title
            LIMIT 5
            """
        ).fetchall()

    recent_orders = db.execute(
        """
        SELECT *
        FROM orders
        ORDER BY created_at DESC, id DESC
        LIMIT 10
        """
    ).fetchall() if "created_at" in order_columns else db.execute(
        "SELECT * FROM orders ORDER BY id DESC LIMIT 10"
    ).fetchall()

    revenue_by_day = []

    if "created_at" in order_columns and "total_paise" in order_columns:
        revenue_rows = db.execute(
            """
            SELECT date(created_at) AS day,
                   COALESCE(SUM(total_paise), 0) AS revenue_paise
            FROM orders
            WHERE status != 'Cancelled'
              AND date(created_at) >= date('now', '-6 days')
            GROUP BY date(created_at)
            """
        ).fetchall()

        lookup = {row["day"]: int(row["revenue_paise"] or 0) for row in revenue_rows}

        for offset in range(6, -1, -1):
            day = date.today() - timedelta(days=offset)
            revenue_by_day.append({
                "day": day.isoformat(),
                "revenue_paise": lookup.get(day.isoformat(), 0),
                "percentage": 0,
            })

        maximum = max((row["revenue_paise"] for row in revenue_by_day), default=0)

        for row in revenue_by_day:
            row["percentage"] = (
                row["revenue_paise"] * 100 / maximum
                if maximum else 0
            )

    return render_template(
        "admin.html",
        books=books,
        book_count=book_count,
        total_orders=total_orders,
        order_count=total_orders,
        total_revenue_paise=int(total_revenue_paise or 0),
        user_count=user_count,
        low_stock=low_stock,
        status_counts=status_counts,
        order_status_counts=status_counts,
        top_books=top_books,
        recent_orders=recent_orders,
        revenue_by_day=revenue_by_day,
        max_revenue_paise=max(
            (row["revenue_paise"] for row in revenue_by_day),
            default=0,
        ),
    )


# ============================================================
# BOOK IMAGE UPLOAD
# ============================================================

def detect_image_type(data):
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_uploaded_image(file):
    if file is None or not file.filename:
        return None

    filename = secure_filename(file.filename)

    if "." not in filename:
        raise ValueError("Image must be JPG, PNG or WebP.")

    extension = filename.rsplit(".", 1)[1].lower()

    if extension not in {"jpg", "jpeg", "png", "webp"}:
        raise ValueError("Only JPG, JPEG, PNG and WebP images are allowed.")

    max_size = current_app.config.get("MAX_IMAGE_SIZE", 1024 * 1024)
    data = file.read(max_size + 1)

    if len(data) > max_size:
        raise ValueError("Image must be 1 MB or smaller.")

    detected = detect_image_type(data)

    if not detected:
        raise ValueError("The uploaded file is not a valid image.")

    expected = "jpg" if extension in {"jpg", "jpeg"} else extension

    if detected != expected:
        raise ValueError("The image extension does not match its file type.")

    upload_folder = Path(
        current_app.config.get(
            "UPLOAD_FOLDER",
            str(Path(current_app.root_path) / "static" / "uploads"),
        )
    )
    upload_folder.mkdir(parents=True, exist_ok=True)

    new_filename = secrets.token_hex(16) + "." + detected
    destination = upload_folder / new_filename
    destination.write_bytes(data)

    return new_filename


# ============================================================
# ADD BOOK
# ============================================================

@admin_bp.route("/admin/book/add", methods=["GET", "POST"])
@admin_required
def admin_add_book():
    db = get_db()

    if request.method == "GET":
        categories = db.execute(
            "SELECT id, name FROM categories ORDER BY name"
        ).fetchall() if table_exists(db, "categories") else []

        tags = db.execute(
            "SELECT id, name FROM tags ORDER BY name"
        ).fetchall() if table_exists(db, "tags") else []

        return render_template(
            "admin_book_form.html",
            book=None,
            categories=categories,
            tags=tags,
            selected_categories=[],
            selected_tags=[],
        )

    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    description = request.form.get("description", "").strip()

    category_names = get_form_names("categories")
    if not category_names:
        category_names = clean_names([request.form.get("category", "")])

    tag_names = get_form_names("tags")
    if not tag_names:
        tag_names = clean_names(request.form.get("tag", "").split(","))

    try:
        price_paise = parse_rupees_to_paise(request.form.get("price"))
        stock = int(request.form.get("stock", "0"))
        if stock < 0:
            raise ValueError("Stock cannot be negative.")
    except (ValueError, TypeError) as error:
        flash(str(error), "danger")
        return redirect(url_for("admin.admin_add_book"))

    if not title or not author or not category_names:
        flash("Title, author and at least one category are required.", "danger")
        return redirect(url_for("admin.admin_add_book"))

    try:
        cover_image = save_uploaded_image(request.files.get("cover_image_file"))
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("admin.admin_add_book"))

    if not cover_image:
        cover_image = request.form.get("cover_image", "").strip() or None

    columns = table_columns(db, "books")
    insert_columns = ["title", "author", "category", "price_paise", "stock"]
    values = [title, author, category_names[0], price_paise, stock]

    if "price" in columns:
        insert_columns.append("price")
        values.append(money_text(price_paise))

    if "description" in columns:
        insert_columns.append("description")
        values.append(description)

    if "cover_image" in columns:
        insert_columns.append("cover_image")
        values.append(cover_image)

    placeholders = ", ".join("?" for _ in insert_columns)
    column_sql = ", ".join(f'"{column}"' for column in insert_columns)

    try:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute(
            f"INSERT INTO books ({column_sql}) VALUES ({placeholders})",
            values,
        )
        book_id = cursor.lastrowid

        set_book_categories(db, book_id, category_names)
        set_book_tags(db, book_id, tag_names)

        if stock and table_exists(db, "stock_log"):
            db.execute(
                """
                INSERT INTO stock_log(book_id, change, reason, user_id)
                VALUES (?, ?, 'initial_stock', ?)
                """,
                (book_id, stock, session.get("user_id")),
            )

        db.commit()
    except Exception:
        db.rollback()
        current_app.logger.exception("Could not add book")
        flash("The book could not be added. Check the application log.", "danger")
        return redirect(url_for("admin.admin_add_book"))

    flash("Book added successfully.", "success")
    return redirect(url_for("admin.admin_dashboard"))


# ============================================================
# EDIT BOOK
# ============================================================

@admin_bp.route("/admin/book/edit/<int:book_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_book(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    if book is None:
        abort(404)

    if request.method == "GET":
        categories = db.execute(
            "SELECT id, name FROM categories ORDER BY name"
        ).fetchall() if table_exists(db, "categories") else []

        tags = db.execute(
            "SELECT id, name FROM tags ORDER BY name"
        ).fetchall() if table_exists(db, "tags") else []

        return render_template(
            "admin_book_form.html",
            book=book,
            categories=categories,
            tags=tags,
            selected_categories=get_book_category_names(db, book_id),
            selected_tags=get_book_tag_names(db, book_id),
        )

    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    description = request.form.get("description", "").strip()

    category_names = get_form_names("categories")
    if not category_names:
        category_names = clean_names([request.form.get("category", "")])

    tag_names = get_form_names("tags")
    if not tag_names:
        tag_names = clean_names(request.form.get("tag", "").split(","))

    try:
        price_paise = parse_rupees_to_paise(request.form.get("price"))
        new_stock = int(request.form.get("stock", "0"))
        if new_stock < 0:
            raise ValueError("Stock cannot be negative.")
    except (ValueError, TypeError) as error:
        flash(str(error), "danger")
        return redirect(url_for("admin.admin_edit_book", book_id=book_id))

    if not title or not author or not category_names:
        flash("Title, author and at least one category are required.", "danger")
        return redirect(url_for("admin.admin_edit_book", book_id=book_id))

    try:
        uploaded_image = save_uploaded_image(request.files.get("cover_image_file"))
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("admin.admin_edit_book", book_id=book_id))

    cover_image = (
        uploaded_image
        or request.form.get("cover_image", "").strip()
        or book["cover_image"]
    )

    old_stock = int(book["stock"] or 0)
    stock_change = new_stock - old_stock
    columns = table_columns(db, "books")

    updates = {
        "title": title,
        "author": author,
        "category": category_names[0],
        "price_paise": price_paise,
        "stock": new_stock,
    }

    if "price" in columns:
        updates["price"] = money_text(price_paise)
    if "description" in columns:
        updates["description"] = description
    if "cover_image" in columns:
        updates["cover_image"] = cover_image

    set_sql = ", ".join(f'"{column}" = ?' for column in updates)

    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            f"UPDATE books SET {set_sql} WHERE id = ?",
            list(updates.values()) + [book_id],
        )

        set_book_categories(db, book_id, category_names)
        set_book_tags(db, book_id, tag_names)

        if stock_change and table_exists(db, "stock_log"):
            db.execute(
                """
                INSERT INTO stock_log(book_id, change, reason, user_id)
                VALUES (?, ?, 'admin_edit', ?)
                """,
                (book_id, stock_change, session.get("user_id")),
            )

        db.commit()
    except Exception:
        db.rollback()
        current_app.logger.exception("Could not update book")
        flash("The book could not be updated.", "danger")
        return redirect(url_for("admin.admin_edit_book", book_id=book_id))

    flash("Book updated successfully.", "success")
    return redirect(url_for("admin.admin_dashboard"))


# ============================================================
# DELETE BOOK
# ============================================================

@admin_bp.route("/admin/book/delete/<int:book_id>", methods=["POST"])
@admin_bp.route("/admin/delete/<int:book_id>", methods=["POST"])
@admin_required
def admin_delete_book(book_id):
    db = get_db()

    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM books WHERE id = ?", (book_id,))
        db.commit()
        flash("Book deleted successfully.", "success")
    except sqlite3.IntegrityError:
        db.rollback()
        flash(
            "This book cannot be deleted because existing records reference it.",
            "danger",
        )
    except Exception:
        db.rollback()
        current_app.logger.exception("Could not delete book")
        flash("The book could not be deleted.", "danger")

    return redirect(url_for("admin.admin_dashboard"))


# ============================================================
# ADMIN ORDERS
# ============================================================

@admin_bp.route("/admin/orders")
@staff_or_admin_required
def admin_orders():
    db = get_db()
    require_table(db, "orders")

    orders = db.execute(
        """
        SELECT o.*,
               (SELECT COUNT(*) FROM order_items oi
                WHERE oi.order_id = o.id) AS line_count,
               (SELECT COALESCE(SUM(oi.quantity), 0)
                FROM order_items oi
                WHERE oi.order_id = o.id) AS item_count
        FROM orders o
        ORDER BY o.created_at DESC, o.id DESC
        """
    ).fetchall()

    return render_template(
        "admin_orders.html",
        orders=orders,
        allowed_status_moves=ALLOWED_STATUS_MOVES,
    )


@admin_bp.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@staff_or_admin_required
def admin_update_order_status(order_id):
    new_status = request.form.get("status", "").strip()
    note = request.form.get("note", "").strip()
    changed_by = session.get("user_id")

    if new_status not in ALLOWED_STATUS_MOVES:
        flash("Invalid order status.", "danger")
        return redirect(url_for("admin.admin_orders"))

    if not changed_by:
        abort(403)

    db = get_db()
    old_status = None

    try:
        db.execute("BEGIN IMMEDIATE")

        order = db.execute(
            "SELECT id, status FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()

        if order is None:
            db.rollback()
            flash("Order not found.", "warning")
            return redirect(url_for("admin.admin_orders"))

        old_status = order["status"]

        if old_status not in ALLOWED_STATUS_MOVES:
            db.rollback()
            flash("This order has an invalid current status.", "danger")
            return redirect(url_for("admin.admin_orders"))

        if new_status == old_status:
            db.rollback()
            flash(f"The order is already {old_status}.", "warning")
            return redirect(url_for("admin.admin_orders"))

        if new_status not in ALLOWED_STATUS_MOVES[old_status]:
            db.rollback()
            flash(
                f"Status change refused: {old_status} to {new_status} is not allowed.",
                "danger",
            )
            return redirect(url_for("admin.admin_orders"))

        if new_status == "Cancelled":
            items = db.execute(
                "SELECT book_id, quantity FROM order_items WHERE order_id = ?",
                (order_id,),
            ).fetchall()

            for item in items:
                cursor = db.execute(
                    "UPDATE books SET stock = stock + ? WHERE id = ?",
                    (item["quantity"], item["book_id"]),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError("Could not restore book stock.")

                if table_exists(db, "stock_log"):
                    db.execute(
                        """
                        INSERT INTO stock_log(book_id, change, reason, user_id)
                        VALUES (?, ?, 'cancelled_order', ?)
                        """,
                        (item["book_id"], item["quantity"], changed_by),
                    )

        cursor = db.execute(
            "UPDATE orders SET status = ? WHERE id = ? AND status = ?",
            (new_status, order_id, old_status),
        )

        if cursor.rowcount != 1:
            raise RuntimeError("Order status changed during this request.")

        if table_exists(db, "order_status_history"):
            history_columns = table_columns(db, "order_status_history")
            insert_columns = ["order_id", "status", "changed_by"]
            values = [order_id, new_status, changed_by]

            if "note" in history_columns:
                insert_columns.append("note")
                values.append(note or None)

            sql_columns = ", ".join(insert_columns)
            placeholders = ", ".join("?" for _ in values)

            db.execute(
                f"INSERT INTO order_status_history ({sql_columns}) VALUES ({placeholders})",
                values,
            )

        db.commit()

    except Exception:
        db.rollback()
        current_app.logger.exception("Order status update failed")
        flash("The order status could not be updated. No changes were saved.", "danger")
        return redirect(url_for("admin.admin_orders"))

    flash(
        f"Order #{order_id} changed from {old_status} to {new_status}.",
        "success",
    )
    return redirect(url_for("admin.admin_orders"))


# ============================================================
# ADMIN COUPONS
# Uses schema.sql: coupons and coupon_uses
# ============================================================

@admin_bp.route("/admin/coupons")
@admin_required
def admin_coupons():
    db = get_db()
    require_table(db, "coupons")

    coupons = db.execute(
        """
        SELECT c.*,
               (SELECT COUNT(*)
                FROM coupon_uses cu
                WHERE cu.coupon_id = c.id) AS usage_count
        FROM coupons c
        ORDER BY c.created_at DESC, c.id DESC
        """
    ).fetchall() if table_exists(db, "coupon_uses") else db.execute(
        "SELECT * FROM coupons ORDER BY created_at DESC, id DESC"
    ).fetchall()

    return render_template("admin_coupons.html", coupons=coupons)


@admin_bp.route("/admin/coupons/add", methods=["GET", "POST"])
@admin_required
def admin_add_coupon():
    db = get_db()
    require_table(db, "coupons")

    if request.method == "GET":
        categories = db.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE").fetchall()
        return render_template("admin_coupon_form.html", coupon=None, categories=categories)

    code = request.form.get("code", "").strip().upper()
    expiry_date = request.form.get("expiry_date", "").strip() or None

    try:
        percent = int(request.form.get("percent", ""))
    except (ValueError, TypeError):
        flash("Enter a valid discount percentage.", "danger")
        return redirect(url_for("admin.admin_add_coupon"))

    if not code:
        flash("Coupon code is required.", "danger")
        return redirect(url_for("admin.admin_add_coupon"))

    if not code.replace("-", "").replace("_", "").isalnum():
        flash("Use only letters, numbers, hyphens or underscores in the coupon code.", "danger")
        return redirect(url_for("admin.admin_add_coupon"))

    if not 1 <= percent <= 100:
        flash("Discount percentage must be between 1 and 100.", "danger")
        return redirect(url_for("admin.admin_add_coupon"))

    if expiry_date:
        try:
            date.fromisoformat(expiry_date)
        except ValueError:
            flash("Enter a valid expiry date.", "danger")
            return redirect(url_for("admin.admin_add_coupon"))

    try:
        min_order_paise = parse_rupees_to_paise(request.form.get("min_order", "0") or "0")
        max_text = request.form.get("max_discount", "").strip()
        max_discount_paise = parse_rupees_to_paise(max_text) if max_text else None
        usage_text = request.form.get("usage_limit", "").strip()
        usage_limit = int(usage_text) if usage_text else None
        if usage_limit is not None and usage_limit < 1:
            raise ValueError("Usage limit must be at least 1.")
        category_text = request.form.get("category_id", "").strip()
        category_id = int(category_text) if category_text else None
        if category_id is not None and not db.execute("SELECT 1 FROM categories WHERE id=?", (category_id,)).fetchone():
            raise ValueError("Select a valid category.")
        one_use = 1 if request.form.get("one_use_per_customer") == "1" else 0
        db.execute(
            """
            INSERT INTO coupons(
                code, percent, expiry_date, active, discount_type, discount_value,
                min_order_paise, max_discount_paise, end_date, usage_limit,
                is_active, one_use_per_customer, category_id
            ) VALUES (?, ?, ?, 1, 'percentage', ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (code, percent, expiry_date, percent, min_order_paise,
             max_discount_paise, expiry_date, usage_limit, one_use, category_id),
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("admin.admin_add_coupon"))
    except sqlite3.IntegrityError:
        db.rollback()
        flash("That coupon code already exists.", "danger")
        return redirect(url_for("admin.admin_add_coupon"))

    flash("Coupon created successfully.", "success")
    return redirect(url_for("admin.admin_coupons"))


@admin_bp.route("/admin/coupons/edit/<int:coupon_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_coupon(coupon_id):
    db = get_db()
    require_table(db, "coupons")

    coupon = db.execute(
        "SELECT * FROM coupons WHERE id = ?",
        (coupon_id,),
    ).fetchone()

    if coupon is None:
        abort(404)

    if request.method == "GET":
        categories = db.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE").fetchall()
        return render_template("admin_coupon_form.html", coupon=coupon, categories=categories)

    code = request.form.get("code", "").strip().upper()
    expiry_date = request.form.get("expiry_date", "").strip() or None

    try:
        percent = int(request.form.get("percent", ""))
    except (ValueError, TypeError):
        flash("Enter a valid discount percentage.", "danger")
        return redirect(url_for("admin.admin_edit_coupon", coupon_id=coupon_id))

    if not code or not 1 <= percent <= 100:
        flash("Enter a coupon code and a percentage between 1 and 100.", "danger")
        return redirect(url_for("admin.admin_edit_coupon", coupon_id=coupon_id))

    if expiry_date:
        try:
            date.fromisoformat(expiry_date)
        except ValueError:
            flash("Enter a valid expiry date.", "danger")
            return redirect(url_for("admin.admin_edit_coupon", coupon_id=coupon_id))

    try:
        min_order_paise = parse_rupees_to_paise(request.form.get("min_order", "0") or "0")
        max_text = request.form.get("max_discount", "").strip()
        max_discount_paise = parse_rupees_to_paise(max_text) if max_text else None
        usage_text = request.form.get("usage_limit", "").strip()
        usage_limit = int(usage_text) if usage_text else None
        if usage_limit is not None and usage_limit < 1:
            raise ValueError("Usage limit must be at least 1.")
        category_text = request.form.get("category_id", "").strip()
        category_id = int(category_text) if category_text else None
        if category_id is not None and not db.execute("SELECT 1 FROM categories WHERE id=?", (category_id,)).fetchone():
            raise ValueError("Select a valid category.")
        one_use = 1 if request.form.get("one_use_per_customer") == "1" else 0
        db.execute(
            """
            UPDATE coupons SET code=?, percent=?, expiry_date=?, discount_type='percentage',
                discount_value=?, min_order_paise=?, max_discount_paise=?, end_date=?,
                usage_limit=?, is_active=active, one_use_per_customer=?, category_id=?
            WHERE id=?
            """,
            (code, percent, expiry_date, percent, min_order_paise, max_discount_paise,
             expiry_date, usage_limit, one_use, category_id, coupon_id),
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("admin.admin_edit_coupon", coupon_id=coupon_id))
    except sqlite3.IntegrityError:
        db.rollback()
        flash("That coupon code already exists.", "danger")
        return redirect(url_for("admin.admin_edit_coupon", coupon_id=coupon_id))

    flash("Coupon updated successfully.", "success")
    return redirect(url_for("admin.admin_coupons"))


@admin_bp.route("/admin/coupons/<int:coupon_id>/toggle", methods=["POST"])
@admin_required
def admin_toggle_coupon(coupon_id):
    db = get_db()
    require_table(db, "coupons")

    coupon = db.execute(
        "SELECT id, active FROM coupons WHERE id = ?",
        (coupon_id,),
    ).fetchone()

    if coupon is None:
        abort(404)

    db.execute(
        "UPDATE coupons SET active = ?, is_active = ? WHERE id = ?",
        (0 if coupon["active"] else 1, 0 if coupon["active"] else 1, coupon_id),
    )
    db.commit()

    flash("Coupon status updated.", "success")
    return redirect(url_for("admin.admin_coupons"))


@admin_bp.route("/admin/coupons/<int:coupon_id>/delete", methods=["POST"])
@admin_required
def admin_delete_coupon(coupon_id):
    db = get_db()
    require_table(db, "coupons")

    try:
        db.execute("DELETE FROM coupons WHERE id = ?", (coupon_id,))
        db.commit()
        flash("Coupon deleted successfully.", "success")
    except sqlite3.IntegrityError:
        db.rollback()
        flash(
            "This coupon has usage history and cannot be deleted. Disable it instead.",
            "warning",
        )

    return redirect(url_for("admin.admin_coupons"))


# ============================================================
# ADMIN RETURNS
# Uses schema.sql: returns and return_items
# ============================================================

@admin_bp.route("/admin/returns")
@staff_or_admin_required
def admin_returns():
    db = get_db()
    require_table(db, "returns")
    require_table(db, "orders")
    require_table(db, "users")

    return_columns = table_columns(db, "returns")
    order_columns = table_columns(db, "orders")
    user_columns = table_columns(db, "users")

    order_customer_column = (
        "customer_name" if "customer_name" in order_columns else None
    )
    user_name_column = "name" if "name" in user_columns else None

    select_customer = (
        f"o.{order_customer_column}"
        if order_customer_column
        else (f"u.{user_name_column}" if user_name_column else "CAST(r.user_id AS TEXT)")
    )

    returns = db.execute(
        f"""
        SELECT r.*,
               o.status AS order_status,
               {select_customer} AS customer_name,
               u.email AS customer_email
        FROM returns r
        LEFT JOIN orders o ON o.id = r.order_id
        LEFT JOIN users u ON u.id = r.user_id
        ORDER BY r.created_at DESC, r.id DESC
        """
    ).fetchall()

    details = {}

    if table_exists(db, "return_items") and table_exists(db, "order_items"):
        item_columns = table_columns(db, "order_items")
        book_columns = table_columns(db, "books")

        title_select = "b.title" if "title" in book_columns else "CAST(oi.book_id AS TEXT)"
        price_select = "oi.price_paise" if "price_paise" in item_columns else "0"

        rows = db.execute(
            f"""
            SELECT ri.return_id, ri.quantity, ri.reason,
                   oi.book_id, {title_select} AS title,
                   {price_select} AS price_paise
            FROM return_items ri
            JOIN order_items oi ON oi.id = ri.order_item_id
            LEFT JOIN books b ON b.id = oi.book_id
            ORDER BY ri.return_id DESC
            """
        ).fetchall()

        for row in rows:
            details.setdefault(row["return_id"], []).append(row)

    return render_template(
        "admin_returns.html",
        returns=returns,
        return_items=details,
    )


@admin_bp.route("/admin/returns/<int:return_id>/status", methods=["POST"])
@staff_or_admin_required
def admin_update_return_status(return_id):
    new_status = request.form.get("status", "").strip()

    if new_status not in {"Approved", "Rejected"}:
        flash("Choose Approved or Rejected.", "danger")
        return redirect(url_for("admin.admin_returns"))

    db = get_db()
    require_table(db, "returns")

    return_columns = table_columns(db, "returns")
    changed_by = session.get("user_id")

    if not changed_by:
        abort(403)

    try:
        db.execute("BEGIN IMMEDIATE")

        return_request = db.execute(
            "SELECT * FROM returns WHERE id = ?",
            (return_id,),
        ).fetchone()

        if return_request is None:
            db.rollback()
            abort(404)

        if return_request["status"] != "Pending":
            db.rollback()
            flash("This return request has already been reviewed.", "warning")
            return redirect(url_for("admin.admin_returns"))

        if new_status == "Approved":
            return_columns_now = table_columns(db, "returns")
            if "order_item_id" in return_columns_now and "quantity" in return_columns_now:
                returned_items = db.execute(
                    "SELECT oi.book_id, r.quantity FROM returns r JOIN order_items oi ON oi.id=r.order_item_id WHERE r.id=?",
                    (return_id,),
                ).fetchall()
            elif table_exists(db, "return_items"):
                returned_items = db.execute(
                    "SELECT oi.book_id, ri.quantity FROM return_items ri JOIN order_items oi ON oi.id=ri.order_item_id WHERE ri.return_id=?",
                    (return_id,),
                ).fetchall()
            else:
                returned_items = []
            for item in returned_items:
                db.execute("UPDATE books SET stock=stock+? WHERE id=?", (int(item["quantity"]), int(item["book_id"])))
                if table_exists(db, "stock_log"):
                    db.execute("INSERT INTO stock_log(book_id, change, reason, user_id) VALUES (?, ?, 'returned_order', ?)", (int(item["book_id"]), int(item["quantity"]), changed_by))

        updates = ["status = ?"]
        values = [new_status]

        if "reviewed_by" in return_columns:
            updates.append("reviewed_by = ?")
            values.append(changed_by)

        if "reviewed_at" in return_columns:
            updates.append("reviewed_at = CURRENT_TIMESTAMP")

        values.append(return_id)

        db.execute(
            f"UPDATE returns SET {', '.join(updates)} WHERE id = ?",
            values,
        )

        db.commit()

    except Exception:
        db.rollback()
        current_app.logger.exception("Return review failed")
        flash("The return request could not be updated.", "danger")
        return redirect(url_for("admin.admin_returns"))

    flash(f"Return request #{return_id} marked {new_status.lower()}.", "success")
    return redirect(url_for("admin.admin_returns"))


# ============================================================
# SALES REPORT
# ============================================================

@admin_bp.route("/admin/report")
@admin_required
def admin_report():
    db = get_db()
    require_table(db, "orders")

    total_orders = db.execute(
        "SELECT COUNT(*) AS count FROM orders WHERE status != 'Cancelled'"
    ).fetchone()["count"]

    order_columns = table_columns(db, "orders")
    total_sales_paise = (
        db.execute(
            """
            SELECT COALESCE(SUM(total_paise), 0) AS total
            FROM orders
            WHERE status != 'Cancelled'
            """
        ).fetchone()["total"]
        if "total_paise" in order_columns
        else 0
    )

    books_sold = 0
    top_books = []
    category_orders = []

    if table_exists(db, "order_items"):
        books_sold = db.execute(
            """
            SELECT COALESCE(SUM(oi.quantity), 0) AS total
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.status != 'Cancelled'
            """
        ).fetchone()["total"]

        item_columns = table_columns(db, "order_items")

        if "price_paise" in item_columns:
            top_books = db.execute(
                """
                SELECT b.id, b.title, b.author,
                       SUM(oi.quantity) AS quantity_sold,
                       COALESCE(SUM(oi.quantity * oi.price_paise), 0) AS revenue_paise
                FROM order_items oi
                JOIN books b ON b.id = oi.book_id
                JOIN orders o ON o.id = oi.order_id
                WHERE o.status != 'Cancelled'
                GROUP BY b.id, b.title, b.author
                ORDER BY quantity_sold DESC, revenue_paise DESC, b.title
                LIMIT 10
                """
            ).fetchall()

    if table_exists(db, "categories") and table_exists(db, "book_categories"):
        category_orders = db.execute(
            """
            SELECT c.id, c.name,
                   COUNT(DISTINCT o.id) AS order_count,
                   COALESCE(SUM(oi.quantity), 0) AS units_sold
            FROM categories c
            LEFT JOIN book_categories bc ON bc.category_id = c.id
            LEFT JOIN order_items oi ON oi.book_id = bc.book_id
            LEFT JOIN orders o ON o.id = oi.order_id
                               AND o.status != 'Cancelled'
            GROUP BY c.id, c.name
            ORDER BY order_count DESC, c.name
            """
        ).fetchall()

    return render_template(
        "report.html",
        total_orders=total_orders,
        total_sales_paise=int(total_sales_paise or 0),
        books_sold=int(books_sold or 0),
        top_books=top_books,
        category_orders=category_orders,
    )


# ============================================================
# CSV EXPORT
# ============================================================

@admin_bp.route("/admin/export")
@admin_required
def admin_export():
    db = get_db()
    require_table(db, "orders")

    order_columns = table_columns(db, "orders")
    wanted_columns = [
        "id",
        "customer_name",
        "email",
        "phone",
        "address_snapshot",
        "subtotal_paise",
        "discount_paise",
        "shipping_paise",
        "tax_paise",
        "total_paise",
        "coupon_code",
        "status",
        "created_at",
    ]

    available = [column for column in wanted_columns if column in order_columns]
    orders = db.execute(
        f"SELECT {', '.join(available)} FROM orders ORDER BY id DESC"
    ).fetchall()

    output = io.StringIO(newline="")
    writer = csv.writer(output)

    writer.writerow([
        "Order ID", "Customer Name", "Email", "Phone", "Address",
        "Subtotal", "Discount", "Shipping", "Tax", "Total", "Coupon", "Status", "Created At",
    ])

    for order in orders:
        writer.writerow([
            order["id"],
            order["customer_name"] if "customer_name" in available else "",
            order["email"] if "email" in available else "",
            order["phone"] if "phone" in available else "",
            order["address_snapshot"] if "address_snapshot" in available else "",
            money_text(order["subtotal_paise"]) if "subtotal_paise" in available else "0.00",
            money_text(order["discount_paise"]) if "discount_paise" in available else "0.00",
            money_text(order["shipping_paise"]) if "shipping_paise" in available else "0.00",
            money_text(order["tax_paise"]) if "tax_paise" in available else "0.00",
            money_text(order["total_paise"]) if "total_paise" in available else "0.00",
            order["coupon_code"] if "coupon_code" in available else "",
            order["status"] if "status" in available else "",
            order["created_at"] if "created_at" in available else "",
        ])

    response = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=orders.csv"
    return response
