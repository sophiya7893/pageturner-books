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

auth_bp = Blueprint(
    "auth",
    __name__,
)


# ============================================================
# TIME HELPERS
# ============================================================

def utc_now():
    """
    Return the current UTC datetime.
    """
    return datetime.now(timezone.utc)


def db_timestamp(value):
    """
    Convert datetime into the format used by SQLite.
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
    Never store the real password-reset token.

    The browser receives the real random token.
    The database stores only its SHA-256 hash.
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
    Store a login attempt.

    success:
        True  -> 1
        False -> 0
    """

    db.execute(
        """
        INSERT INTO login_attempts (
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
    Step 32:

    After a successful login, remove previous
    login attempts for that email.
    """

    db.execute(
        """
        DELETE FROM login_attempts
        WHERE LOWER(email) = LOWER(?)
        """,
        (email,),
    )


def login_blocked(
    db,
    email,
):
    """
    Step 32:

    If an email has five or more failed attempts
    during the previous ten minutes, login is
    temporarily blocked.

    Even the correct password is refused while
    blocked.
    """

    cutoff = db_timestamp(
        utc_now()
        - timedelta(minutes=10)
    )

    result = db.execute(
        """
        SELECT COUNT(*) AS total
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

    failures = result["total"]

    return failures >= 5


# ============================================================
# LOGIN
# ============================================================

@auth_bp.route(
    "/login",
    methods=["GET", "POST"],
)
def login():

    # --------------------------------------------------------
    # DISPLAY LOGIN PAGE
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "login.html"
        )

    # --------------------------------------------------------
    # READ FORM DATA
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
    # BASIC VALIDATION
    # --------------------------------------------------------

    if not email or not password:

        flash(
            "Email and password are required.",
            "danger",
        )

        return render_template(
            "login.html"
        ), 400

    db = get_db()

    # --------------------------------------------------------
    # STEP 32
    # CHECK LOGIN LOCKOUT FIRST
    # --------------------------------------------------------

    if login_blocked(
        db,
        email,
    ):

        flash(
            "Too many failed login attempts. "
            "Please try again later.",
            "danger",
        )

        return render_template(
            "login.html"
        ), 429

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
        """,
        (email,),
    ).fetchone()

    # --------------------------------------------------------
    # CHECK PASSWORD HASH
    # --------------------------------------------------------

    password_ok = False

    if user:

        stored_hash = user[
            "password_hash"
        ]

        if stored_hash:

            try:

                password_ok = (
                    check_password_hash(
                        stored_hash,
                        password,
                    )
                )

            except (ValueError, TypeError):

                password_ok = False

    # --------------------------------------------------------
    # FAILED LOGIN
    # --------------------------------------------------------

    if not password_ok:

        record_login_attempt(
            db,
            email,
            False,
        )

        db.commit()

        flash(
            "Invalid email or password.",
            "danger",
        )

        return render_template(
            "login.html"
        ), 401

    # --------------------------------------------------------
    # SUCCESSFUL LOGIN
    #
    # Step 32:
    # successful login clears failed attempts.
    # --------------------------------------------------------

    clear_login_attempts(
        db,
        email,
    )

    db.commit()

    # --------------------------------------------------------
    # CREATE NEW AUTHENTICATED SESSION
    # --------------------------------------------------------

    session.clear()

    session["user_id"] = user[
        "id"
    ]

    session["user_name"] = user[
        "name"
    ]

    session["user_email"] = user[
        "email"
    ]

    session["user_role"] = user[
        "role"
    ]

    # --------------------------------------------------------
    # STEP 33
    # CREATE FRESH CSRF TOKEN
    # --------------------------------------------------------

    session["_csrf_token"] = (
        secrets.token_urlsafe(32)
    )

    flash(
        "Login successful.",
        "success",
    )

    # --------------------------------------------------------
    # HANDLE ?next=
    #
    # Only local paths are accepted.
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

    # --------------------------------------------------------
    # ROLE-BASED REDIRECT
    # --------------------------------------------------------

    if user["role"] == "admin":

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    if user["role"] == "staff":

        return redirect(
            url_for(
                "admin.admin_orders"
            )
        )

    # --------------------------------------------------------
    # CUSTOMER REDIRECT
    # --------------------------------------------------------

    return redirect(
        url_for(
            "shop.home"
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

    # Remove authentication and CSRF information.
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
    # DISPLAY FORM
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
        """,
        (email,),
    ).fetchone()

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Do not reveal whether the email exists.
    # --------------------------------------------------------

    if user:

        # ----------------------------------------------------
        # STEP 31
        # GENERATE SECURE RANDOM TOKEN
        # ----------------------------------------------------

        raw_token = (
            secrets.token_urlsafe(32)
        )

        # Store only SHA-256 digest.
        digest = token_digest(
            raw_token
        )

        # Token expires after 15 minutes.
        expires_at = db_timestamp(
            utc_now()
            + timedelta(minutes=15)
        )

        try:

            db.execute(
                "BEGIN IMMEDIATE"
            )

            # ------------------------------------------------
            # INVALIDATE OLD UNUSED TOKENS
            # ------------------------------------------------

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

            # ------------------------------------------------
            # STORE NEW HASHED TOKEN
            # ------------------------------------------------

            db.execute(
                """
                INSERT INTO reset_tokens (
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
        # ASSIGNMENT:
        #
        # No email server required.
        # Print reset link to terminal.
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
    # SAME MESSAGE WHETHER USER EXISTS OR NOT
    # --------------------------------------------------------

    flash(
        "If an account exists for that email, "
        "a password reset link has been generated. "
        "Check the Flask terminal.",
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
def reset_password(
    token,
):

    # --------------------------------------------------------
    # HASH TOKEN RECEIVED FROM URL
    # --------------------------------------------------------

    digest = token_digest(
        token
    )

    now = db_timestamp(
        utc_now()
    )

    db = get_db()

    # --------------------------------------------------------
    # FIND TOKEN
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
        """,
        (
            digest,
        ),
    ).fetchone()

    # --------------------------------------------------------
    # MADE-UP / INVALID TOKEN
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
    # ALREADY USED TOKEN
    # --------------------------------------------------------

    if reset_record[
        "used"
    ]:

        flash(
            "This password reset link has already been used.",
            "danger",
        )

        return redirect(
            url_for(
                "auth.forgot_password"
            )
        )

    # --------------------------------------------------------
    # EXPIRED TOKEN
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
    # DISPLAY PASSWORD RESET FORM
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
    # SERVER-SIDE PASSWORD VALIDATION
    # --------------------------------------------------------

    if len(password) < 8:

        flash(
            "Password must contain at least "
            "8 characters.",
            "danger",
        )

        return render_template(
            "reset_password.html",
            token=token,
        ), 400

    if password != confirm_password:

        flash(
            "Passwords do not match.",
            "danger",
        )

        return render_template(
            "reset_password.html",
            token=token,
        ), 400

    # --------------------------------------------------------
    # STEP 31
    #
    # TOKEN CONSUMPTION + PASSWORD UPDATE
    # ARE ONE TRANSACTION.
    # --------------------------------------------------------

    try:

        db.execute(
            "BEGIN IMMEDIATE"
        )

        # ----------------------------------------------------
        # RE-CHECK AND CONSUME TOKEN
        # ----------------------------------------------------

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

        if result.rowcount != 1:

            db.rollback()

            flash(
                "This password reset link is "
                "invalid, expired, or already used.",
                "danger",
            )

            return redirect(
                url_for(
                    "auth.forgot_password"
                )
            )

        # ----------------------------------------------------
        # STORE HASHED PASSWORD
        # ----------------------------------------------------

        new_password_hash = (
            generate_password_hash(
                password
            )
        )

        db.execute(
            """
            UPDATE users

            SET password_hash = ?

            WHERE id = ?
            """,
            (
                new_password_hash,
                reset_record[
                    "user_id"
                ],
            ),
        )

        # ----------------------------------------------------
        # CLEAR LOGIN LOCKOUT
        # ----------------------------------------------------

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
                reset_record[
                    "user_id"
                ],
            ),
        )

        db.commit()

    except Exception:

        db.rollback()
        raise

    # --------------------------------------------------------
    # REMOVE EXISTING LOGIN SESSION
    # --------------------------------------------------------

    session.clear()

    flash(
        "Your password has been reset. "
        "Please log in with your new password.",
        "success",
    )

    return redirect(
        url_for(
            "auth.login"
        )
    )