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
from security import login_required


# ============================================================
# AUTH BLUEPRINT
# ============================================================

auth_bp = Blueprint(
    "auth",
    __name__,
)


# ============================================================
# TIME HELPERS
# ============================================================

def utc_now():
    """
    Return the current UTC time.
    """

    return datetime.now(
        timezone.utc
    )


def db_timestamp(value):
    """
    Convert a datetime value into the timestamp format
    stored in SQLite.
    """

    return value.astimezone(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ============================================================
# PASSWORD RESET TOKEN HELPER
# ============================================================

def token_digest(token):
    """
    Hash password-reset tokens before storing them.

    The raw token is never stored in the database.
    """

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


# ============================================================
# LOGIN ATTEMPT HELPERS
# ============================================================

def record_login_attempt(
    db,
    email,
    success,
):
    """
    Record a successful or failed login attempt.
    """

    db.execute(
        """
        INSERT INTO login_attempts
        (
            email,
            success
        )
        VALUES (?, ?)
        """,
        (
            email.lower(),
            int(success),
        ),
    )


def clear_login_attempts(
    db,
    email,
):
    """
    Remove old login attempts after successful login.
    """

    db.execute(
        """
        DELETE FROM login_attempts
        WHERE LOWER(email) = LOWER(?)
        """,
        (
            email,
        ),
    )


def login_blocked(
    db,
    email,
):
    """
    Block login when there have been at least five
    failed attempts during the previous ten minutes.
    """

    cutoff = db_timestamp(
        utc_now()
        - timedelta(minutes=10)
    )

    result = db.execute(
        """
        SELECT
            COUNT(*) AS total

        FROM login_attempts

        WHERE LOWER(email) = LOWER(?)
          AND success = 0
          AND attempted_at >= ?
        """,
        (
            email,
            cutoff,
        ),
    ).fetchone()

    if result is None:
        return False

    return int(
        result["total"] or 0
    ) >= 5


# ============================================================
# SHARED LOGIN HELPER
# ============================================================

def authenticate_account(
    email,
    password,
    allowed_roles,
):
    """
    Validate email, password and account role.

    Returns:

        (user, None)

    on success.

    Otherwise:

        (None, "blocked")

    or:

        (None, "invalid")
    """

    db = get_db()

    # --------------------------------------------------------
    # CHECK LOGIN RATE LIMIT
    # --------------------------------------------------------

    if login_blocked(
        db,
        email,
    ):

        return (
            None,
            "blocked",
        )

    # --------------------------------------------------------
    # FIND USER
    # --------------------------------------------------------

    user = db.execute(
        """
        SELECT
            id,
            name,
            email,
            password_hash,
            role

        FROM users

        WHERE LOWER(email) = LOWER(?)

        LIMIT 1
        """,
        (
            email,
        ),
    ).fetchone()

    # --------------------------------------------------------
    # CHECK PASSWORD
    # --------------------------------------------------------

    password_ok = False

    if (
        user is not None
        and user["password_hash"]
    ):

        try:

            password_ok = (
                check_password_hash(
                    user["password_hash"],
                    password,
                )
            )

        except (
            ValueError,
            TypeError,
        ):

            password_ok = False

    # --------------------------------------------------------
    # CHECK ROLE
    # --------------------------------------------------------

    role_ok = (
        user is not None
        and user["role"]
        in allowed_roles
    )

    # --------------------------------------------------------
    # LOGIN FAILED
    # --------------------------------------------------------

    if (
        not password_ok
        or not role_ok
    ):

        record_login_attempt(
            db,
            email,
            False,
        )

        db.commit()

        return (
            None,
            "invalid",
        )

    # --------------------------------------------------------
    # LOGIN SUCCESSFUL
    # --------------------------------------------------------

    clear_login_attempts(
        db,
        email,
    )

    db.commit()

    return (
        user,
        None,
    )


# ============================================================
# CREATE LOGIN SESSION
# ============================================================

def create_login_session(user):
    """
    Create a clean authenticated session.
    """

    session.clear()

    session["user_id"] = (
        user["id"]
    )

    session["user_name"] = (
        user["name"]
    )

    session["user_email"] = (
        user["email"]
    )

    session["user_role"] = (
        user["role"]
    )

    # Create a fresh CSRF token after login.
    session["_csrf_token"] = (
        secrets.token_urlsafe(32)
    )


# ============================================================
# USER LOGIN
# ============================================================

@auth_bp.route(
    "/login",
    methods=["GET", "POST"],
)
def login():

    # --------------------------------------------------------
    # SHOW LOGIN PAGE
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "login.html"
        )

    # --------------------------------------------------------
    # READ FORM
    # --------------------------------------------------------

    email = request.form.get(
        "email",
        "",
    ).strip().lower()

    password = request.form.get(
        "password",
        "",
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if (
        not email
        or not password
    ):

        flash(
            "Please enter your email and password.",
            "danger",
        )

        return render_template(
            "login.html"
        ), 400

    # --------------------------------------------------------
    # AUTHENTICATE CUSTOMER
    # --------------------------------------------------------

    user, error = authenticate_account(
        email,
        password,
        {
            "customer",
            "user",
        },
    )

    # --------------------------------------------------------
    # TOO MANY FAILED ATTEMPTS
    # --------------------------------------------------------

    if error == "blocked":

        flash(
            (
                "Too many failed login attempts. "
                "Please try again later."
            ),
            "danger",
        )

        return render_template(
            "403.html"
        ), 429

    # --------------------------------------------------------
    # INVALID LOGIN
    # --------------------------------------------------------

    if error == "invalid":

        flash(
            "Invalid user email or password.",
            "danger",
        )

        return render_template(
            "403.html"
        ), 403

    # --------------------------------------------------------
    # LOGIN SUCCESS
    # --------------------------------------------------------

    # Preserve a guest cart before create_login_session clears the
    # anonymous session. Merge it into the database cart after login.
    guest_cart = session.get("cart", {})
    if not isinstance(guest_cart, dict):
        guest_cart = {}

    create_login_session(user)

    if guest_cart:
        session["cart"] = guest_cart
        session.modified = True
        # Import lazily to avoid an auth <-> shop import cycle.
        from shop import merge_guest_cart
        merge_guest_cart(user["id"])

    flash(
        "Login successful.",
        "success",
    )

    # --------------------------------------------------------
    # OPTIONAL REDIRECT BACK TO REQUESTED PAGE
    # --------------------------------------------------------

    next_url = request.args.get(
        "next",
        "",
    )

    if (
        next_url.startswith("/")
        and not next_url.startswith("//")
    ):

        return redirect(
            next_url
        )

    return redirect(
        url_for(
            "shop.home"
        )
    )


# ============================================================
# ADMIN LOGIN SUBMISSION
# ============================================================

@auth_bp.route(
    "/admin/login",
    methods=["POST"],
    endpoint="admin_login_submit",
)
def admin_login_submit():

    # --------------------------------------------------------
    # READ FORM
    # --------------------------------------------------------

    email = request.form.get(
        "email",
        "",
    ).strip().lower()

    password = request.form.get(
        "password",
        "",
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if (
        not email
        or not password
    ):

        flash(
            (
                "Please enter your admin "
                "email and password."
            ),
            "danger",
        )

        return render_template(
            "403.html"
        ), 403

    # --------------------------------------------------------
    # AUTHENTICATE ADMIN
    # --------------------------------------------------------

    user, error = authenticate_account(
        email,
        password,
        {
            "admin",
        },
    )

    if error == "blocked":

        flash(
            (
                "Too many failed login attempts. "
                "Please try again later."
            ),
            "danger",
        )

        return render_template(
            "403.html"
        ), 429

    if error == "invalid":

        flash(
            "Invalid admin email or password.",
            "danger",
        )

        return render_template(
            "403.html"
        ), 403

    # --------------------------------------------------------
    # LOGIN SUCCESS
    # --------------------------------------------------------

    create_login_session(
        user
    )

    flash(
        "Admin login successful.",
        "success",
    )

    return redirect(
        url_for(
            "admin.admin_dashboard"
        )
    )


# ============================================================
# LOGOUT
# ============================================================

@auth_bp.route(
    "/logout",
    methods=["POST"],
)
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success",
    )

    return redirect(
        url_for(
            "shop.home"
        )
    )


# ============================================================
# FORGOT PASSWORD
# ============================================================

@auth_bp.route(
    "/forgot-password",
    methods=["GET", "POST"],
)
def forgot_password():

    # --------------------------------------------------------
    # SHOW FORM
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "forgot_password.html"
        )

    # --------------------------------------------------------
    # READ EMAIL
    # --------------------------------------------------------

    email = request.form.get(
        "email",
        "",
    ).strip().lower()

    if not email:

        flash(
            "Please enter your email.",
            "danger",
        )

        return render_template(
            "forgot_password.html"
        ), 400

    db = get_db()

    # --------------------------------------------------------
    # FIND USER
    # --------------------------------------------------------

    user = db.execute(
        """
        SELECT
            id,
            email

        FROM users

        WHERE LOWER(email) = LOWER(?)

        LIMIT 1
        """,
        (
            email,
        ),
    ).fetchone()

    # --------------------------------------------------------
    # CREATE RESET TOKEN
    #
    # We deliberately show the same final message whether
    # or not the email exists. This prevents account
    # enumeration.
    # --------------------------------------------------------

    if user is not None:

        raw_token = (
            secrets.token_urlsafe(32)
        )

        digest = token_digest(
            raw_token
        )

        expires_at = db_timestamp(
            utc_now()
            + timedelta(minutes=15)
        )

        try:

            db.execute(
                "BEGIN IMMEDIATE"
            )

            # Invalidate any older unused reset links.
            db.execute(
                """
                UPDATE reset_tokens

                SET used = 1

                WHERE user_id = ?
                  AND used = 0
                """,
                (
                    user["id"],
                ),
            )

            # Store only the SHA-256 digest.
            db.execute(
                """
                INSERT INTO reset_tokens
                (
                    user_id,
                    token_hash,
                    expires_at,
                    used
                )

                VALUES (?, ?, ?, 0)
                """,
                (
                    user["id"],
                    digest,
                    expires_at,
                ),
            )

            db.commit()

        except Exception:

            db.rollback()
            raise

        # ----------------------------------------------------
        # DEVELOPMENT RESET LINK
        #
        # For this project the reset URL is printed in
        # the Flask terminal instead of sending real email.
        # ----------------------------------------------------

        reset_url = url_for(
            "auth.reset_password",
            token=raw_token,
            _external=True,
        )

        current_app.logger.warning(
            "Password reset link for %s: %s",
            email,
            reset_url,
        )

    # --------------------------------------------------------
    # GENERIC RESPONSE
    # --------------------------------------------------------

    flash(
        (
            "If an account exists for that email, "
            "a reset link has been generated. "
            "Check the Flask terminal."
        ),
        "info",
    )

    return redirect(
        url_for(
            "auth.forgot_password"
        )
    )


# ============================================================
# RESET PASSWORD
# ============================================================

@auth_bp.route(
    "/reset-password/<token>",
    methods=["GET", "POST"],
)
def reset_password(token):

    digest = token_digest(
        token
    )

    now = db_timestamp(
        utc_now()
    )

    db = get_db()

    # --------------------------------------------------------
    # FIND RESET TOKEN
    # --------------------------------------------------------

    reset_record = db.execute(
        """
        SELECT
            id,
            user_id,
            expires_at,
            used

        FROM reset_tokens

        WHERE token_hash = ?

        LIMIT 1
        """,
        (
            digest,
        ),
    ).fetchone()

    # --------------------------------------------------------
    # INVALID TOKEN
    # --------------------------------------------------------

    if reset_record is None:

        flash(
            "This password reset link is invalid.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.forgot_password"
            )
        )

    # --------------------------------------------------------
    # TOKEN ALREADY USED
    # --------------------------------------------------------

    if reset_record["used"]:

        flash(
            (
                "This password reset link "
                "has already been used."
            ),
            "danger",
        )

        return redirect(
            url_for(
                "auth.forgot_password"
            )
        )

    # --------------------------------------------------------
    # TOKEN EXPIRED
    # --------------------------------------------------------

    if (
        reset_record["expires_at"]
        <= now
    ):

        flash(
            "This password reset link has expired.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.forgot_password"
            )
        )

    # --------------------------------------------------------
    # SHOW RESET FORM
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "reset_password.html",
            token=token,
        )

    # --------------------------------------------------------
    # READ NEW PASSWORD
    # --------------------------------------------------------

    password = request.form.get(
        "password",
        "",
    )

    confirm_password = request.form.get(
        "confirm_password",
        "",
    )

    # --------------------------------------------------------
    # PASSWORD LENGTH
    # --------------------------------------------------------

    if len(password) < 8:

        flash(
            (
                "Password must contain "
                "at least 8 characters."
            ),
            "danger",
        )

        return render_template(
            "reset_password.html",
            token=token,
        ), 400

    # --------------------------------------------------------
    # PASSWORDS MUST MATCH
    # --------------------------------------------------------

    if (
        password
        != confirm_password
    ):

        flash(
            "Passwords do not match.",
            "danger",
        )

        return render_template(
            "reset_password.html",
            token=token,
        ), 400

    # --------------------------------------------------------
    # UPDATE PASSWORD
    # --------------------------------------------------------

    try:

        db.execute(
            "BEGIN IMMEDIATE"
        )

        # Mark the token used only if it is still valid.
        result = db.execute(
            """
            UPDATE reset_tokens

            SET used = 1

            WHERE id = ?
              AND used = 0
              AND expires_at > ?
            """,
            (
                reset_record["id"],
                now,
            ),
        )

        # Another request may have used the token first.
        if result.rowcount != 1:

            db.rollback()

            flash(
                (
                    "This password reset link is "
                    "invalid, expired, or already used."
                ),
                "danger",
            )

            return redirect(
                url_for(
                    "auth.forgot_password"
                )
            )

        # Hash new password.
        new_password_hash = (
            generate_password_hash(
                password
            )
        )

        # Save new password.
        db.execute(
            """
            UPDATE users

            SET password_hash = ?

            WHERE id = ?
            """,
            (
                new_password_hash,
                reset_record["user_id"],
            ),
        )

        # Clear failed login attempts for this user.
        db.execute(
            """
            DELETE FROM login_attempts

            WHERE LOWER(email) = LOWER(
                (
                    SELECT email
                    FROM users
                    WHERE id = ?
                )
            )
            """,
            (
                reset_record["user_id"],
            ),
        )

        db.commit()

    except Exception:

        db.rollback()
        raise

    # --------------------------------------------------------
    # REQUIRE LOGIN WITH NEW PASSWORD
    # --------------------------------------------------------

    session.clear()

    flash(
        (
            "Your password has been reset. "
            "Please log in with your new password."
        ),
        "success",
    )

    return redirect(
        url_for(
            "auth.login"
        )
    )


# ============================================================
# CHANGE PASSWORD
# ============================================================

@auth_bp.route(
    "/change-password",
    methods=["GET", "POST"],
)
@login_required
def change_password():

    user_id = session.get(
        "user_id"
    )

    db = get_db()

    # --------------------------------------------------------
    # FIND CURRENT USER
    # --------------------------------------------------------

    user = db.execute(
        """
        SELECT
            id,
            name,
            email,
            password_hash

        FROM users

        WHERE id = ?

        LIMIT 1
        """,
        (
            user_id,
        ),
    ).fetchone()

    if user is None:

        session.clear()

        flash(
            (
                "Your account could not be found. "
                "Please log in again."
            ),
            "danger",
        )

        return redirect(
            url_for(
                "auth.login"
            )
        )

    # --------------------------------------------------------
    # SHOW CHANGE PASSWORD FORM
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "change_password.html"
        )

    # --------------------------------------------------------
    # READ FORM
    # --------------------------------------------------------

    current_password = request.form.get(
        "current_password",
        "",
    )

    new_password = request.form.get(
        "new_password",
        "",
    )

    confirm_password = request.form.get(
        "confirm_password",
        "",
    )

    # --------------------------------------------------------
    # ALL FIELDS REQUIRED
    # --------------------------------------------------------

    if (
        not current_password
        or not new_password
        or not confirm_password
    ):

        flash(
            "Please complete every password field.",
            "danger",
        )

        return render_template(
            "change_password.html"
        ), 400

    # --------------------------------------------------------
    # VERIFY CURRENT PASSWORD
    # --------------------------------------------------------

    current_password_correct = False

    if user["password_hash"]:

        try:

            current_password_correct = (
                check_password_hash(
                    user["password_hash"],
                    current_password,
                )
            )

        except (
            ValueError,
            TypeError,
        ):

            current_password_correct = False

    if not current_password_correct:

        flash(
            "Current password is incorrect.",
            "danger",
        )

        return render_template(
            "change_password.html"
        ), 400

    # --------------------------------------------------------
    # NEW PASSWORD LENGTH
    # --------------------------------------------------------

    if len(new_password) < 8:

        flash(
            (
                "New password must be "
                "at least 8 characters."
            ),
            "danger",
        )

        return render_template(
            "change_password.html"
        ), 400

    # --------------------------------------------------------
    # PASSWORDS MUST MATCH
    # --------------------------------------------------------

    if (
        new_password
        != confirm_password
    ):

        flash(
            (
                "New password and confirmation "
                "do not match."
            ),
            "danger",
        )

        return render_template(
            "change_password.html"
        ), 400

    # --------------------------------------------------------
    # NEW PASSWORD MUST BE DIFFERENT
    # --------------------------------------------------------

    try:

        same_password = (
            check_password_hash(
                user["password_hash"],
                new_password,
            )
        )

    except (
        ValueError,
        TypeError,
    ):

        same_password = False

    if same_password:

        flash(
            (
                "Your new password must be "
                "different from your current password."
            ),
            "danger",
        )

        return render_template(
            "change_password.html"
        ), 400

    # --------------------------------------------------------
    # HASH NEW PASSWORD
    # --------------------------------------------------------

    new_password_hash = (
        generate_password_hash(
            new_password
        )
    )

    # --------------------------------------------------------
    # UPDATE PASSWORD
    # --------------------------------------------------------

    try:

        db.execute(
            "BEGIN IMMEDIATE"
        )

        db.execute(
            """
            UPDATE users

            SET password_hash = ?

            WHERE id = ?
            """,
            (
                new_password_hash,
                user_id,
            ),
        )

        # Clear previous failed login attempts.
        db.execute(
            """
            DELETE FROM login_attempts

            WHERE LOWER(email) = LOWER(?)
            """,
            (
                user["email"],
            ),
        )

        db.commit()

    except Exception:

        db.rollback()
        raise

    flash(
        "Your password was changed successfully.",
        "success",
    )

    return redirect(
        url_for(
            "shop.profile"
        )
    )