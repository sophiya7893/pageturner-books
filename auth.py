
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from db import get_db


# ============================================================
# AUTH BLUEPRINT
# ============================================================

auth_bp = Blueprint("auth", __name__)


# ============================================================
# TIME HELPERS
# ============================================================

def utc_now():
    return datetime.now(timezone.utc)


def db_timestamp(value):
    return value.astimezone(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ============================================================
# PASSWORD RESET TOKEN HELPER
# ============================================================

def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ============================================================
# LOGIN ATTEMPT HELPERS
# ============================================================

def record_login_attempt(db, email, success):
    db.execute(
        """
        INSERT INTO login_attempts (email, success)
        VALUES (?, ?)
        """,
        (email.lower(), int(success)),
    )


def clear_login_attempts(db, email):
    db.execute(
        """
        DELETE FROM login_attempts
        WHERE LOWER(email) = LOWER(?)
        """,
        (email,),
    )


def login_blocked(db, email):
    cutoff = db_timestamp(
        utc_now() - timedelta(minutes=10)
    )

    result = db.execute(
        """
        SELECT COUNT(*) AS total
        FROM login_attempts
        WHERE LOWER(email) = LOWER(?)
          AND success = 0
          AND attempted_at >= ?
        """,
        (email, cutoff),
    ).fetchone()

    return result["total"] >= 5


# ============================================================
# SHARED LOGIN HELPER
# ============================================================

def authenticate_account(email, password, allowed_roles):
    """
    Validate credentials and account role.
    Return the user row on success, otherwise None.
    """

    db = get_db()

    if login_blocked(db, email):
        return None, "blocked"

    user = db.execute(
        """
        SELECT id, name, email, password_hash, role
        FROM users
        WHERE LOWER(email) = LOWER(?)
        """,
        (email,),
    ).fetchone()

    password_ok = False

    if user and user["password_hash"]:
        try:
            password_ok = check_password_hash(
                user["password_hash"], password
            )
        except (ValueError, TypeError):
            password_ok = False

    if not password_ok or user["role"] not in allowed_roles:
        record_login_attempt(db, email, False)
        db.commit()
        return None, "invalid"

    clear_login_attempts(db, email)
    db.commit()

    return user, None


def create_login_session(user):
    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    session["user_role"] = user["role"]
    session["_csrf_token"] = secrets.token_urlsafe(32)


# ============================================================
# USER LOGIN
# ============================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Please enter your email and password.", "danger")
        return render_template("login.html"), 400

    user, error = authenticate_account(
        email, password, {"customer", "user"}
    )

    if error == "blocked":
        flash(
            "Too many failed login attempts. Please try again later.",
            "danger",
        )
        return render_template("403.html"), 429

    if error == "invalid":
        flash("Invalid user email or password.", "danger")
        return render_template("403.html"), 403

    create_login_session(user)

    flash("Login successful.", "success")

    next_url = request.args.get("next", "")

    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)

    return redirect(url_for("shop.home"))


# ============================================================
# ADMIN LOGIN
# ============================================================

@auth_bp.route(
    "/admin/login",
    methods=["POST"],
    endpoint="admin_login_submit",
)
def admin_login_submit():

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        flash(
            "Please enter your admin email and password.",
            "danger",
        )
        return render_template("403.html"), 403

    user, error = authenticate_account(
        email, password, {"admin"}
    )

    if error == "blocked":
        flash(
            "Too many failed login attempts. Please try again later.",
            "danger",
        )
        return render_template("403.html"), 429

    if error == "invalid":
        flash("Invalid admin email or password.", "danger")
        return render_template("403.html"), 403

    create_login_session(user)

    flash("Admin login successful.", "success")

    return redirect(url_for("admin.admin_dashboard"))


# ============================================================
# LOGOUT
# ============================================================

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("shop.home"))


# ============================================================
# FORGOT PASSWORD
# ============================================================

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()

    if not email:
        flash("Please enter your email.", "danger")
        return render_template("forgot_password.html"), 400

    db = get_db()

    user = db.execute(
        """
        SELECT id, email
        FROM users
        WHERE LOWER(email) = LOWER(?)
        """,
        (email,),
    ).fetchone()

    # Use the same message whether the account exists or not.
    if user:
        raw_token = secrets.token_urlsafe(32)
        digest = token_digest(raw_token)

        expires_at = db_timestamp(
            utc_now() + timedelta(minutes=15)
        )

        try:
            db.execute("BEGIN IMMEDIATE")

            db.execute(
                """
                UPDATE reset_tokens
                SET used = 1
                WHERE user_id = ? AND used = 0
                """,
                (user["id"],),
            )

            db.execute(
                """
                INSERT INTO reset_tokens (
                    user_id, token_hash, expires_at, used
                )
                VALUES (?, ?, ?, 0)
                """,
                (user["id"], digest, expires_at),
            )

            db.commit()

        except Exception:
            db.rollback()
            raise

        reset_url = url_for(
            "auth.reset_password",
            token=raw_token,
            _external=True,
        )

        # Development only: reset link appears in the terminal.
        current_app.logger.warning(
            "Password reset link for %s: %s",
            email,
            reset_url,
        )

    flash(
        "If an account exists for that email, a reset link "
        "has been generated. Check the Flask terminal.",
        "info",
    )

    return redirect(url_for("auth.forgot_password"))


# ============================================================
# RESET PASSWORD
# ============================================================

@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    digest = token_digest(token)
    now = db_timestamp(utc_now())
    db = get_db()

    reset_record = db.execute(
        """
        SELECT id, user_id, expires_at, used
        FROM reset_tokens
        WHERE token_hash = ?
        """,
        (digest,),
    ).fetchone()

    if reset_record is None:
        flash("This password reset link is invalid.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if reset_record["used"]:
        flash(
            "This password reset link has already been used.",
            "danger",
        )
        return redirect(url_for("auth.forgot_password"))

    if reset_record["expires_at"] <= now:
        flash("This password reset link has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "GET":
        return render_template(
            "reset_password.html",
            token=token,
        )

    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if len(password) < 8:
        flash("Password must contain at least 8 characters.", "danger")
        return render_template(
            "reset_password.html", token=token
        ), 400

    if password != confirm_password:
        flash("Passwords do not match.", "danger")
        return render_template(
            "reset_password.html", token=token
        ), 400

    try:
        db.execute("BEGIN IMMEDIATE")

        result = db.execute(
            """
            UPDATE reset_tokens
            SET used = 1
            WHERE id = ?
              AND used = 0
              AND expires_at > ?
            """,
            (reset_record["id"], now),
        )

        if result.rowcount != 1:
            db.rollback()
            flash(
                "This password reset link is invalid, expired, "
                "or already used.",
                "danger",
            )
            return redirect(url_for("auth.forgot_password"))

        new_password_hash = generate_password_hash(password)

        db.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
            """,
            (new_password_hash, reset_record["user_id"]),
        )

        db.execute(
            """
            DELETE FROM login_attempts
            WHERE LOWER(email) = LOWER(
                (SELECT email FROM users WHERE id = ?)
            )
            """,
            (reset_record["user_id"],),
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    session.clear()

    flash(
        "Your password has been reset. Please log in with your new password.",
        "success",
    )

    return redirect(url_for("auth.login"))
