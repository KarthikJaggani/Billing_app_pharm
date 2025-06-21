import sqlite3

# Create (or connect to) the database
conn = sqlite3.connect("pharmacy_static_admin.db")
cur = conn.cursor()

# Create tables
cur.executescript("""
-- Login table
CREATE TABLE IF NOT EXISTS login (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
);

-- Master table
CREATE TABLE IF NOT EXISTS master (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT,
    batch_no TEXT,
    expiry_date TEXT,
    pack TEXT,
    available_qty INTEGER,
    buying_price REAL,
    mrp REAL,
    selling_price REAL,
    user_id TEXT,
    is_active TEXT DEFAULT 'Y',
    UNIQUE(item_name, batch_no)
);

-- Pharmacy header
CREATE TABLE IF NOT EXISTS pharmacy_header (
    bill_no TEXT PRIMARY KEY,
    sale_date TEXT,
    customer_name TEXT,
    doctor_name TEXT,
    prescription_ref TEXT,
    payment_type TEXT,
    total_price REAL,
    discount_percent REAL,
    net_total REAL,
    remarks TEXT,
    day_bill_id INTEGER,
    user_id TEXT
);

-- Pharmacy items
CREATE TABLE IF NOT EXISTS pharmacy_items (
    item_id INTEGER,
    bill_no TEXT,
    batch_no TEXT,
    expiry_date TEXT,
    pack TEXT,
    available_qty INTEGER,
    mrp REAL,
    net_price REAL,
    required_qty INTEGER,
    price REAL,
    new_avl_qty INTEGER
);

CREATE TABLE IF NOT EXISTS patients( 
             patient_id INTEGER PRIMARY KEY AUTOINCREMENT,  
             full_name TEXT NOT NULL,
             age INTEGER NOT NULL,
             gender TEXT NOT NULL,
             phone TEXT CHECK(length(phone) = 10),
             marital_status TEXT,
             address TEXT NOT NULL,
             patient_type TEXT,
             doctor_to_visit TEXT,
             registration_date TEXT,
             created_by TEXT
        );
        
-- Create unique index on master table
CREATE UNIQUE INDEX IF NOT EXISTS idx_item_batch ON master (item_name, batch_no);


CREATE TABLE IF NOT EXISTS patients( 
             patient_id INTEGER PRIMARY KEY AUTOINCREMENT,  
             full_name TEXT NOT NULL,
             age INTEGER NOT NULL,
             gender TEXT NOT NULL,
             phone TEXT CHECK(length(phone) = 10),
             marital_status TEXT,
             address TEXT NOT NULL,
             patient_type TEXT,
             doctor_to_visit TEXT,
             registration_date TEXT,
             created_by TEXT
            )
-- 🟩 1️⃣ returns_header table
CREATE TABLE IF NOT EXISTS returns_header (
    return_no TEXT PRIMARY KEY,
    bill_no TEXT,
    return_date DATE,
    reason TEXT,
    total_amount REAL,
    sale_date TEXT,
    day_bill_id INTEGER,
    customer_name TEXT,
    doctor_name TEXT,
    prescription_ref TEXT,
    payment_type TEXT,
    created_by TEXT
);

-- 🟩 2️⃣ returns_items table (full grid fields)
CREATE TABLE IF NOT EXISTS returns_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_no TEXT,
    item_id INTEGER,
    item_name TEXT,
    batch_no TEXT,
    expiry_date TEXT,
    pack TEXT,
    available_qty INTEGER,
    mrp REAL,
    net_price REAL,
    sold_qty INTEGER,
    return_qty INTEGER,
    return_amount REAL,
    created_by TEXT,
    FOREIGN KEY (return_no) REFERENCES returns_header(return_no)
);


CREATE TABLE IF NOT EXISTS stock_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adjustment_date DATE,
    item_id INTEGER,
    item_name TEXT,
    batch_no TEXT,
    expiry_date TEXT,
    pack TEXT,
    available_qty INTEGER,
    adjust_qty INTEGER,
    reason TEXT,
    adjusted_by TEXT
);



""")

# Insert default admin user
cur.execute("""
INSERT INTO login (user_id, username, password, role)
VALUES (?, ?, ?, ?)
""", ("1", "admin", "1234", "admin"))



# Save and close
conn.commit()
conn.close()

print("✅ Empty database created with default admin user (admin/1234).")
