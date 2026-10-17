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

# ============================================================
# INITIALISE DATABASE
# ============================================================

def init_db():
    """
    Create database tables and safely add missing columns.
    Existing data is preserved.
    """

    db = get_db()

    # Create tables defined in schema.sql
    with current_app.open_resource("schema.sql") as schema_file:
        db.executescript(
            schema_file.read().decode("utf-8")
        )

    # Check whether the reviews table exists
    tables = db.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'reviews'
    """).fetchone()

    if tables:
        # Read existing reviews columns
        review_columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(reviews)"
            ).fetchall()
        }

        # Add name column only if it is missing
        if "name" not in review_columns:
            db.execute(
                "ALTER TABLE reviews ADD COLUMN name TEXT"
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