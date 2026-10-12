import sqlite3

from flask import current_app, g


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():
    """
    Return one SQLite connection for the current Flask request.

    The connection is stored in Flask's `g` object so the same
    request does not repeatedly open new database connections.
    """

    if "db" not in g:

        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            timeout=10
        )

        # Allows:
        # row["title"]
        # instead of:
        # row[0]
        g.db.row_factory = sqlite3.Row

        # Enforce SQLite foreign keys.
        g.db.execute(
            "PRAGMA foreign_keys = ON"
        )

        # Wait for a locked database instead of failing
        # immediately.
        g.db.execute(
            "PRAGMA busy_timeout = 10000"
        )

    return g.db


# ============================================================
# CLOSE DATABASE
# ============================================================

def close_db(error=None):
    """
    Close the database connection when the Flask request ends.
    """

    db = g.pop(
        "db",
        None
    )

    if db is not None:
        db.close()


# ============================================================
# INITIALISE DATABASE
# ============================================================

def init_db():
    """
    Create database tables using schema.sql.

    Existing tables/data are preserved because schema.sql
    should use CREATE TABLE IF NOT EXISTS.
    """

    db = get_db()

    with current_app.open_resource(
        "schema.sql"
    ) as schema_file:

        db.executescript(
            schema_file.read().decode(
                "utf-8"
            )
        )

    db.commit()


# ============================================================
# REGISTER DATABASE WITH FLASK
# ============================================================

def init_app(app):
    """
    Register database cleanup with the Flask application.
    """

    app.teardown_appcontext(
        close_db
    )