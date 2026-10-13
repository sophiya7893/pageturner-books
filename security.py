
import hmac
import secrets
from functools import wraps

from flask import (
    abort,
    current_app,
    redirect,
    request,
    session,
    url_for,
)

from db import get_db


CSRF_SESSION_KEY = "_csrf_token"


# ============================================================
# CSRF PROTECTION
# ============================================================

def generate_csrf_token():
    """
    Create a random CSRF token for the current session.

    The same token is reused until the session is cleared.
    """

    token = session.get(CSRF_SESSION_KEY)

    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token

    return token


def get_submitted_csrf_token():
    """
    Read the token submitted by an HTML form or API request.

    HTML forms:
        <input type="hidden" name="csrf_token" ...>

    API requests:
        X-CSRF-Token: <token>
    """

    token = request.form.get("csrf_token", "")

    if not token:
        token = request.form.get("_csrf_token", "")

    if not token:
        token = request.headers.get("X-CSRF-Token", "")

    return token.strip()


def validate_csrf_token():
    """
    Reject POST requests when the token is missing or invalid.
    """

    expected = session.get(CSRF_SESSION_KEY)
    submitted = get_submitted_csrf_token()

    if not expected or not submitted:
        current_app.logger.warning(
            "CSRF validation failed: missing token; "
            "session token exists=%s, submitted token exists=%s",
            bool(expected),
            bool(submitted),
        )

        abort(
            400,
            description="Missing CSRF token. Refresh the page and try again.",
        )

    if not hmac.compare_digest(expected, submitted):
        current_app.logger.warning(
            "CSRF validation failed: token mismatch."
        )

        abort(
            400,
            description="Invalid CSRF token. Refresh the page and try again.",
        )


def install_csrf_protection(app):
    """
    Install global CSRF protection.

    Every POST request must provide a valid session token.
    """

    app.jinja_env.globals["csrf_token"] = generate_csrf_token

    @app.before_request
    def csrf_before_request():
        if request.method == "POST":
            validate_csrf_token()


# ============================================================
# CURRENT USER
# ============================================================

def current_user():
    """
    Return the logged-in user, or None if nobody is logged in.
    """

    user_id = session.get("user_id")

    if not user_id:
        return None

    db = get_db()

    return db.execute(
        """
        SELECT
            id,
            name,
            email,
            role
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()


# ============================================================
# LOGIN REQUIRED
# ============================================================

def login_required(view):
    """
    Require the user to be logged in.
    """

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = current_user()

        if user is None:
            return redirect(
                url_for(
                    "auth.login",
                    next=request.url,
                )
            )

        return view(*args, **kwargs)

    return wrapped_view


# ============================================================
# ROLE REQUIRED
# ============================================================

def role_required(*allowed_roles):
    """
    Restrict access to the specified roles.

    Example:
        @role_required("admin")

        @role_required("staff", "admin")
    """

    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = current_user()

            if user is None:
                return redirect(
                    url_for(
                        "auth.login",
                        next=request.url,
                    )
                )

            if user["role"] not in allowed_roles:
                abort(403)

            return view(*args, **kwargs)

        return wrapped_view

    return decorator


# ============================================================
# ADMIN ONLY
# ============================================================

def admin_required(view):
    return role_required("admin")(view)


# ============================================================
# STAFF OR ADMIN
# ============================================================

def staff_or_admin_required(view):
    return role_required("staff", "admin")(view)
