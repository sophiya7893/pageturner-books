import os

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    session,
    url_for,
)

from config import Config
from db import init_app as init_db_app
from db import init_db
from security import (
    current_user,
    install_csrf_protection,
)

from auth import auth_bp
from shop import shop_bp
from admin import admin_bp
from api import api_bp


# ============================================================
# APPLICATION FACTORY - STEP 39
# ============================================================

def create_app(test_config=None):
    """
    Flask application factory.

    Normal use:
        app = create_app()

    Tests:
        app = create_app({
            "TESTING": True,
            "DATABASE": temporary_database
        })

    This makes Step 40 testing much easier.
    """

    app = Flask(
        __name__,
        instance_relative_config=False
    )

    # --------------------------------------------------------
    # DEFAULT CONFIGURATION
    # --------------------------------------------------------

    app.config.from_object(
        Config
    )

    # --------------------------------------------------------
    # TEST CONFIGURATION
    #
    # Step 40 can replace DATABASE without touching
    # the real pageturner.db file.
    # --------------------------------------------------------

    if test_config is not None:
        app.config.update(
            test_config
        )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    init_db_app(app)

    # --------------------------------------------------------
    # CSRF - STEP 33
    # --------------------------------------------------------

    install_csrf_protection(
        app
    )

    # --------------------------------------------------------
    # REGISTER BLUEPRINTS - STEP 39
    # --------------------------------------------------------

    app.register_blueprint(
        auth_bp
    )

    app.register_blueprint(
        shop_bp
    )

    app.register_blueprint(
        admin_bp
    )

    app.register_blueprint(
        api_bp
    )

    # --------------------------------------------------------
    # GLOBAL TEMPLATE VARIABLES
    # --------------------------------------------------------

    @app.context_processor
    def inject_global_values():
        user = current_user()

        cart_data = session.get(
            "cart",
            {}
        )

        if isinstance(
            cart_data,
            dict
        ):
            try:
                cart_count = sum(
                    int(quantity)
                    for quantity
                    in cart_data.values()
                    if int(quantity) > 0
                )

            except (
                ValueError,
                TypeError
            ):
                cart_count = 0

        else:
            cart_count = 0

        role = (
            user["role"]
            if user
            else None
        )

        return {
            "current_user": user,
            "cart_count": cart_count,

            # Compatibility with existing templates.
            "admin_logged_in":
                role == "admin",

            "staff_logged_in":
                role in {
                    "staff",
                    "admin"
                },
        }

    # --------------------------------------------------------
    # ERROR HANDLERS
    # --------------------------------------------------------

    @app.errorhandler(400)
    def bad_request(error):
        return (
            render_template(
                "400.html",
                error=error
            )
            if template_exists(
                app,
                "400.html"
            )
            else (
                "Bad Request: "
                + str(
                    getattr(
                        error,
                        "description",
                        error
                    )
                )
            ),
            400
        )

    @app.errorhandler(403)
    def forbidden(error):
        return (
            render_template(
                "403.html",
                error=error
            )
            if template_exists(
                app,
                "403.html"
            )
            else "403 Forbidden",
            403
        )

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template(
            "404.html"
        ), 404

    @app.errorhandler(413)
    def file_too_large(error):
        flash(
            (
                "Uploaded file is too large. "
                "Cover images must be "
                "1 MB or smaller."
            ),
            "danger"
        )

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    @app.errorhandler(500)
    def internal_server_error(error):
        return render_template(
            "500.html"
        ), 500

    return app


# ============================================================
# OPTIONAL TEMPLATE CHECK
# ============================================================

def template_exists(
    app,
    template_name
):
    """
    Check whether an optional error template exists.

    This lets 400/403 work even if the project only
    currently contains 404.html and 500.html.
    """

    try:
        app.jinja_env.get_template(
            template_name
        )

        return True

    except Exception:
        return False


# ============================================================
# CREATE APPLICATION
# ============================================================

app = create_app()


# ============================================================
# DEVELOPMENT SERVER
# ============================================================

if __name__ == "__main__":

    # Existing database is preserved.
    # schema.sql should use CREATE TABLE IF NOT EXISTS.
    with app.app_context():
        init_db()

    app.run(
        debug=True
    )