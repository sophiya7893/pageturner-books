# PageTurner Books — Windows setup

## Requirements
- Python 3.11 or newer (Python 3.12/3.13 recommended)
- VS Code or another editor

## First-time setup
Open PowerShell in this folder:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python migrate.py
python seed_demo.py
python create_admin.py
python -m pytest -q
python app.py
```

Open `http://127.0.0.1:5000`.

`create_admin.py` prompts for an administrator name, email, and password. It creates a new administrator or resets the role/password for that email. No default admin password is shipped.

## Existing database
The included `pageturner.db` is the project database. Before updating a copy of your own database, make a backup first:

```powershell
python backup.py
python migrate.py
```

The migration runner uses `PAGETURNER_DATABASE` if set. The Flask application and backup command use the same setting. For example, to test on a separate database:

```powershell
$env:PAGETURNER_DATABASE = "$PWD\test-pageturner.db"
python migrate.py
python seed_demo.py
python create_admin.py
python app.py
```

Close the terminal or run `Remove-Item Env:PAGETURNER_DATABASE` to return to the default database.

## Useful commands

```powershell
python migrate.py       # apply only pending numbered migrations
python seed_demo.py     # add sample books/coupons without duplicating them
python create_admin.py  # create/reset an admin login
python backup.py        # create a consistent SQLite backup; keep last five
python -m pytest -q     # run tests
python app.py           # start the local development server
```

## Important notes
- Do not commit real customer data, database backups, `.env` files, or production secrets to Git.
- Set a strong random `SECRET_KEY` environment variable before any deployment.
- This is a local development server. Use a production WSGI server and HTTPS for deployment.
- Payment collection is not connected to a real payment provider unless you add and configure one.
- Keep a separate backup of your own database before structural migrations.
