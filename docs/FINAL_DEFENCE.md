# PageTurner Books — Step 74 Final Defence (Round 2)

## Fresh database demo

1. Make a copy of the project folder or choose a new empty database path.
2. In PowerShell set a fresh database path before migrating:
   ```powershell
   $env:PAGETURNER_DATABASE = "$PWD\defence-fresh.db"
   python migrate.py
   python migrate.py
   ```
3. Confirm that the second run says the database is up to date.
4. Seed demo books/users only using the project's documented seed process; do not copy the existing database into the fresh path.
5. Run `python app.py` and demonstrate customer, admin, search, checkout, order and report flows.

## Explain one of each

### Migration
- Migration files live in `migrations/` and are applied in filename/version order.
- `schema_version` records successful versions.
- Each migration is executed in an explicit transaction. If a migration fails, the transaction is rolled back and its version is not recorded.

### Race-condition protection
- Checkout and stock reservations use a SQLite write transaction (`BEGIN IMMEDIATE`) and re-check stock/reservations before writing the order.
- Database unique constraints protect duplicate cart/wishlist/review/import records even if a Python pre-check is absent.
- Coupon use and stock updates must be performed in the same write transaction as order creation.

### Money calculation
- Store money as integer paise. Example: ₹33.33 = 3333 paise.
- Three books: `3333 * 3 = 9999` paise.
- A 10% discount is rounded half-up to `1000` paise; after discount the subtotal is `8999` paise (₹89.99), before any applicable shipping/tax rules.
- Tax is rounded at the line level in paise so the cart/order/invoice/CSV can share the same persisted amounts.

### Ownership check (403/404)
- Tracking, invoice, return and notification routes should query using both the resource ID and the authenticated user's ID (or allow admin explicitly).
- Demonstrate by signing in as one customer and attempting to open a different customer's order ID. The route must return 403/404 rather than disclose the order.

## Two live changes to practise

1. **Change free shipping from ₹500 to ₹400:** update `site_settings.free_shipping_threshold_paise` to `40000`, then test an order below and above ₹400.
2. **Add “Sort by rating”:** add a `rating_desc` option to the catalogue sort dropdown and map it to the existing SQL `average_rating DESC` ordering, with title as a stable tie-breaker. Verify the selected option remains active after pagination.

## Step 74 completion checklist

- [ ] Fresh database created only with `migrate.py`.
- [ ] Second migration run made no schema changes.
- [ ] Explain a migration and its rollback behavior without notes.
- [ ] Demonstrate concurrent stock/coupon protection.
- [ ] Explain the integer-paise calculation.
- [ ] Demonstrate an order ownership denial.
- [ ] Complete two live changes and re-test the affected flows.
