# PageTurner Books — Consolidated Roadmap Status (Steps 42–74)

This build consolidates the requested storefront, database, shopping, order, security, API, admin, and stretch features. The numbered SQL migrations are authoritative; `schema.sql` remains for legacy compatibility and test setup.

## Look and feel — Steps 42–45
- Shared `base.html` header, navigation, cart/unread notification counts, flash banners, and footer.
- Hand-written responsive CSS design system; no Bootstrap or CSS CDN.
- Custom 403, 404, 413, and 500 pages.
- Templates extend the shared base; catalogue layout collapses on narrow screens.

## Foundation — Steps 46–48
- Currency stored as integer paise; shared Jinja `money` filter for display.
- Numbered transactional migrations, `schema_version`, rollback for a failed migration, and repeatable migration runs.
- Normalized `categories`, `book_categories`, `tags`, and `book_tags`; old category values are backfilled by migration.

## Better shopping — Steps 49–56
- Parameterized title/author/tag search, multi-category filter, ranking, sorting, and 8-item pagination.
- Stock badges and server-side stock validation.
- Unique wishlist rows, database cart for signed-in users, session cart for guests, and cart merge on login.
- Ten-minute stock reservations with expiration checks.
- Purchase-verified reviews and SQL average ratings.
- Customer profile aggregates and current-password validation for password changes.

## Orders and money — Steps 57–63
- One shared order-status transition dictionary in `order_rules.py`; every status update is recorded in history.
- Owner-only tracking and invoice pages (both `/order/<id>/invoice` and `/orders/<id>/invoice` are supported).
- Admin coupon create/edit/activate/deactivate/delete; expiry, usage limits, minimum and maximum discount, per-customer limit, and optional category restriction.
- Pincode-zone shipping, free-shipping threshold, 5% line-level tax rounding, and stored paise totals.
- Partial return requests with quantity validation, transactional stock restoration, and stock logs.

## Security, API and admin — Steps 64–67
- Hashed device-session tokens and individual/all-device revocation.
- Read-only JSON book API with JSON 404 responses.
- Database-backed 30-per-minute IP rate limit and automatic admin activity logging.
- Date-range reports and CSV export.

## Stretch — Steps 68–74
- Debounced live suggestions after two characters.
- CSRF-protected contact form and admin message inbox.
- User-scoped notifications and unread count; triggers for order updates, return decisions, and wishlist restocks.
- Transactional CSV import with row-level error report and duplicate protection.
- SQLite online backup command with latest-five retention.
- Search ranking by title, author, then tags.
- Final defence instructions in `docs/FINAL_DEFENCE.md`.

## Verification performed for this build
- `python -m compileall -q .` passed.
- `python -m pytest -q`: 25 tests passed using Flask 3.1.3 and its dependencies from the original project environment.
- Fresh database migrations 001–011 applied; the second run made no changes.
- `PRAGMA integrity_check` returned `ok`; `PRAGMA foreign_key_check` returned no violations.
- Public pages, API routes, admin pages, coupon creation, and a checkout/order creation path were exercised with Flask's test client.
- A template endpoint audit found no missing `url_for` endpoints.
- Money-related database columns were checked; none are declared REAL/FLOAT/DOUBLE.

## Local setup
Follow [`SETUP_WINDOWS.md`](SETUP_WINDOWS.md). Before applying migrations to your own database, create a separate backup with `python backup.py`.
