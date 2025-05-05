import sqlite3

# Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect('hotel.db')
c = conn.cursor()

# Enable foreign key constraints (important for SQLite)
c.execute("PRAGMA foreign_keys = ON;")

# Create the customers table if it doesn't exist
c.execute('''
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
''')

# Create the dishes table if it doesn't exist
c.execute('''
    CREATE TABLE IF NOT EXISTS dishes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL
    );
''')


# Create the dish_reviews table
c.execute('''
    CREATE TABLE IF NOT EXISTS dish_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        dish_id INTEGER,
        rating INTEGER CHECK(rating BETWEEN 1 AND 5),
        review_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (dish_id) REFERENCES dishes(id)
    );
''')

# Create the dish_ratings table
c.execute('''
    CREATE TABLE IF NOT EXISTS dish_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dish_id INTEGER,
        average_rating FLOAT,
        total_reviews INTEGER,
        FOREIGN KEY (dish_id) REFERENCES dishes(id)
    );
''')

# Commit the changes and close the connection
conn.commit()
conn.close()

print("Customers, dish reviews, and ratings tables created successfully!")
