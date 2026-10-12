import hmac
import secrets
from functools import wraps

from flask import (
    abort,
    redirect,
    request,
    session,
    url_for,
)

from db import get_db


CSRF_SESSION_KEY = "_csrf_token"


# ============================================================
# CSRF PROTECTION - STEP 33
# ============================================================

def generate_csrf_token():
    """
    Create one random CSRF token for the user's session.

    The same token is reused during the session.
    """

    token = session.get(CSRF_SESSION_KEY)

    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token

    return token


def get_submitted_csrf_token():
    """
    HTML forms send the CSRF token using _csrf_token.

    JSON/API requests may send it using:
        X-CSRF-Token
    """

    token = request.form.get(
        "_csrf_token",
        ""
    )

    if token:
        return token

    return request.headers.get(
        "X-CSRF-Token",
        ""
    )


def validate_csrf_token():
    """
    Reject POST requests when the CSRF token
    is missing or incorrect.
    """

    expected = session.get(
        CSRF_SESSION_KEY
    )

    submitted = get_submitted_csrf_token()

    if not expected or not submitted:
        abort(
            400,
            description="Missing CSRF token."
        )

    if not hmac.compare_digest(
        expected,
        submitted
    ):
        abort(
            400,
            description="Invalid CSRF token."
        )


def install_csrf_protection(app):
    """
    Install CSRF protection globally.

    Every POST request must contain a valid token.
    """

    app.jinja_env.globals[
        "csrf_token"
    ] = generate_csrf_token

    @app.before_request
    def csrf_before_request():

        if request.method == "POST":
            validate_csrf_token()


# ============================================================
# CURRENT USER
# ============================================================

def current_user():
    """
    Return the currently logged-in user.

    Returns None when no user is logged in.
    """

    user_id = session.get(
        "user_id"
    )

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
        (user_id,)
    ).fetchone()


# ============================================================
# LOGIN REQUIRED
# ============================================================

def login_required(view):
    """
    Require a logged-in user.
    """

    @wraps(view)
    def wrapped_view(
        *args,
        **kwargs
    ):

        user = current_user()

        if user is None:
            return redirect(
                url_for(
                    "auth.login",
                    next=request.url
                )
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped_view


# ============================================================
# ROLE REQUIRED - STEP 30
# ============================================================

def role_required(*allowed_roles):
    """
    Require one of the supplied roles.

    Example:

        @role_required("admin")

    or:

        @role_required("staff", "admin")
    """

    def decorator(view):

        @wraps(view)
        def wrapped_view(
            *args,
            **kwargs
        ):

            user = current_user()

            if user is None:
                return redirect(
                    url_for(
                        "auth.login",
                        next=request.url
                    )
                )

            if user["role"] not in allowed_roles:
                abort(403)

            return view(
                *args,
                **kwargs
            )

        return wrapped_view

    return decorator


# ============================================================
# ADMIN ONLY
# ============================================================

def admin_required(view):
    return role_required(
        "admin"
    )(view)


# ============================================================
# STAFF OR ADMIN
# ============================================================

def staff_or_admin_required(view):
    return role_required(
        "staff",
        "admin"
    )(view)