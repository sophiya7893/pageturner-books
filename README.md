# PageTurner Books

**Current setup guide:** see [`SETUP_WINDOWS.md`](SETUP_WINDOWS.md) for the verified Windows commands, database migration, demo seed, admin setup, backup, and tests.

This is a Flask + SQLite bookstore project with numbered migrations and the requested Steps 42–74 enhancements. Run `python migrate.py` before starting the app on a fresh database. Use `python seed_demo.py` for sample books and `python create_admin.py` to create/reset an administrator account; no default admin password is shipped.

> Back up your own database before applying migrations. The included database is a project copy. Do not use it to overwrite a separate live database.

1. Project Overview

PageTurner Books is a full-stack online bookstore application. Customers can browse, search, filter, sort, register, log in, use a wishlist, manage a shopping cart, apply coupons, complete checkout, review orders, and see order status. Administrators can securely manage books and orders, view sales reports, and export data.

2. Technologies

Python

Flask

SQLite

HTML5

CSS3

JavaScript

Jinja2

Werkzeug password hashing

Fetch API

3. Features

3.1 Customer Features

Book catalogue and book detail pages.

Search by title or author.

Category filtering.

Title/price sorting.

Pagination.

Customer registration, login, and logout.

Secure password hashing.

Shopping cart with quantity updates and removal.

Coupon application.

Wishlist add/remove.

Checkout and order confirmation.

Customer order history.

Order statuses: Placed, Packed, Delivered.

Reviews and 1–5 ratings.

Custom 404 and 500 pages.

3.2 Admin Features

Secure admin login/logout.

Protected admin routes.

Add, edit, and delete books.

Manage customer orders.

Update order status.

Sales report.

Top-selling books.

CSV export.

4. Project Structure

PageTurner Books/
├── app.py
├── schema.sql
├── seed.sql
├── queries.sql
├── README.md
├── pageturner.db
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── book_detail.html
│   ├── cart.html
│   ├── checkout.html
│   ├── order_confirmation.html
│   ├── orders.html
│   ├── wishlist.html
│   ├── 404.html
│   ├── 500.html
│   ├── admin_login.html
│   ├── admin_dashboard.html
│   ├── admin_book_form.html
│   ├── admin_orders.html
│   └── admin_report.html
└── static/
    ├── style.css
    ├── app.js
    └── images/

5. Database Tables

books — catalogue, price, stock, description, cover image.

users — customer accounts and password hashes.

admins — administrator accounts and password hashes.

orders — customer/order totals, discounts, status, and timestamps.

order_items — books and quantities belonging to each order.

reviews — customer ratings and comments.

wishlist — saved customer books with UNIQUE(user_id, book_id).

coupons — code, percentage, expiry date, and active flag.

Indexes are created for common category, order, title, author, order-item, wishlist, review, and coupon lookups.

6. Seed Catalogue

Atomic Habits — James Clear — Self Help — ₹499

Deep Work — Cal Newport — Productivity — ₹450

The 7 Habits of Highly Effective People — Stephen R. Covey — Self Help — ₹599

Think and Grow Rich — Napoleon Hill — Personal Development — ₹399

Ikigai — Héctor García — Lifestyle — ₹350

Clean Code — Robert C. Martin — Programming — ₹699

Python Crash Course — Eric Matthes — Programming — ₹799

The Pragmatic Programmer — Andrew Hunt — Programming — ₹650

A Brief History of Time — Stephen Hawking — Science — ₹550

The Selfish Gene — Richard Dawkins — Science — ₹620

Sapiens — Yuval Noah Harari — History — ₹699

India After Gandhi — Ramachandra Guha — History — ₹799

The Alchemist — Paulo Coelho — Fiction — ₹399

Rich Dad Poor Dad — Robert T. Kiyosaki — Finance — ₹499

7. Coupons

WELCOME10 — 10% discount — active until 2099-12-31.

BOOK20 — 20% discount — active until 2099-12-31.

8. Search, Filter, Sort and Pagination

The home page supports a combined q search parameter for title/author, category filtering, sorting, and pagination. Example: /?q=python&category=Programming&sort=price&page=2.

title_asc

title_desc

price_asc

price_desc

Pagination preserves active search, category, and sort parameters. A no-results message is shown when nothing matches.

9. Cart and Coupons

Customers can add books, update quantities, and remove items.

Cart totals include item subtotals.

Coupon input uses name="coupon_code".

Invalid or expired coupons produce a friendly message.

The navigation displays the cart count.

10. Checkout and Concurrency Safety

Checkout runs inside a transaction and uses this safe stock update:

UPDATE books
SET stock = stock - ?
WHERE id = ?
  AND stock >= ?;

The application checks cursor.rowcount. If it is zero, the requested stock is unavailable and the transaction is rolled back. This prevents two simultaneous purchases from both successfully buying the last copy.

11. Authentication and Security

Passwords are stored with Werkzeug generate_password_hash().

Passwords are verified with check_password_hash().

Customer-only routes require login.

Admin routes require admin authentication.

Set `SECRET_KEY` as an environment variable for any non-local deployment. Use `python create_admin.py` to create or reset the admin account; admin credentials are not hard-coded.

Do not store production passwords or secrets in source code.

12. Wishlist

Logged-in customers can save books.

Toggling an existing book removes it.

Toggling a missing book adds it.

UNIQUE(user_id, book_id) prevents duplicate entries.

Wishlist cards show image, category, title, author, price, stock, and actions.

13. Orders and Status

Successful checkout creates an order and related order_items.

The order confirmation page is named order_confirmation.html.

Customer history is orders.html.

Admins can change status between Placed, Packed, and Delivered.

Customers can see the current status in their order history.

14. Reviews

Book detail pages support review information, including review count and average rating. Server-side validation restricts ratings to 1 through 5.

15. JavaScript and API

static/app.js contains client-side functionality.

/api/books returns JSON book data.

Fetch is used for selected add-to-cart interactions without a full page reload.

The cart badge can update after fetch operations.

16. Validation and Error Handling

Required form fields are validated server-side.

Negative prices are rejected.

Invalid quantities are rejected.

Ratings must be 1–5.

Empty-cart checkout is prevented.

Custom 404 and 500 handlers are included.

Database transactions roll back on checkout errors.

17. Admin Sales Report

The sales report calculates total orders, total sales, books sold, and top-selling books from the orders and order_items tables. A new database with no orders will correctly display zero values until a successful order is created.

18. Important Routes

/ — Home/catalogue

/book/<book_id> — Book detail

/api/books — JSON API

/register — Register

/login — Login

/logout — Logout

/wishlist — Wishlist

/wishlist/toggle/<book_id> — Wishlist toggle

/cart — Cart

/cart/add/<book_id> — Add to cart

/cart/update — Update cart

/cart/remove/<book_id> — Remove item

/cart/coupon — Apply coupon

/checkout — Checkout

/order/<order_id> — Order confirmation

/orders — Order history

/admin/login — Admin login

/admin/logout — Admin logout

/admin — Dashboard

/admin/books/add — Add book

/admin/books/edit/<book_id> — Edit book

/admin/books/delete/<book_id> — Delete book

/admin/orders — Manage orders

/admin/report — Sales report

/admin/export — CSV export

19. Installation and Running

Follow `SETUP_WINDOWS.md` for the current setup steps. In short:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python migrate.py
python seed_demo.py
python create_admin.py
python -m pytest -q
python app.py
```

Open `http://127.0.0.1:5000`. Always run the numbered `migrate.py` runner on a fresh database; do not run legacy migration helper scripts directly.

20. Configuration

- `SECRET_KEY` — Flask session signing secret; use a strong random value outside local development.
- `PAGETURNER_DATABASE` — optional path to the SQLite database. The app, migration runner, seed command, and backup command use this same environment variable.
- `python create_admin.py` — interactively creates or resets an administrator account. No default password is documented or hard-coded.

Keep real customer data, backups, `.env` files, and production secrets out of Git.

21. GitHub Update Workflow

Make changes in the local project.

Run git status.

Run git add .

Run git commit -m "Update PageTurner Books"

Run git push origin main.

Refresh GitHub and verify the changed files.

Git commands are run from the local project folder. GitHub is the remote repository.

22. Testing Checklist

Home page loads.

Search works.

Category and sorting work.

Pagination works.

Book detail works.

Registration/login work.

Wishlist add/remove works.

Cart add/update/remove works.

Quantity validation works.

Valid and invalid coupons work.

Checkout creates an order.

Stock decreases safely.

Concurrent last-copy checkout allows only one successful order.

Order confirmation works.

Order history works.

Admin authentication works.

Admin book management works.

Admin order status works.

Sales report reflects orders.

404/500 pages work.

23. Troubleshooting

If Sales Report shows 0, check that the orders table contains completed orders.

If images show 404, verify the cover filename matches a file in static/images/.

If coupons fail, confirm the form field is coupon_code.

If cart quantities fail, confirm the form posts to update_cart and uses quantity_<book_id>.

If checkout fails, inspect the Flask terminal and database transaction error.

If GitHub does not show changes, check git status, commit, and push to the correct branch.

24. SQL Examples

Search:
SELECT * FROM books WHERE title LIKE ? OR author LIKE ?;

Category:
SELECT * FROM books WHERE category = ?;

Safe stock update:
UPDATE books SET stock = stock - ? WHERE id = ? AND stock >= ?;

Customer orders:
SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC;

25. Application Flow

Customer browses books.

Customer searches/filters/sorts.

Customer opens a book.

Customer adds it to the cart.

Customer optionally applies a coupon.

Customer logs in/registers.

Customer completes checkout.

The transaction safely updates stock and saves the order.

Customer sees confirmation and order history.

Admin manages books, orders, status, reports, and exports.

26. Production Recommendations

Use HTTPS.

Use a production WSGI server.

Use strong secrets and secure cookies.

Back up the database.

Do not commit private credentials or sensitive production data.

Add CSRF protection for production forms.

Review authorization on all state-changing routes.

27. Project Status

PageTurner Books contains the main bookstore workflow: catalogue browsing, search/filter/sort/pagination, authentication, wishlist, cart, coupons, safe checkout, orders, order status, reviews, admin management, reporting, JSON/fetch functionality, validation, indexes, and custom error handling.

28. License

This project was created as an educational bookstore web application using Flask and SQLite.

## Steps 42–45: shared layout, design system, feedback, responsive UI

The project uses `templates/base.html` for the shared header, navigation, cart count,
login/logout links, flash-message banners, and footer. Page templates extend this base
and provide their own `{% block content %}`. Shared styles are loaded from
`static/style.css`; colors and common design values are CSS custom properties in `:root`.

The stylesheet includes reusable buttons, cards, forms, tables, book-grid layouts,
and responsive rules at 900px, 600px, and smaller widths. No Bootstrap or CSS CDN is
required. Custom 403, 404, and 500 pages extend the shared base and include a Back to
home link. Oversized uploads use a matching custom error page too.

### Run locally

1. Install Python 3.10 or newer.
2. Create and activate a virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Back up `pageturner.db` before applying any database migrations.
5. Run `python migrate.py` if your database needs the project's migrations.
6. Start the site with `python app.py` and open `http://127.0.0.1:5000`.

The current development environment used for this update did not have Flask installed,
so application-level browser/client tests could not be executed here. Python syntax
compilation and template/layout checks were performed.


## Roadmap Steps 46–48: Money, Migrations, Categories

- Monetary fields use integer paise (for example, ₹199.50 is stored as `19950`). Templates use the shared Jinja `money` filter; the formatter uses integer division and never converts paise to float. CSV order exports format the same integer-paise values as rupee strings.
- `migrate.py` applies numbered SQL files in `migrations/` in ascending order, records applied versions in `schema_version`, skips already-applied versions, and executes each migration in its own explicit transaction. It can be run repeatedly.
- Before structural migration work, a copy of the current database is included as `pageturner-before-steps-46-48.db`. Keep a separate copy of your own live database before running migrations on your machine.
- `005_category_backfill.sql` copies the existing `books.category` values into `categories` and `book_categories`. Category filters use a single query with `GROUP BY` and `HAVING COUNT(DISTINCT ...)` for multiple selected categories. The old `books.category` text column remains temporarily for compatibility with older routes and imports; normalized relationships are used for multi-category filtering.
- Coupon fixed discounts, minimum order thresholds, and maximum discounts are stored in integer paise. Percentage values remain percentages, not money. Legacy rupee-valued coupon columns are converted and removed by the migration runner.

### Run the migrations

1. Stop the application and make a copy of `pageturner.db`.
2. Install packages: `python -m pip install -r requirements.txt`.
3. Run: `python migrate.py`.
4. Run `python migrate.py` a second time to verify that no migrations are repeated.
5. Start the app with `python app.py`.

If the database is in another location, set `PAGETURNER_DATABASE` to its path before running `migrate.py`.

## Roadmap Steps 49–56: Better Shopping

- Catalogue search, multi-category filters, sorting, and eight-item pagination run through parameterized SQL. Category selections, search terms, and sort choice remain applied when moving between pages; out-of-range page numbers are clamped safely.
- Book cards and detail pages show available stock, including active reservations. Out-of-stock books cannot be added, and the server validates stock regardless of the browser UI.
- Wishlist rows are protected by a database unique constraint. Logged-in carts are stored in `cart_items`; guest carts remain in the session and are merged into the database cart after login, capped by available stock.
- Opening checkout reserves cart quantities for ten minutes. Active reservations reduce availability to other customers, while expired reservations are ignored automatically.
- Reviews require a purchase, use a rating from 1 to 5, and are protected against duplicate customer/book reviews by a unique database index. Average ratings are computed in SQL.
- The customer profile displays order count and total spend from SQL aggregates. Change Password asks for the current password before allowing a change.

### Testing note

The update passed Python syntax compilation, parsing of all 39 Jinja templates, SQLite integrity checks, and SQLite-level tests for multi-category filtering and unique wishlist/cart rows. Flask route/browser integration tests could not run in this build environment because Flask was not installed and package installation was unavailable offline. Run `python -m pip install -r requirements.txt` and `python -m pytest` on your machine to run the full test suite.


## Roadmap Steps 57–63: Orders, Payments, Invoices and Returns

- Order statuses use one `ALLOWED_STATUS_MOVES` dictionary: Placed → Packed → Shipped → Delivered, or Placed → Cancelled. Each status update writes the actor, timestamp and note to `order_status_history`. New orders create their initial Placed history row; migration 008 backfills history for existing orders.
- `/orders/<id>/tracking` is restricted to the order owner and displays a CSS timeline. `/orders/<id>/invoice` is available only to the owner or an admin/staff account and includes subtotal, discount, shipping, tax and total; print styles hide navigation and buttons.
- Coupon administration supports create, deactivate/activate and delete, expiry, usage limit, minimum order, maximum discount, one use per customer and an optional category. Checkout revalidates coupon rules inside the order transaction and records `coupon_uses` so simultaneous requests cannot both consume a limit-one coupon.
- Shipping is looked up by the first two digits of the delivery pincode using `shipping_zones` (legacy first-digit zone rows remain as a fallback). Shipping is free at or above the `free_shipping_threshold_paise` site setting (the included default is ₹500). Tax is 5%, calculated per order line with integer-paise half-up rounding. Subtotal, discount, shipping, tax and total are stored on the order and used by checkout, order details, invoice and CSV export.
- Return requests are limited to delivered orders and to the unreturned quantity for each order item. Admin approval restores stock and writes `stock_log` within one `BEGIN IMMEDIATE` transaction. A request already reviewed cannot restore stock twice.

### Step 57–63 migration and verification

1. Stop the app and make a separate copy of `pageturner.db`.
2. Install dependencies with `python -m pip install -r requirements.txt`.
3. Run `python migrate.py`; migration `008_orders_shipping_returns.sql` adds the two-digit shipping zones and indexes, backfills status history, and safely rebuilds legacy orders whose status constraint omitted `Shipped`.
4. Run `python migrate.py` a second time; completed migrations are skipped.
5. Run `python -m pytest`, then start with `python app.py`.

The migration was tested against both the bundled database copy and a fresh database: the second run made no changes, and SQLite foreign-key checks returned no violations. Python compilation and Jinja parsing passed. Full Flask request/browser tests could not be executed in this environment because Flask is not installed here.


## Steps 64–67: Security, API, and reporting

- Run `python migrate.py` before starting the app. Migration `009_security_reporting_indexes.sql` adds lookup indexes and is safe to re-run.
- `/devices` lists active browser sessions. Session tokens are random values kept in the signed browser session; the database stores only SHA-256 hashes. Revoke a device to make its next request sign out, or use **Log out everywhere** to revoke all sessions including the current one.
- `/api/books`, `/api/books?q=term`, and `/api/books/<id>` are read-only JSON endpoints. Missing book IDs return JSON with HTTP 404. `/api/` requests are limited to 30 per minute per remote IP and return JSON HTTP 429 when the limit is reached.
- Successful state-changing `/admin...` requests are recorded in `admin_log` automatically.
- `/admin/reports` accepts a date range and can export the daily order totals as CSV. Monetary amounts in the report and CSV are integer paise; the return total is the value of approved returned items.
- Before applying migrations to a live database, make a separate copy of the `.db` file.


## Stretch steps 68–74

### Step 68 — Live search suggestions
The catalogue search uses plain JavaScript `fetch()` against `/api/books?q=...`. Suggestions start at two characters, are debounced, show at most five matches, and hide quietly when no matches are returned.

### Step 69 — Contact messages
Visitors can submit a contact form. Required fields are validated server-side and the form uses the shared CSRF token. Administrators can review messages and mark them as read at `/admin/messages`.

### Step 70 — In-app notifications
The shared header shows the unread count. Notification queries are scoped to the logged-in user; opening a notification marks only that user's row as read. Database triggers create notifications for order status history changes, return decisions and wishlist restocks.

### Step 71 — CSV book import
Administrators can import a CSV at `/admin/books/import`. Required columns are `title,author,price,stock,category`; optional columns are `description,cover_image`. Valid rows are inserted in one transaction, rejected rows report their CSV row number and reason, exact-file imports are idempotent, and title/author duplicates are skipped. Imported categories are linked into `categories` and `book_categories`.

### Step 72 — Online-safe SQLite backup
Run `python backup.py`. The script uses `sqlite3.Connection.backup()` so it can run while the application is using the database. It creates a timestamped file under `backups/` and retains only the newest five. Optional arguments: `--database`, `--backup-dir`, and `--keep`.

### Step 73 — Ranked search
The catalogue and `/api/books?q=term` rank title matches first (score 3), author matches second (score 2), and tag matches third (score 1). Values are parameterized; an empty result still displays “No books found”.

### Step 74 — Final defence checklist
See `docs/FINAL_DEFENCE.md` for the fresh-database demo procedure, migration/race-condition/money/ownership explanations, and two quick live-change exercises.
