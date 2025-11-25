import sqlite3

# Connect to database
connection = sqlite3.connect('database.db')

with connection:
    cursor = connection.cursor()

    # 1. DROP OLD TABLES (Resetting the database structure)
    cursor.execute("DROP TABLE IF EXISTS orders")
    cursor.execute("DROP TABLE IF EXISTS customers")

    # 2. CREATE CUSTOMERS TABLE (Added 'address')
    cursor.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT
        );
    """)

    # 3. CREATE ORDERS TABLE (Added 'weight', renamed 'product_name' -> 'details')
    cursor.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            tracking_number TEXT,
            details TEXT,
            weight TEXT,
            status TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        );
    """)

    # --- 4. ADD SAMPLE DATA (Test User) ---

    # Create User: 徐双双
    cursor.execute("INSERT INTO customers (name, phone, address) VALUES (?, ?, ?)",
                   ('徐双双', '13615826555', '秀洲区龙湖春江华庭8号楼1804'))

    # Get the ID of the new user
    customer_id = cursor.lastrowid

    # Add Order 1
    cursor.execute("""
        INSERT INTO orders (customer_id, tracking_number, details, weight, status) 
        VALUES (?, ?, ?, ?, ?)
    """, (customer_id, 'ZB899150368IA', 'LoveShackFancy Holiday All Day Slim Bottle', '4.5 Lb', '处理中'))

    # Add Order 2
    cursor.execute("""
        INSERT INTO orders (customer_id, tracking_number, details, weight, status) 
        VALUES (?, ?, ?, ?, ?)
    """, (customer_id, 'ZB899151946CA', 'LoveShackFancy Holiday Quencher ProTour Ornament Set', '1.2 Lb', '已发货'))

print("✅ Database updated with new columns (Address, Weight, Details)!")