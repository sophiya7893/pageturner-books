# PageTurner Books

An online bookstore built with **Flask, SQLite, HTML, CSS, and JavaScript**.

PageTurner Books allows customers to browse books, search and filter the catalogue, add books to a cart, place orders, submit reviews, and find previous orders using their phone number. It also includes an admin area for managing books and viewing sales reports.

## Features

### Customer Features

* Browse available books
* Search books by title or other catalogue information
* Filter books by category
* Sort books by title or price
* Paginate the book catalogue with 6 books per page
* View individual book details
* Add books to the shopping cart
* Increase or decrease cart quantities
* Prevent customers from ordering more books than available stock
* Display **Out of Stock** when a book has no stock
* Reduce stock automatically after checkout
* Submit book reviews with a 1–5 star rating
* Display the average rating for books
* Checkout with customer name, phone number, and delivery address
* Find previous orders using a phone number
* Display a friendly message when no orders are found

### Admin Features

* Admin login protected by a password
* Session-based admin authentication
* Add new books
* Edit existing books
* Delete books
* Manage book stock
* View sales reports
* View total orders and revenue
* View best-selling books
* View orders grouped by category

## Technologies Used

* **Python**
* **Flask**
* **SQLite**
* **HTML5**
* **CSS3**
* **JavaScript**
* **Jinja2**

## Project Structure

```text
pageturner-books/
│
├── static/
│   ├── app.js
│   ├── style.css
│   └── images/
│
├── templates/
│   ├── admin_book_form.html
│   ├── admin_login.html
│   ├── admin.html
│   ├── base.html
│   ├── book_detail.html
│   ├── cart.html
│   ├── checkout.html
│   ├── home.html
│   ├── order.html
│   ├── orders.html
│   └── report.html
│
├── app.py
├── pageturner.db
├── queries.sql
├── README.md
├── requirements.txt
├── schema.sql
└── seed.sql
```

## Run the Project

Open PowerShell in the project folder.

### 1. Create a virtual environment

```powershell
python -m venv .venv
```

### 2. Activate the virtual environment

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate the environment again:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install the required packages

```powershell
python -m pip install -r requirements.txt
```

### 4. Start the Flask application

```powershell
python app.py
```

Open the local address shown by Flask in your browser.

## Database

The project uses an existing SQLite database:

```text
pageturner.db
```

The application connects to this database through Flask and SQLite.

The project also includes:

```text
schema.sql
seed.sql
queries.sql
```

`schema.sql` contains the database structure, `seed.sql` contains initial book/sample data, and `queries.sql` contains SQL queries used by the project and reporting features.

## Stock Control

Each book has a stock quantity.

The application:

1. Checks available stock before adding a book to the cart.
2. Prevents the customer from adding more copies than are available.
3. Shows an **Out of Stock** badge when stock reaches zero.
4. Checks stock again during checkout.
5. Reduces the database stock after a successful purchase.

The final checkout check is important because the stock may have changed after the customer added the book to their cart.

## Reviews and Ratings

Customers can submit reviews containing:

* Name
* Rating from 1 to 5
* Comment

The application calculates the average rating for each book using the reviews stored in the database.

Multiple reviews are included when calculating the average.

## Order History

Customers can find their orders by entering the phone number used during checkout.

The order history uses SQL joins and grouping to retrieve order information and the number of items in each order.

If the phone number does not match an order, the application displays a friendly **No orders found** message.

## Admin Area

The admin section is protected by a password stored in the application configuration.

After successful login, an admin session is created.

The admin can:

* Add books
* Edit books
* Delete books
* Update stock
* View the admin dashboard
* View sales reports

Unauthenticated users attempting to access protected admin pages are redirected to the admin login page.

## Reports

The admin report page provides database-driven information including:

* Total number of orders
* Total revenue
* Best-selling books
* Orders per category

The report uses SQL aggregate functions such as:

```sql
COUNT()
SUM()
GROUP BY
ORDER BY
```

## Sorting and Pagination

The book catalogue supports sorting by:

* Title
* Price

The catalogue displays **6 books per page** using SQL:

```sql
LIMIT
OFFSET
```

Customers can move between pages using **Previous** and **Next** controls.

Category filtering and sorting can be used together.

## SQL Queries

The `queries.sql` file contains the required database queries for the project.

It includes queries for:

* Book information
* Searching/filtering
* Sorting
* Stock information
* Reviews and ratings
* Order information
* Best-selling books
* Revenue
* Orders by category

The report section contains the required aggregate SQL queries.

## Testing

The following cases should be tested before demonstrating the project:

### Cart Testing

* Add a book to the cart.
* Increase the quantity.
* Try to add more copies than available stock.
* Try to add a book with zero stock.
* Remove a book from the cart.
* Test an empty cart.
* Test quantity `0`.

### Checkout Testing

* Place an order successfully.
* Confirm that stock decreases after checkout.
* Buy the last available copy.
* Confirm that the book becomes **Out of Stock**.
* Try purchasing a book after its stock reaches zero.

### Order History Testing

* Search using a valid phone number.
* Search using an incorrect phone number.
* Confirm that a friendly no-orders message is displayed.

### Admin Testing

* Open the admin page without logging in.
* Confirm that the user is redirected to the login page.
* Log in with the correct admin password.
* Add a book.
* Edit a book.
* Delete a book.
* Check the admin report.

### Review Testing

* Add one review.
* Add multiple reviews for the same book.
* Confirm that the average rating changes correctly.

## Important Stock-Concurrency Consideration

If two customers try to purchase the last copy at nearly the same time, the checkout operation should perform the stock check and stock update as part of a database transaction.

SQLite transactions help prevent both customers from successfully reducing the same single stock item.

The application should never rely only on the stock value displayed when the customer adds the book to the cart. The stock must be checked again during checkout.

## Admin Password

The admin password is kept in a variable in the Flask application and is checked during admin login.

For a real production application, the password should not be hard-coded. A secure environment variable and password hashing system should be used instead.

## License

This project was created as an educational bookstore web application using Flask and SQLite.
