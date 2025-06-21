from flask import Flask, render_template, request, redirect, jsonify, session, flash,url_for
import sqlite3
import pandas as pd
import datetime
import os
import uuid

app = Flask(__name__)
app.secret_key = "d2ee6f1f8f67f3dcd27b7f7aa3d33272f6f8a7e8baf2735c88ecb33c3aeb5b12"

DATABASE = 'pharmacy_static_admin.db'


def get_db():
    conn = sqlite3.connect(DATABASE,timeout=10)
    conn.row_factory = sqlite3.Row
    return conn
    
from flask import Flask, request, session, jsonify
import datetime
import uuid
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'


# 🔒 Check license before all requests
@app.before_request
def check_license():
    allowed_paths = ['/static', '/renew', '/login', '/favicon.ico', '/change_password']
    if any(request.path.startswith(p) for p in allowed_paths):
        return

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT end_date FROM license ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row:
        end_date = datetime.datetime.strptime(row[0], "%Y-%m-%d").date()
        today = datetime.date.today()
        if today > end_date:
            return '''
                <h2 style="color:red">⛔ License Expired</h2>
                <p>Please contact developer and enter a new license key below:</p>
                <a href="/renew">🔑 Click here to Renew</a>
            ''', 403

# ✅ License renewal via license key
@app.route("/renew", methods=["GET", "POST"])
def renew_license():
    if request.method == "POST":
        license_key = request.form.get("license_key", "").strip()

        try:
            if not license_key.startswith("KJ-"):
                return "❌ Invalid license key format"

            # Expecting: KJ-2025-07-31
            _, date_part = license_key.split("KJ-", 1)
            expiry = datetime.datetime.strptime(date_part, "%Y-%m-%d").date()

            # ✅ Save to DB
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE license SET end_date = ? WHERE id = 1", (expiry,))
            conn.commit()
            cur.close()
            conn.close()

            return f"✅ License updated successfully until {expiry}"
        except Exception as e:
            return f"❌ Invalid license key: {str(e)}"

    return '''
        <h3>🔐 Renew License</h3>
        <form method="post">
            Enter License Key: <input type="text" name="license_key">
            <button type="submit">Activate</button>
        </form>
    '''


# 🛠️ Optional: change admin password (if still using password-based renewal)
@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, renew_password FROM license ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return "❌ License record not found."

    license_id, current = row

    if request.method == "POST":
        old = request.form.get("old_password", "")
        new = request.form.get("new_password", "")

        if old != current:
            cur.close()
            conn.close()
            return "❌ Old password incorrect"

        cur.execute("UPDATE license SET renew_password = ? WHERE id = ?", (new, license_id))
        conn.commit()
        cur.close()
        conn.close()
        return "✅ Password changed successfully"

    cur.close()
    conn.close()
    return '''
        <form method="post">
            Old Password: <input type="password" name="old_password"><br>
            New Password: <input type="password" name="new_password"><br>
            <button type="submit">Change</button>
        </form>
    '''

# 📦 On startup: create 15-day trial license if not exists
def ensure_license():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM license")
    if cur.fetchone()[0] == 0:
        start = datetime.date.today()
        end = start + datetime.timedelta(days=15)
        cur.execute("INSERT INTO license (start_date, end_date, renew_password) VALUES (?, ?, ?)", 
                    (start, end, 'kjadmin123'))
        conn.commit()
    cur.close()
    conn.close()

ensure_license()



# ---------- NEW START: daily Day_Bill_ID helpers ----------
def get_today_day_bill_id(conn):
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(day_bill_id), 0) + 1 FROM pharmacy_header WHERE date(sale_date) = date('now') AND user_id = ?", (session.get("user_id"),))
    val = cur.fetchone()[0]
    cur.close()
    return val

def get_next_bill_no(conn):
    cur = conn.cursor()
    cur.execute("SELECT MAX(bill_no) FROM pharmacy_header")
    last = cur.fetchone()[0]
    cur.close()
    if last:
        next_seq = int(last[1:]) + 1  # strip “B”
    else:
        next_seq = 1
    return f"B{next_seq:06d}"  # B000001 …

def get_next_day_bill(conn, sale_date, user_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(MAX(day_bill_id), 0) + 1
        FROM pharmacy_header
        WHERE date(sale_date) = date(?)
          AND user_id = ?
    """, (sale_date, user_id))
    val = cur.fetchone()[0]
    cur.close()
    return val
# ---------- NEW END -----------------------------------------

@app.context_processor
def inject_ids():
    conn = get_db()
    ctx = {
        "day_bill_id": get_today_day_bill_id(conn),
        "bill_no": get_next_bill_no(conn)
    }
    conn.close()
    return ctx

def refresh_user_role():
    if "user_id" in session:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT role FROM login WHERE user_id = ?", (session["user_id"],))
        row = cur.fetchone()
        if row:
            db_role = row[0]
            if session.get("role") != db_role:
                session["role"] = db_role  # update the session
        cur.close()
        conn.close()


# ---------- Login & dashboard ----------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT user_id, role FROM login WHERE username=? AND password=?", (username, password))
            user = cur.fetchone()
            cur.close()
            conn.close()

            if user:
                session["user_id"] = user["user_id"]
                session["role"] = user["role"]

                return redirect("/dashboard")
            else:
                flash("❌ Invalid username or password.")
        except Exception as e:
            flash(f"🔥 Database error: {e}")

    return render_template("index.html")


@app.route('/dashboard')
def dashboard():
    if "user_id" not in session:
        flash("⚠️ Please log in to access the dashboard.")
        return redirect('/')
    return render_template('dashboard.html')


# ---------- Master form screen ----------
@app.route('/master')
def master_form():
    if "user_id" not in session:
        flash("⚠️ You must be logged in to access this page.")
        return redirect('/')
    return render_template('master_form.html')

# ---------- SAVE (multiple rows) ----------
@app.route("/master/save", methods=["POST"])
def master_save():
    if "user_id" not in session:
        return "⛔ Unauthorized", 403

    try:
        item_ids = request.form.getlist('item_id')
        item_names = request.form.getlist('item_name')
        batch_nos = request.form.getlist('batch_no')
        expiry_dates = request.form.getlist('expiry_date')
        packs = request.form.getlist('pack')
        available_qtys = request.form.getlist('available_qty')
        buying_prices = request.form.getlist('buying_price')
        mrps = request.form.getlist('mrp')
        selling_prices = request.form.getlist('selling_price')
        areas = request.form.getlist('area')

        rows = zip(item_ids, item_names, batch_nos, expiry_dates, packs,
                   available_qtys, buying_prices, mrps, selling_prices,areas)

        conn = get_db()
        cur = conn.cursor()
        insert_count = 0
        update_count = 0

        for r in rows:
            item_id = r[0]
            item_name = r[1]
            batch_no = r[2]
            expiry_date_str = r[3]
            pack = r[4]
            available_qty = r[5]
            buying_price = r[6]
            mrp = r[7]
            selling_price = r[8]
            area = r[9]

            expiry_date = datetime.datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
            today = datetime.datetime.today().date()
            if expiry_date <= today:
                return f"❌ Expiry date for item '{item_name}' must be a future date.", 400

            if all([item_name, batch_no, expiry_date_str, pack, buying_price, mrp, selling_price]):
                if item_id:
                    cur.execute("""
                        UPDATE master
                        SET item_name = ?, batch_no = ?, expiry_date = ?, pack = ?,
                            available_qty = ?, buying_price = ?, mrp = ?, selling_price = ?,area = ?,
                            is_active = 'Y'
                        WHERE item_id = ?
                    """, (item_name, batch_no, expiry_date_str, pack, available_qty,
                          buying_price, mrp, selling_price,area, item_id))
                    update_count += 1
                else:
                    cur.execute("""
                        INSERT INTO master (item_name, batch_no, expiry_date, pack,
                                            available_qty, buying_price, mrp, selling_price,area, user_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (item_name, batch_no, expiry_date_str, pack, available_qty,
                          buying_price, mrp, selling_price,area, session.get("user_id")))
                    insert_count += 1

        conn.commit()
        return f"✅ {insert_count} item(s) inserted, {update_count} item(s) updated successfully."

    except Exception as e:
        return f"❌ Save Error: {e}", 500

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


@app.route('/master/delete/<item_id>', methods=['POST'])
def delete_item(item_id):
    if "user_id" not in session:
        return "⛔ Unauthorized", 403
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE master SET is_active = 'N' WHERE item_id = ?", (item_id,))
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Item {item_id} deleted successfully."
    except Exception as e:
        return f"❌ Delete failed: {e}", 500

# ---------- SEARCH (simple) ----------
@app.route('/master/search')
def master_search():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 403
    refresh_user_role()
    q = request.args.get('q', '').upper()
    conn = get_db()
    cur = conn.cursor()

    user_id = session.get("user_id")
    role = session.get("role", "")  # more reliable than just 'is_admin'

    base_sql = """
        SELECT item_id, item_name, batch_no, expiry_date, pack,
               available_qty, buying_price, mrp, selling_price, is_active,area
        FROM master
        WHERE UPPER(item_name) LIKE ?
    """
    params = [q + '%']

    # ✅ Only apply user filter if not admin
    if role != "admin":
        base_sql += " AND user_id = ?"
        params.append(user_id)

    cur.execute(base_sql, params)
    rows = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(rows)


# ---------- UPLOAD EXCEL ----------
@app.route('/master/upload', methods=['POST'])
def master_upload():
    if "user_id" not in session:
        return "⛔ Unauthorized", 403

    try:
        # Get the uploaded file
        file = request.files.get('excel_file')
        if not file:
            return "❌ No file uploaded", 400

        # Read Excel file
        try:
            df = pd.read_excel(file)
        except Exception as e:
            return f"❌ Failed to read Excel file: {e}", 400

        # Ensure required columns exist
        required_columns = {
            "item_name", "batch_no", "expiry_date", "pack",
            "available_qty", "buying_price", "mrp", "selling_price"
        }
        actual_columns = set(col.lower() for col in df.columns)

        if not required_columns.issubset(actual_columns):
            return "❌ Invalid Excel format. Required columns: " + ", ".join(required_columns), 400

        conn = get_db()
        cur = conn.cursor()

        inserted = 0
        skipped = []

        for _, row in df.iterrows():
            try:
                # Convert and validate fields
                item_name = str(row.item_name).strip()
                batch_no = str(row.batch_no).strip()
                expiry_date = (
                    row.expiry_date.date()
                    if isinstance(row.expiry_date, pd.Timestamp)
                    else datetime.datetime.strptime(str(row.expiry_date), "%Y-%m-%d").date()
                )
                today = datetime.date.today()

                if expiry_date <= today:
                    skipped.append(f"{item_name} (expired)")
                    continue

                pack = str(row.pack)
                available_qty = int(row.available_qty)
                buying_price = float(row.buying_price)
                mrp = float(row.mrp)
                selling_price = float(row.selling_price)

                if available_qty <= 0:
                    skipped.append(f"{item_name} (0 quantity)")
                    continue

                # Insert row
                cur.execute("""
                    INSERT INTO master (
                        item_name, batch_no, expiry_date, pack,
                        available_qty, buying_price, mrp, selling_price, user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item_name, batch_no, expiry_date, pack,
                    available_qty, buying_price, mrp, selling_price,
                    session.get("user_id")
                ))

                inserted += 1

            except sqlite3.IntegrityError:
                skipped.append(f"{row.item_name} / {row.batch_no} (duplicate)")
            except Exception as e:
                conn.rollback()
                cur.close()
                conn.close()
                return f"❌ Upload failed on item '{row.get('item_name', '')}': {e}", 500

        conn.commit()
        cur.close()
        conn.close()

        if skipped:
            return (
                f"✅ Uploaded {inserted} row(s). "
                f"❌ Skipped {len(skipped)}: " + ", ".join(skipped)
            )
        else:
            return f"✅ All {inserted} row(s) uploaded successfully!"

    except Exception as e:
        return f"❌ Upload error: {e}", 500


@app.route('/pharmacy')
def pharmacy_form():
    if "user_id" not in session:
        flash("⛔ Please log in to access the pharmacy page.")
        return redirect('/')
    return render_template("transaction_form.html", datetime=datetime.datetime)

# -------- SEARCH ITEMS ----------
@app.route('/pharmacy/search_items')
def search_items():
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401
    refresh_user_role()
    q = request.args.get('q', '').upper()
    user_id = session.get('user_id')
    is_admin = session.get('role') == 'admin'

    conn = get_db()
    cur = conn.cursor()

    sql = """
        SELECT item_id,item_name, batch_no,
               expiry_date,
               pack, available_qty, mrp, selling_price
        FROM master
        WHERE UPPER(item_name) LIKE ? AND date(expiry_date) >= date('now') AND COALESCE(is_active, 'Y') = 'Y'
    """

    params = [q + "%"]

    if not is_admin:
        sql += " AND user_id = ?"
        params.append(user_id)

    sql += " LIMIT 20"

    try:
        cur.execute(sql, params)
        rows = [
            dict(zip([d[0] for d in cur.description], r))
            for r in cur.fetchall()
        ]
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": f"DB error: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/pharmacy/search_bills')
def search_bills():
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401
    refresh_user_role()
    q = request.args.get('q', '').upper()
    user_id = session.get("user_id")
    is_admin = session.get("role") == "admin"

    conn = get_db()
    cur = conn.cursor()

    # Base SQL query
    base_sql = """
        SELECT bill_no,
               day_bill_id,
               sale_date AS sale_date,
               customer_name
        FROM pharmacy_header
        WHERE (UPPER(customer_name) LIKE ? OR sale_date LIKE ?)
    """
    params = [q + '%', q + '%']

    if not is_admin:
        base_sql += " AND user_id = ?"
        params.append(user_id)

    base_sql += " ORDER BY sale_date DESC, day_bill_id DESC LIMIT 20"

    try:
        cur.execute(base_sql, params)
        rows = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": f"DB error: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/pharmacy/get_bill')
def get_bill():
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401
    bill_no = request.args.get('bill_no')
    conn = get_db()
    cur = conn.cursor()

    # Header
    cur.execute("""
        SELECT day_bill_id, bill_no, sale_date, customer_name,
               doctor_name, prescription_ref, payment_type,
               total_price, discount_percent, net_total, remarks,mrno, visit_type
        FROM pharmacy_header WHERE bill_no = ?
    """, (bill_no,))
    hdr_row = cur.fetchone()
    hdr = dict(hdr_row) if hdr_row else {}

    # Items
    cur.execute("""
        SELECT m.item_name, i.batch_no, i.expiry_date,
               i.pack, i.available_qty, i.mrp, i.net_price, i.required_qty, i.price,
               i.new_avl_qty
        FROM pharmacy_items i join master m ON i.item_id = m.item_id WHERE bill_no = ?
    """, (bill_no,))
    items = [dict(row) for row in cur.fetchall()]
    
    cur.execute("SELECT COUNT(*) FROM returns_header WHERE bill_no = ?", (bill_no,))
    return_count = cur.fetchone()[0]
    has_return = return_count > 0

    cur.close()
    conn.close()
    return jsonify({'header': hdr, 'items': items,'has_return': has_return})

@app.route('/pharmacy/print_bill')
def print_bill():
    if "user_id" not in session:
        return redirect('/')
    
    bill_no = request.args.get('bill_no', '').strip()
    if not bill_no:
        return "❌ bill_no is required", 400
        
    bill_no = request.args.get('bill_no')
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM pharmacy_header WHERE bill_no = ?", (bill_no,))
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        return "❌ No bill found for this bill number.", 404
    header = dict(row)

    cur.execute("""
        SELECT m.item_name, i.batch_no, i.expiry_date, i.pack,
               i.required_qty, i.net_price, i.price
        FROM pharmacy_items i join  master m ON i.item_id = m.item_id
        WHERE bill_no = ?
    """, (bill_no,))
    items = [dict(r) for r in cur.fetchall()]

    cur.close()
    conn.close()
    return render_template("print_receipt.html", hdr=header, items=items)

@app.route('/save_pharmacy_item', methods=['POST'])
def save_pharmacy_item():
    if "user_id" not in session:
        return "⛔ Unauthorized", 401
    try:
        conn = get_db()
        cur = conn.cursor()
        item_ids = request.form.getlist('item_id')
        required_qtys = request.form.getlist('required_qty')

        for i in range(len(item_ids)):
            item_id = item_ids[i]
            required_qty = int(required_qtys[i])

            cur.execute("SELECT available_qty FROM master WHERE item_id = ?", (item_id,))
            result = cur.fetchone()
            if not result:
                cur.close()
                conn.close()
                return f"❌ Item with ID {item_id} not found in master", 400
            available_qty = result["available_qty"]

            if required_qty < 1:
                cur.close()
                conn.close()
                return f"❌ Quantity must be at least 1 for item {item_id}", 400
            if required_qty > available_qty:
                cur.close()
                conn.close()
                return f"❌ Entered quantity exceeds available stock for item {item_id}", 400

            cur.execute("INSERT INTO pharmacy_items (item_id, required_qty) VALUES (?, ?)", (item_id, required_qty))
            cur.execute("UPDATE master SET available_qty = available_qty - ? WHERE item_id = ?", (required_qty, item_id))

        conn.commit()
        cur.close()
        conn.close()
        return "✅ Pharmacy items saved successfully"
    except Exception as e:
        return f"❌ Error: {str(e)}", 500


@app.route('/pharmacy/reports', methods=['GET', 'POST'])
def pharmacy_reports():
    conn = get_db()
    cur = conn.cursor()
    refresh_user_role()
    report_type = request.form.get('report_type', 'daily')

    today = datetime.date.today()  # ✅ this should work

    if report_type == 'daily':
        from_date = to_date = today
    elif report_type == 'weekly':
        from_date = today - datetime.timedelta(days=7)
        to_date = today
    elif report_type == 'monthly':
        from_date = today.replace(day=1)
        to_date = today
    elif report_type == 'quarterly':
        from_date = today - datetime.timedelta(days=90)
        to_date = today

    user_id = session.get('user_id')
    is_admin = session.get('role') == 'admin'

    base_sql = """
        SELECT day_bill_id, sale_date, customer_name, COALESCE(net_total, 0) as net_total
        FROM pharmacy_header
        WHERE date(sale_date) BETWEEN ? AND ?
    """
    params = [from_date, to_date]

    if not is_admin:
        base_sql += " AND user_id = ?"
        params.append(user_id)

    base_sql += " ORDER BY sale_date DESC, day_bill_id ASC"
    cur.execute(base_sql, params)
    rows = cur.fetchall()
    total_billing = sum((row["net_total"] if "net_total" in row.keys() else 0) for row in rows)

    return render_template('pharmacy_reports.html',
                           report_data=rows,
                           total_billing=total_billing,
                           report_type=report_type)


@app.route("/stock-grid")
def stock_grid():
    connection = get_db()
    cursor = connection.cursor()
    refresh_user_role()
    user_id = session.get("user_id")
    is_admin = session.get("role") == "admin"

    sql = "SELECT item_name, available_qty, expiry_date FROM master WHERE available_qty > 0"
    params = ()
    if not is_admin:
        sql += " AND user_id = ?"
        params = (user_id,)

    cursor.execute(sql, params)

    red_items = []
    yellow_items = []
    blue_items = []
    green_items = []

    expiring_1_month = []
    expiring_3_months = []
    expired_items = []

    today = datetime.date.today()
    one_month_later = today + datetime.timedelta(days=30)
    three_months_later = today + datetime.timedelta(days=90)

    for row in cursor.fetchall():
        name = row["item_name"]
        qty = int(row["available_qty"] or 0)
        expiry = row["expiry_date"]

        # Stock level color
        if qty < 25:
            red_items.append({"item_name": name, "quantity": qty})
        elif qty < 50:
            yellow_items.append({"item_name": name, "quantity": qty})
        elif qty < 75:
            blue_items.append({"item_name": name, "quantity": qty})
        elif qty < 100:
            green_items.append({"item_name": name, "quantity": qty})

        # Expiry check
        if expiry:
            expiry_date = datetime.datetime.strptime(expiry, "%Y-%m-%d").date()
            if expiry_date < today:
                expired_items.append({"item_name": name, "expiry_date": expiry})
            elif today <= expiry_date <= one_month_later:
                expiring_1_month.append({"item_name": name, "expiry_date": expiry})
            elif today <= expiry_date <= three_months_later:
                expiring_3_months.append({"item_name": name, "expiry_date": expiry})

    cursor.close()
    connection.close()

    return render_template(
        "stock_grid.html",
        red_items=red_items,
        yellow_items=yellow_items,
        blue_items=blue_items,
        green_items=green_items,
        expiring_1_month=expiring_1_month,
        expiring_3_months=expiring_3_months,
        expired_items= expired_items
        
    )


@app.route('/pharmacy/save', methods=['POST'])
def save_pharmacy():
    try:
        f = request.form
        conn = get_db()
        cur = conn.cursor()
        bill_no = f['bill_no']
        print("[DEBUG] Saving bill_no:", bill_no)

        # Duplicate check
        cur.execute("""
            SELECT COUNT(*) FROM pharmacy_header
            WHERE customer_name = ? AND sale_date = ? AND prescription_ref = ?
        """, (f['customer_name'], f['sale_date'], f['prescription_ref']))
        if cur.fetchone()[0] > 0:
            return f"Duplicate bill for {f['customer_name']} on {f['sale_date']}"

        # Insert header
        try:
            cur.execute("""
                INSERT INTO pharmacy_header (
                    bill_no, sale_date, customer_name, doctor_name, prescription_ref,
                    payment_type, total_price, discount_percent, net_total, remarks, user_id,mrno,visit_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?,?)
            """, (
                bill_no, f['sale_date'], f['customer_name'], f['doctor_name'], f['prescription_ref'],
                f['payment_type'], f['total_price'], f['discount_percent'], f['net_total'], f['remarks'],
                session.get("user_id"),f['mrno'],f['visit_type']
            ))
            print("[DEBUG] Header insert done.")
        except Exception as e:
            print(f"[ERROR] Header insert failed: {e}")
            return f"❌ Save failed: Header insert failed for bill_no {bill_no}", 500

        # Confirm header is inserted
        cur.execute("SELECT bill_no FROM pharmacy_header WHERE bill_no = ?", (bill_no,))
        if not cur.fetchone():
            print("[ERROR] Header not found after insert.")
            return f"❌ Save failed: Header not saved for bill_no {bill_no}", 500

        # Set Day-bill-ID
        next_day_bill = get_next_day_bill(conn, f['sale_date'], session.get("user_id"))
        cur.execute("""
            UPDATE pharmacy_header
            SET day_bill_id = ?
            WHERE bill_no = ?
        """, (next_day_bill, bill_no))
        print("[DEBUG] Day bill ID updated:", next_day_bill)

        # Insert item rows
        rows = zip(
            f.getlist('item_id'), f.getlist('batch_no'), f.getlist('expiry_date'),
            f.getlist('pack'), f.getlist('available_qty'), f.getlist('mrp'),
            f.getlist('net_price'), f.getlist('required_qty'), f.getlist('price'),
            f.getlist('new_avl_qty')
        )
        inserted_items = 0
        for r in rows:
            item_id = r[0]
            required_qty = r[7]

            if not required_qty or int(required_qty) <= 0:
                return f"❌ Quantity must be greater than 0 for item", 400

            if all(r):
                cur.execute("""
                    INSERT INTO pharmacy_items
                      (bill_no, item_id, batch_no, expiry_date, pack, available_qty,
                       mrp, net_price, required_qty, price, new_avl_qty)
                    VALUES
                      (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (bill_no, r[0], r[1], r[2], r[3], r[4],
                      r[5], r[6], r[7], r[8], r[9]))
                cur.execute("""
                    UPDATE master
                    SET available_qty = ?
                    WHERE item_id = ? AND batch_no = ?
                """, (r[9], r[0], r[1]))
                inserted_items += 1

        conn.commit()
        print(f"[DEBUG] Insert complete: {inserted_items} items for bill {bill_no}")
        return f"✅ Bill {bill_no} saved!"
    except Exception as e:
        print("[ERROR] Save failed:", e)
        return f"❌ Save failed: {e}", 500
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

@app.route("/patient", methods=["GET", "POST"])
def patient_registration():
    if "user_id" not in session:
        return redirect(url_for("login"))

    mr_no = request.args.get("mr_no", "")
    form_data = {}
    saved = False

    if request.method == "POST":
        # Save new patient
        full_name = request.form.get("full_name", "")
        age = request.form.get("age", "")
        gender = request.form.get("gender", "")
        phone = request.form.get("phone", "")
        marital_status = request.form.get("marital_status", "")
        address = request.form.get("address", "")
        patient_type = request.form.get("patient_type", "")
        doctor_to_visit = request.form.get("doctor_to_visit", "")
        created_by = session["user_id"]
        registration_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO patients 
                (full_name, age, gender, phone, marital_status, address, patient_type, doctor_to_visit, registration_date, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (full_name, age, gender, phone, marital_status, address, patient_type, doctor_to_visit, registration_date, created_by))
            mr_no = cur.lastrowid
            con.commit()
            cur.close()

        flash("✅ Patient saved successfully.", "success")
        return redirect(url_for("patient_registration", mr_no=mr_no))

    # GET: Load data only if mr_no param exists
    if mr_no:
        with get_db() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM patients WHERE patient_id = ?", (mr_no,))
            patient = cur.fetchone()
            cur.close() 
            if patient:
                form_data = dict(patient)
                saved = True

    # ✅ If no mr_no, form_data stays empty
    return render_template("patient_registration.html", mr_no=mr_no, form_data=form_data, saved=saved)




@app.route("/patient/search", methods=["POST"])
def patient_search():
    if "user_id" not in session:
        return redirect(url_for("login"))

    search_query = request.form.get("search_query", "").strip()
    with get_db() as con:
        cur = con.cursor()
        if search_query:
            cur.execute("""
                SELECT patient_id, full_name, phone 
                FROM patients 
                WHERE full_name LIKE ? OR phone LIKE ? OR patient_id LIKE ?
            """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
        else:
            cur.execute("""
                SELECT patient_id, full_name, phone 
                FROM patients
                ORDER BY patient_id DESC LIMIT 50
            """)
        rows = cur.fetchall()

    table_html = ""
    for row in rows:
        table_html += f"""
        <tr onclick="selectPatient('{row['patient_id']}')">
          <td>{row['patient_id']}</td>
          <td>{row['full_name']}</td>
          <td>{row['phone']}</td>
        </tr>
        """
        
    return table_html

@app.route('/patient/print/<int:patient_id>')
def print_patient(patient_id):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    row = cur.fetchone()
    if not row:
        return "Patient not found", 404
    patient = dict(row)
    return render_template("patient_print.html", patient=patient)
    
@app.route('/returns', methods=['GET'])
def show_returns_form():
    return render_template('returns_form.html')
    
def generate_next_return_no():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT return_no FROM returns_header ORDER BY return_no DESC LIMIT 1")
        last = cur.fetchone()
        if last and last["return_no"]:
            num_part = int(last["return_no"][1:])  # remove leading 'R'
            new_num = num_part + 1
        else:
            new_num = 1
        return "R" + str(new_num).zfill(6)

@app.route('/returns', methods=['POST'])
def save_returns():
    if "user_id" not in session:
        return "❌ Unauthorized", 401

    # 🟩 Generate new return_no
    return_no = generate_next_return_no()

    # 🟩 Read header fields
    bill_no = request.form.get('bill_no')
    reason = request.form.get('reason')
    total_amount = request.form.get('total_amount')
    sale_date = request.form.get('sale_date')
    day_bill_id = request.form.get('day_bill_id')
    customer_name = request.form.get('customer_name')
    doctor_name = request.form.get('doctor_name')
    prescription_ref = request.form.get('prescription_ref')
    payment_type = request.form.get('payment_type')
    discount_percent = request.form.get('discount_percent')

    # 🟩 Read grid data
    item_ids = request.form.getlist('item_id[]')
    item_names = request.form.getlist('item_name[]')
    batch_nos = request.form.getlist('batch_no[]')
    expiry_dates = request.form.getlist('expiry_date[]')
    packs = request.form.getlist('pack[]')
    available_qtys = request.form.getlist('available_qty[]')
    mrps = request.form.getlist('mrp[]')
    net_prices = request.form.getlist('net_price[]')
    sold_qtys = request.form.getlist('sold_qty[]')
    return_qtys = request.form.getlist('return_qty[]')
    return_amounts = request.form.getlist('return_amount[]')

    if len(item_ids) != len(return_qtys) or len(item_ids) != len(return_amounts):
        return "❌ Data mismatch! Please refresh the page.", 400
    
    for i in range(min(len(item_ids), len(return_qtys))):
        qty = int(return_qtys[i])
        if qty <= 0:
            return "❌ Return Qty must be greater than 0.", 400 
    if not day_bill_id or not customer_name:
        return '❌ Day Bill No and Patient Name are mandatory', 400


    with get_db() as con:
        cur = con.cursor()
        # 🟩 Save returns_header
        cur.execute("""
            INSERT INTO returns_header
            (return_no, bill_no, return_date, reason, total_amount, sale_date,
             day_bill_id, customer_name, doctor_name, prescription_ref, payment_type, discount_percent,created_by)
            VALUES (?, ?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?,?)
        """, (
            return_no, bill_no, reason, total_amount, sale_date, day_bill_id,
            customer_name, doctor_name, prescription_ref, payment_type,discount_percent,
            session["user_id"]
        ))

        # 🟩 Save returns_items
        for i in range(len(item_ids)):
            qty = return_qtys[i]
            amount = return_amounts[i]
            if not qty or int(qty) == 0:
                continue
            cur.execute("""
                INSERT INTO returns_items
                (return_no, item_id, item_name, batch_no, expiry_date, pack,
                 available_qty, mrp, net_price, sold_qty, return_qty, return_amount, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                return_no,
                item_ids[i],
                item_names[i],
                batch_nos[i],
                expiry_dates[i],
                packs[i],
                available_qtys[i],
                mrps[i],
                net_prices[i],
                sold_qtys[i],
                qty,
                amount,
                session["user_id"]
            ))
            
            cur.execute("""
                UPDATE master
                SET available_qty = available_qty + ?
                WHERE item_id = ?
            """, (qty, item_ids[i]))
            
        con.commit()
        cur.close()

    return f"✅ Return saved successfully! Return No: {return_no}"

@app.route('/returns/fetch_bill', methods=['GET'])
def fetch_bill():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    bill_no = request.args.get('bill_no', '').strip()
    if not bill_no:
        return jsonify({"error": "❌ Bill number is required."}), 400

    try:
        with get_db() as con:
            cur = con.cursor()

            # 🛑 Check if return already exists
            cur.execute("SELECT 1 FROM returns_header WHERE bill_no = ?", (bill_no,))
            if cur.fetchone():
                return jsonify({"error": "❌ Return already done for this bill."})

            # ✅ Fetch header
            cur.execute("""
                SELECT sale_date, day_bill_id, customer_name, doctor_name, 
                       prescription_ref, payment_type, discount_percent
                FROM pharmacy_header
                WHERE bill_no = ?
            """, (bill_no,))
            header_row = cur.fetchone()
            if not header_row:
                return jsonify({"error": "❌ Bill not found."}), 404

            header = dict(header_row)

            # ✅ Fetch item details with JOIN to master
            cur.execute("""
                SELECT i.item_id, m.item_name, i.batch_no, i.expiry_date, 
                       i.pack, i.available_qty, i.mrp, i.net_price, i.required_qty
                FROM pharmacy_items i
                JOIN master m ON i.item_id = m.item_id
                WHERE i.bill_no = ?
            """, (bill_no,))
            items = [dict(row) for row in cur.fetchall()]

        return jsonify({"header": header, "items": items})

    except Exception as e:
        return jsonify({"error": f"❌ Internal Server Error: {str(e)}"}), 500


@app.route('/returns/search')
def search_returns():
    q = request.args.get('q', '')
    with get_db() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT return_no, customer_name, return_date
            FROM returns_header
            WHERE return_no LIKE ? OR customer_name LIKE ?
            ORDER BY return_date DESC,return_no desc
            LIMIT 20
        """, ('%' + q + '%', '%' + q + '%'))
        rows = [dict(row) for row in cur.fetchall()]
    return jsonify(rows)

@app.route('/returns/get_return')
def get_return():
    return_no = request.args.get('return_no', '')
    with get_db() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT * FROM returns_header WHERE return_no = ?
        """, (return_no,))
        header_row = cur.fetchone()
        header = dict(header_row) if header_row else {}

        cur.execute("""
            SELECT * FROM returns_items WHERE return_no = ?
        """, (return_no,))
        items = [dict(row) for row in cur.fetchall()]

    return jsonify({"header": header, "items": items})


@app.route('/returns/print')
def print_return():
    return_no = request.args.get('return_no', '')
    with get_db() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT * FROM returns_header WHERE return_no = ?
        """, (return_no,))
        header = dict(cur.fetchone())

        cur.execute("""
            SELECT * FROM returns_items WHERE return_no = ?
        """, (return_no,))
        items = [dict(row) for row in cur.fetchall()]

    return render_template('print_return.html', header=header, items=items)

@app.route('/stock_adjustment', methods=['GET'])
def show_adjust_form():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT upper(username) as username FROM login WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        username = row["username"] if row and "username" in row.keys() else "Unknown"


    return render_template('Stock Adjustment.html',
                           username=username,
                           datetime=datetime)

    
    
@app.route('/adjust_stock', methods=['POST'])
def save_adjustment():
    if "user_id" not in session:
        return "❌ Unauthorized", 401

    adjustment_date = request.form.get('adjustment_date')
    item_name = request.form.get('item_name')
    batch_no = request.form.get('batch_no')
    expiry_date = request.form.get('expiry_date')
    pack = request.form.get('pack')
    available_qty = request.form.get('available_qty')
    adjust_qty = int(request.form.get('adjust_qty'))
    reason = request.form.get('reason')
    item_id = request.form.get('item_id')
    
    if adjust_qty == 0:
            return jsonify({"error": "Adjustment quantity cannot be zero"}), 400

    with get_db() as con:
        cur = con.cursor()

        # Insert adjustment record
        cur.execute("""
            INSERT INTO stock_adjustments
            (adjustment_date, item_name, batch_no, expiry_date, pack, available_qty, adjust_qty, reason, adjusted_by,item_id)
            VALUES (date('now'), ?, ?, ?, ?, ?, ?, ?, ?,?)
        """, (item_name, batch_no, expiry_date, pack, available_qty, adjust_qty, reason, session["user_id"],item_id))

        # Update master stock
        cur.execute("""
            UPDATE master
            SET available_qty = available_qty + ?
            WHERE item_id = ?
        """, (adjust_qty, item_id))

        con.commit()

    return "✅ Stock adjusted successfully!"

@app.route('/adjust_stock/search')
def search_adjustments():
    q = request.args.get('q', '')
    with get_db() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT id, adjustment_date, item_name, reason
            FROM stock_adjustments
            WHERE item_name LIKE ? OR reason LIKE ?
            ORDER BY adjustment_date DESC
            LIMIT 20
        """, ('%' + q + '%', '%' + q + '%'))
        rows = [dict(row) for row in cur.fetchall()]
    return jsonify(rows)

@app.route('/adjust_stock/get_adjustment')
def get_adjustment():
    adj_id = request.args.get('id')
    with get_db() as con:
        cur = con.cursor()
        # Join with users table to get the username
        cur.execute(""" select
             sa.id,
             sa.adjustment_date,
             sa.item_id,
             sa.item_name,
             sa.batch_no,
             sa.expiry_date,
             sa.pack,
             sa.available_qty,
             sa.adjust_qty,
             sa.reason,
             upper(u.username) AS adjusted_by_name
            FROM stock_adjustments sa
            LEFT JOIN Login u ON sa.adjusted_by = u.user_id
            WHERE sa.id = ?
        """, (adj_id,))
        row = cur.fetchone()
        adjustment = dict(row) if row else {}

    return jsonify({'adjustment': adjustment})

@app.route("/pharmacy/search_mrno")
def search_mrno():
    mrno = request.args.get("mrno", "").strip()
    if not mrno:
        return jsonify({"exists": False})

    try:
        mrno_int = int(mrno)
    except ValueError:
        return jsonify({"exists": False})

    with get_db() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT full_name, doctor_to_visit
            FROM patients
            WHERE patient_id = ?
        """, (mrno_int,))
        row = cur.fetchone()
        cur.close()
        if row:
            patient = {
                "full_name": row[0],
                "doctor": row[1]
            }
            return jsonify({"exists": True, "patient": patient})
        else:
            return jsonify({"exists": False})


@app.route("/sales_report", methods=["GET"])
def sales_report():
    if "user_id" not in session:
        return redirect(url_for("login"))

    refresh_user_role()
    is_admin = session.get("role") == "admin"

    if not is_admin:
        return "❌ Access Denied: Only admin can view sales reports"
        
        
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    report_type = request.args.get("report_type")
    print("DEBUG - Received report_type:", report_type)

    # Show only the form if no filters selected yet
    if not from_date or not to_date or not report_type:
        return render_template("sales_report.html", data=None, headers=[], report_type="", from_date="", to_date="")

    connection = get_db()
    cursor = connection.cursor()

    data = []
    headers = []
    query = ""
    params = (from_date, to_date)

    if report_type == "item_sold_qty":
        query = """
            SELECT b.item_name, SUM(a.required_qty) AS total_sold_quantity
            FROM pharmacy_items a
            JOIN master b ON a.item_id = b.item_id
            JOIN pharmacy_header h ON a.bill_no = h.bill_no
            WHERE h.sale_date BETWEEN ? AND ?
            GROUP BY a.item_id
            ORDER BY total_sold_quantity DESC
        """
        headers = ["Item Name", "Total Sold Quantity"]

    elif report_type == "daily_sale":
        query = """
            SELECT h.sale_date, COUNT(*) AS bills,
                   SUM(h.total_price), SUM(h.discount_percent), SUM(h.net_total)
            FROM pharmacy_header h
            WHERE h.sale_date BETWEEN ? AND ?
            GROUP BY h.sale_date
            ORDER BY h.sale_date DESC
        """
        headers = ["Sale Date", "Bills", "Total Price", "Discount %", "Net Total"]

    elif report_type == "item_sold_count":
        query = """
            SELECT b.item_name, COUNT(*) AS number_of_times
            FROM pharmacy_items a
            JOIN master b ON a.item_id = b.item_id
            JOIN pharmacy_header h ON a.bill_no = h.bill_no
            WHERE h.sale_date BETWEEN ? AND ?
            GROUP BY a.item_id
            ORDER BY number_of_times DESC
        """
        headers = ["Item Name", "Number of Times Sold"]

    elif report_type == "item_amount_generated":
        query = """
            SELECT b.item_name, SUM(a.price) AS amount_generated
            FROM pharmacy_items a
            JOIN master b ON a.item_id = b.item_id
            JOIN pharmacy_header h ON a.bill_no = h.bill_no
            WHERE h.sale_date BETWEEN ? AND ?
            GROUP BY a.item_id
            ORDER BY amount_generated DESC
        """
        headers = ["Item Name", "Amount Generated"]

    elif report_type == "most_margin_items":
        query = """
            SELECT m.item_name, m.buying_price, m.selling_price,
                   (m.selling_price - m.buying_price) AS margin_per_unit,
                   SUM(pi.required_qty) AS total_qty_sold,
                   (m.selling_price - m.buying_price) * SUM(pi.required_qty) AS total_margin
            FROM pharmacy_items pi
            JOIN master m ON pi.item_id = m.item_id
            JOIN pharmacy_header h ON pi.bill_no = h.bill_no
            WHERE h.sale_date BETWEEN ? AND ?
            GROUP BY m.item_id
            ORDER BY total_margin DESC
        """
        headers = ["Item Name", "Buying Price", "Selling Price", "Margin/Unit", "Qty Sold", "Total Margin"]

    else:
        cursor.close()
        connection.close()
        return "❌ Invalid report type"

    try:
        cursor.execute(query, params)
        data = cursor.fetchall()
    except Exception as e:
        return f"❌ Error executing report: {e}"
    finally:
        cursor.close()
        connection.close()

    return render_template(
        "sales_report.html",
        data=data,
        headers=headers,
        report_type=report_type,
        from_date=from_date,
        to_date=to_date
    )

if __name__ == '__main__':
    app.run(debug=True)
 
