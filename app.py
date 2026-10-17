import os

from flask import (
    Flask,
    session,
    render_template,
)

import db

from admin import admin_bp
from auth import auth_bp
from shop import shop_bp, money
from api import api_bp
from extras import extras_bp, install_extras
from security import (
    current_user,
    install_csrf_protection,
)


# ============================================================
# BASE DIRECTORY
# ============================================================

BASE_DIR = os.path.abspath(
    os.path.dirname(__file__)
)


# ============================================================
# CREATE FLASK APPLICATION
# ============================================================

app = Flask(
    __name__
)

# One money formatter shared by every Jinja template.
app.jinja_env.filters["money"] = money


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

app.config.from_mapping(

    # --------------------------------------------------------
    # SESSION / SECURITY
    # --------------------------------------------------------

    SECRET_KEY=os.environ.get(
        "SECRET_KEY",
        "pageturner-development-secret-key"
    ),

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    DATABASE=os.environ.get(
        "PAGETURNER_DATABASE",
        os.path.join(BASE_DIR, "pageturner.db"),
    ),

    # --------------------------------------------------------
    # FILE UPLOAD LIMIT
    # 5 MB
    # --------------------------------------------------------

    MAX_CONTENT_LENGTH=(
        5
        * 1024
        * 1024
    ),
)


# ============================================================
# SESSION COOKIE SETTINGS
# ============================================================

app.config.update(

    SESSION_COOKIE_HTTPONLY=True,

    SESSION_COOKIE_SAMESITE="Lax",

    # Keep False while developing on:
    # http://127.0.0.1:5000
    #
    # Change to True only when using HTTPS.
    SESSION_COOKIE_SECURE=False,
)


# ============================================================
# DATABASE
# ============================================================

db.init_app(
    app
)


# ============================================================
# CSRF PROTECTION
# ============================================================

install_csrf_protection(
    app
)


# ============================================================
# REGISTER BLUEPRINTS
# ============================================================

app.register_blueprint(
    auth_bp
)

app.register_blueprint(
    shop_bp
)

app.register_blueprint(
    admin_bp
)
app.register_blueprint(api_bp)
app.register_blueprint(extras_bp)
install_extras(app)


# ============================================================
# TEMPLATE CONTEXT
# ============================================================

@app.context_processor
def inject_global_template_values():
    """
    Values automatically available in every Jinja template.

    Templates can use:

        current_user
        cart_count
    """

    user = current_user()

    cart_count = 0
    notification_count = 0

    user_id = session.get(
        "user_id"
    )

    # --------------------------------------------------------
    # LOGGED-IN CUSTOMER CART
    # --------------------------------------------------------

    if user_id:

        try:

            database = db.get_db()

            row = database.execute(
                """
                SELECT
                    COALESCE(
                        SUM(quantity),
                        0
                    ) AS total

                FROM cart_items

                WHERE user_id = ?
                """,
                (
                    user_id,
                )
            ).fetchone()

            if row is not None:

                cart_count = int(
                    row["total"]
                    or 0
                )

        except Exception:

            # Do not prevent the whole website from loading
            # if cart_items has not been created yet.
            cart_count = 0

    # --------------------------------------------------------
    # GUEST SESSION CART
    # --------------------------------------------------------

    else:

        cart = session.get(
            "cart",
            {}
        )

        if isinstance(
            cart,
            dict
        ):

            for quantity in cart.values():

                try:

                    quantity = int(
                        quantity
                    )

                except (
                    ValueError,
                    TypeError
                ):

                    continue

                if quantity > 0:

                    cart_count += (
                        quantity
                    )

    if user_id:
        try:
            row = db.get_db().execute(
                "SELECT COUNT(*) AS total FROM notifications WHERE user_id = ? AND is_read = 0",
                (user_id,),
            ).fetchone()
            notification_count = int(row["total"] or 0) if row else 0
        except Exception:
            notification_count = 0

    return {
        "current_user": user,
        "cart_count": cart_count,
        "notification_count": notification_count,
    }


# ============================================================
# 413 - FILE TOO LARGE
# ============================================================

@app.errorhandler(413)
def file_too_large(error):
    return render_template(
        "error.html",
        code=413,
        heading="File Too Large",
        message="The uploaded file is too large. Please choose a smaller file and try again.",
    ), 413


# ============================================================
# 404
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template("404.html"), 404


# ============================================================
# 403
# ============================================================

@app.errorhandler(403)
def forbidden(error):

    return render_template("403.html"), 403


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )

@app.errorhandler(500)
def internal_server_error(error):
    return render_template("500.html"), 500
