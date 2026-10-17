"""Add-on routes for PageTurner Books steps 64-74."""
import csv, hashlib, io, secrets, sqlite3, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from db import get_db
from security import login_required, admin_required, generate_csrf_token

extras_bp = Blueprint('extras', __name__)


def _hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def install_extras(app):
    @app.before_request
    def _extras_security():
        # API rate limiting is stored in SQLite and applies to every /api/ request.
        if request.path.startswith('/api/'):
            conn = get_db()
            now = int(time.time())
            # Use the socket peer address by default. Trusting arbitrary X-Forwarded-For
            # values lets clients rotate spoofed IPs to evade the rate limit.
            ip = request.remote_addr or 'unknown'
            conn.execute('DELETE FROM api_rate_limits WHERE requested_at < ?', (now - 60,))
            count = conn.execute('SELECT COUNT(*) FROM api_rate_limits WHERE ip=? AND requested_at > ?', (ip, now - 60)).fetchone()[0]
            if count >= 30:
                conn.commit()
                return jsonify(error='rate limit exceeded', message='Maximum 30 API requests per minute.'), 429
            conn.execute('INSERT INTO api_rate_limits(ip,requested_at) VALUES (?,?)', (ip, now))
            conn.commit()
        # A revoked session token is rejected on the next request.
        uid, raw = session.get('user_id'), session.get('_device_token')
        if uid and raw:
            row = get_db().execute('SELECT id FROM user_sessions WHERE user_id=? AND token_hash=?', (uid, _hash_token(raw))).fetchone()
            if not row:
                session.clear()
                flash('This session was revoked. Please log in again.', 'error')
                if request.endpoint not in ('auth.login', 'static'):
                    return redirect(url_for('auth.login'))
            else:
                get_db().execute('UPDATE user_sessions SET last_seen=CURRENT_TIMESTAMP WHERE id=?', (row['id'],))
                get_db().commit()
        elif uid:
            # Clear stale cookies instead of attempting a foreign-key insert
            # for a user account that no longer exists.
            account = get_db().execute(
                'SELECT id FROM users WHERE id = ?', (uid,)
            ).fetchone()
            if account is None:
                session.clear()
            else:
                raw = secrets.token_urlsafe(32)
                get_db().execute(
                    'INSERT INTO user_sessions(user_id,token_hash,user_agent) VALUES (?,?,?)',
                    (uid, _hash_token(raw), request.user_agent.string[:250]),
                )
                get_db().commit()
                session['_device_token'] = raw

    @app.after_request
    def _automatic_admin_audit(response):
        if request.path.startswith('/admin') and request.method in ('POST','PUT','PATCH','DELETE') and response.status_code < 400:
            uid = session.get('user_id')
            if uid:
                try:
                    get_db().execute('INSERT INTO admin_log(user_id,action,target) VALUES (?,?,?)', (uid, request.method + ' ' + request.path, request.path))
                    get_db().commit()
                except Exception:
                    current_app.logger.exception('Unable to write admin activity log')
        return response


@extras_bp.route('/api/books/<int:book_id>')
def api_book_detail(book_id):
    row = get_db().execute('''SELECT id,title,author,category,price_paise,stock,description,cover_image,created_at FROM books WHERE id=?''', (book_id,)).fetchone()
    if not row:
        return jsonify(error='not found'), 404
    return jsonify(dict(row))


@extras_bp.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip()
        message = request.form.get('text','').strip()
        if not name or not email or not message:
            flash('Please fill in your name, email, and message.', 'error')
            return render_template('contact.html'), 400
        if len(message) > 5000 or len(name) > 120 or len(email) > 254:
            flash('Please shorten the submitted information.', 'error')
            return render_template('contact.html'), 400
        get_db().execute('INSERT INTO messages(name,email,text) VALUES (?,?,?)', (name,email,message))
        get_db().commit()
        flash('Your message has been sent. Thank you!', 'success')
        return redirect(url_for('extras.contact'))
    return render_template('contact.html')


@extras_bp.route('/admin/messages')
@admin_required
def admin_messages():
    rows = get_db().execute('SELECT * FROM messages ORDER BY is_read ASC, created_at DESC').fetchall()
    return render_template('admin_messages.html', messages=rows)


@extras_bp.route('/admin/messages/<int:message_id>/read', methods=['POST'])
@admin_required
def admin_message_read(message_id):
    cur = get_db().execute('UPDATE messages SET is_read=1 WHERE id=?', (message_id,))
    get_db().commit()
    if not cur.rowcount:
        abort(404)
    flash('Message marked as read.', 'success')
    return redirect(url_for('extras.admin_messages'))


@extras_bp.route('/notifications')
@login_required
def notifications():
    uid = session['user_id']
    rows = get_db().execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC', (uid,)).fetchall()
    return render_template('notifications.html', notifications=rows)


@extras_bp.route('/notifications/<int:notification_id>')
@login_required
def open_notification(notification_id):
    conn = get_db(); uid = session['user_id']
    row = conn.execute('SELECT * FROM notifications WHERE id=? AND user_id=?', (notification_id,uid)).fetchone()
    if not row:
        abort(404)
    conn.execute('UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?', (notification_id,uid)); conn.commit()
    target = row['link'] or url_for('extras.notifications')
    if not target.startswith('/') or target.startswith('//'):
        target = url_for('extras.notifications')
    return redirect(target)


@extras_bp.route('/devices')
@login_required
def devices():
    rows = get_db().execute('SELECT id,user_agent,created_at,last_seen,token_hash FROM user_sessions WHERE user_id=? ORDER BY last_seen DESC', (session['user_id'],)).fetchall()
    current_hash = _hash_token(session.get('_device_token',''))
    # Never send token hashes to the browser, even though they are not raw tokens.
    devices_list = [
        {
            'id': row['id'],
            'user_agent': row['user_agent'],
            'created_at': row['created_at'],
            'last_seen': row['last_seen'],
            'is_current': bool(current_hash and row['token_hash'] == current_hash),
        }
        for row in rows
    ]
    return render_template('devices.html', devices=devices_list)


@extras_bp.route('/devices/<int:device_id>/revoke', methods=['POST'])
@login_required
def revoke_device(device_id):
    conn=get_db(); uid=session['user_id']
    row=conn.execute('SELECT token_hash FROM user_sessions WHERE id=? AND user_id=?',(device_id,uid)).fetchone()
    if not row: abort(404)
    conn.execute('DELETE FROM user_sessions WHERE id=? AND user_id=?',(device_id,uid)); conn.commit()
    if row['token_hash']==_hash_token(session.get('_device_token','')): session.clear(); flash('This device has been logged out.','success'); return redirect(url_for('auth.login'))
    flash('Device session revoked.','success'); return redirect(url_for('extras.devices'))


@extras_bp.route('/devices/revoke-all', methods=['POST'])
@login_required
def revoke_all_devices():
    conn=get_db(); uid=session['user_id']
    # Revoke every token, including this browser, to implement true log out everywhere.
    conn.execute('DELETE FROM user_sessions WHERE user_id=?',(uid,)); conn.commit()
    session.clear()
    flash('All devices have been logged out. Please sign in again to continue.','success')
    return redirect(url_for('auth.login'))


@extras_bp.route('/admin/books/import', methods=['GET','POST'])
@admin_required
def import_books():
    if request.method == 'POST':
        upload=request.files.get('file')
        if not upload or not upload.filename.lower().endswith('.csv'):
            flash('Choose a CSV file.','error'); return redirect(url_for('extras.import_books'))
        raw=upload.read()
        digest=hashlib.sha256(raw).hexdigest(); conn=get_db()
        if conn.execute('SELECT 1 FROM book_imports WHERE file_hash=?',(digest,)).fetchone():
            flash('This exact CSV file was already imported. No duplicate books were added.','error'); return redirect(url_for('extras.import_books'))
        try: text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            flash('CSV must use UTF-8 encoding.','error'); return redirect(url_for('extras.import_books'))
        reader=csv.DictReader(io.StringIO(text)); errors=[]; valid=[]
        for line,row in enumerate(reader,start=2):
            title=(row.get('title') or '').strip(); author=(row.get('author') or '').strip(); category=(row.get('category') or '').strip()
            try:
                price_text=(row.get('price') or row.get('price_rupees') or '').strip()
                if not title or not author or not category: raise ValueError('title, author, and category are required')
                if not price_text: raise ValueError('price is required')
                amount=Decimal(price_text)
                if not amount.is_finite() or amount < 0: raise ValueError('price must be a non-negative amount')
                price_paise=int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                stock=int(row.get('stock') or '')
                if stock<0: raise ValueError('stock cannot be negative')
                valid.append((title,author,category,price_paise,stock,(row.get('description') or '').strip(),(row.get('cover_image') or '').strip()))
            except (ValueError, TypeError, InvalidOperation) as exc: errors.append(f'Row {line}: invalid or missing value ({exc})')
        if not valid:
            flash('No valid rows found. ' + '; '.join(errors[:10]),'error'); return render_template('import_books.html', errors=errors, added=0)
        try:
            conn.execute('BEGIN IMMEDIATE')
            added=0
            for item in valid:
                exists=conn.execute('SELECT 1 FROM books WHERE title=? COLLATE NOCASE AND author=? COLLATE NOCASE',(item[0],item[1])).fetchone()
                if exists: errors.append(f"Duplicate: {item[0]} by {item[1]} (skipped)"); continue
                cur = conn.execute('INSERT INTO books(title,author,category,price_paise,stock,description,cover_image) VALUES (?,?,?,?,?,?,?)',item)
                book_id = cur.lastrowid
                # Keep the normalized multi-category filter in sync with CSV imports.
                category_row = conn.execute('SELECT id FROM categories WHERE name=? COLLATE NOCASE', (item[2],)).fetchone()
                if category_row:
                    category_id = category_row['id']
                else:
                    category_id = conn.execute('INSERT INTO categories(name) VALUES (?)', (item[2],)).lastrowid
                conn.execute('INSERT OR IGNORE INTO book_categories(book_id,category_id) VALUES (?,?)', (book_id, category_id))
                added+=1
            conn.execute('INSERT INTO book_imports(file_hash) VALUES (?)',(digest,)); conn.commit()
        except Exception:
            conn.rollback(); raise
        flash(f'Import complete: {added} books added, {len(errors)} rows skipped or rejected.','success')
        return render_template('import_books.html', errors=errors, added=added)
    return render_template('import_books.html', errors=[], added=None)


@extras_bp.route('/admin/reports')
@admin_required
def reports_range():
    from_date=request.args.get('from_date','').strip(); to_date=request.args.get('to_date','').strip()
    if not from_date or not to_date:
        return render_template('reports_range.html', from_date=from_date,to_date=to_date, report=None, rows=[], error=None)
    try:
        start=datetime.strptime(from_date,'%Y-%m-%d').date(); end=datetime.strptime(to_date,'%Y-%m-%d').date()
        if end < start: raise ValueError('The to-date must be on or after the from-date.')
    except ValueError as exc:
        return render_template('reports_range.html',from_date=from_date,to_date=to_date,report=None,rows=[],error=str(exc))
    conn=get_db()
    params=(from_date+' 00:00:00',to_date+' 23:59:59')
    report=conn.execute('''SELECT COUNT(*) order_count, COALESCE(SUM(total_paise),0) revenue,
      CASE WHEN COUNT(*)=0 THEN 0 ELSE CAST(SUM(total_paise) / COUNT(*) AS INTEGER) END average_order_value
      FROM orders WHERE created_at BETWEEN ? AND ? AND COALESCE(status,'') <> 'Cancelled' ''',params).fetchone()
    rows=conn.execute('''SELECT substr(created_at,1,10) day, COUNT(*) orders, COALESCE(SUM(total_paise),0) revenue
      FROM orders WHERE created_at BETWEEN ? AND ? AND COALESCE(status,'') <> 'Cancelled'
      GROUP BY substr(created_at,1,10) ORDER BY day''',params).fetchall()
    best=conn.execute('''SELECT COALESCE(c.name,b.category,'Uncategorized') category, SUM(oi.quantity) sold
      FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN books b ON b.id=oi.book_id
      LEFT JOIN book_categories bc ON bc.book_id=b.id LEFT JOIN categories c ON c.id=bc.category_id
      WHERE o.created_at BETWEEN ? AND ? GROUP BY category ORDER BY sold DESC LIMIT 1''',params).fetchone()
    # Support both the legacy per-item returns table (order_item_id,
    # requested_at) and the newer return-request + return_items structure.
    return_columns = {row['name'] for row in conn.execute("PRAGMA table_info('returns')").fetchall()}
    if {'order_item_id', 'quantity'}.issubset(return_columns):
        return_date_column = 'created_at' if 'created_at' in return_columns else 'requested_at'
        returns_total = conn.execute(f"""SELECT COALESCE(SUM(r.quantity * oi.price_paise),0)
          FROM returns r JOIN order_items oi ON oi.id=r.order_item_id
          JOIN orders o ON o.id=oi.order_id
          WHERE r.{return_date_column} BETWEEN ? AND ? AND r.status='Approved'""",
          (from_date+' 00:00:00',to_date+' 23:59:59')).fetchone()[0]
    else:
        return_date_column = 'created_at' if 'created_at' in return_columns else 'requested_at'
        returns_total = conn.execute(f"""SELECT COALESCE(SUM(ri.quantity * oi.price_paise),0)
          FROM returns r JOIN return_items ri ON ri.return_id=r.id
          JOIN order_items oi ON oi.id=ri.order_item_id
          WHERE r.{return_date_column} BETWEEN ? AND ? AND r.status='Approved'""",
          (from_date+' 00:00:00',to_date+' 23:59:59')).fetchone()[0]
    report=dict(report); report['best_category']=best['category'] if best else '—'; report['returns_total']=returns_total
    if request.args.get('format')=='csv':
        out=io.StringIO(); writer=csv.writer(out); writer.writerow(['Date','Orders','Revenue (paise)'])
        for row in rows: writer.writerow([row['day'],row['orders'],row['revenue']])
        from flask import Response
        return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="pageturner-report-{from_date}-to-{to_date}.csv"'})
    return render_template('reports_range.html',from_date=from_date,to_date=to_date,report=report,rows=rows,error=None)
