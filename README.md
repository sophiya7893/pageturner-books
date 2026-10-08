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

SECRET_KEY, ADMIN_EMAIL, and ADMIN_PASSWORD can be configured with environment variables.

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

Install Python 3.x.

Open a terminal in the project folder.

Optionally create a virtual environment.

Install Flask and required packages.

Ensure schema.sql and seed.sql are available.

Run python app.py.

Open the local Flask URL in a browser.

Example:
python -m venv venv
venv\Scripts\activate
pip install flask
python app.py

20. Configuration

SECRET_KEY — Flask session secret.

ADMIN_EMAIL — administrator email.

ADMIN_PASSWORD — administrator password/initial setup value.

Use strong production secrets and keep them outside Git.

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

## License

This project was created as an educational bookstore web application using Flask and SQLite.
