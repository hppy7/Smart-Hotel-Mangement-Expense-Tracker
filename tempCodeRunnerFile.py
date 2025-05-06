from flask import Flask, render_template, request, redirect,url_for
from flask_mail import Mail, Message
import sqlite3
import heapq
import os

app = Flask(__name__)

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'happysohil1234@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
mail = Mail(app)

# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price_per_unit REAL NOT NULL,
            quantity_in_stock REAL NOT NULL,
            threshold REAL DEFAULT 5
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS dishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            cost_price REAL NOT NULL,
            selling_price REAL NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dish_id INTEGER,
            quantity INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS dishes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        ingredients TEXT NOT NULL,
        cost_price REAL NOT NULL,
        selling_price REAL NOT NULL
    )
''')
    # Create the dish_inventory table if it doesn't exist
    c.execute("""
        CREATE TABLE IF NOT EXISTS dish_inventory (
            dish_name TEXT PRIMARY KEY,
            quantity_in_stock INTEGER NOT NULL
        );
    """)


    conn.commit()
    conn.close()

init_db()
@app.route('/')
def index():
    conn = sqlite3.connect('database.db')  # Or switch to hotel.db if needed
    c = conn.cursor()
    c.execute("SELECT id, name, cost_price, selling_price FROM dishes")
    dishes = [
        {'id': row[0], 'name': row[1], 'cost_price': row[2], 'selling_price': row[3]}
        for row in c.fetchall()
    ]
    conn.close()
    return render_template('index.html', dishes=dishes)



@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    conn = sqlite3.connect('database.db', check_same_thread=False)  # or 'hotel.db' if that’s your actual DB
    c = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_or_update':
            name = request.form['name']
            price = float(request.form['price'])
            quantity = float(request.form['quantity'])
            threshold = float(request.form['threshold'])

            # Check if ingredient exists
            c.execute("SELECT id, quantity_in_stock, price_per_unit FROM ingredients WHERE name = ?", (name,))
            existing = c.fetchone()

            if existing:
                # Update quantity and average price
                existing_id, current_qty, current_price = existing
                new_qty = current_qty + quantity
                avg_price = ((current_price * current_qty) + (price * quantity)) / new_qty
                c.execute("""
                    UPDATE ingredients
                    SET quantity_in_stock = ?, price_per_unit = ?, threshold = ?
                    WHERE id = ?
                """, (new_qty, avg_price, threshold, existing_id))
            else:
                # Insert new ingredient
                c.execute("""
                    INSERT INTO ingredients (name, price_per_unit, quantity_in_stock, threshold)
                    VALUES (?, ?, ?, ?)
                """, (name, price, quantity, threshold))

            conn.commit()

        elif action == 'update_price':
            ingredient_name = request.form['ingredient_name']
            new_price = float(request.form['new_price'])

            c.execute("""
                UPDATE ingredients
                SET price_per_unit = ?
                WHERE name = ?
            """, (new_price, ingredient_name))

            conn.commit()

    # Fetch all ingredients
    c.execute("SELECT * FROM ingredients")
    ingredients = c.fetchall()
    conn.close()
    return render_template('inventory.html', ingredients=ingredients)

@app.route('/inventory-alerts')
def inventory_alerts():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        SELECT name, quantity_in_stock, threshold FROM ingredients
        WHERE quantity_in_stock < threshold
    ''')
    alerts = c.fetchall()
    conn.close()

    if alerts:
        alert_lines = [f"{item[0]} - {item[1]} left (threshold: {item[2]})" for item in alerts]
        alert_message = "\n".join(alert_lines)

        msg = Message("\U0001F6A8 Inventory Restock Alert",
                      recipients=["happysohil1234@gmail.com", "bhatsuheem1@gmail.com"])
        msg.body = f"The following items need restocking:\n\n{alert_message}"
        mail.send(msg)

    return render_template('inventory_alerts.html', alerts=alerts)

@app.route('/add-dish', methods=['GET', 'POST'])
def add_dish():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    low_stock_threshold = 5
    low_stock_warnings = []
    error = None

    # Handle dish deletion
    if request.method == 'POST' and request.form.get('action') == 'delete':
        dish_to_delete = request.form.get('dish_to_delete')
        c.execute("DELETE FROM dishes WHERE name = ?", (dish_to_delete,))
        c.execute("DELETE FROM dish_inventory WHERE dish_name = ?", (dish_to_delete,))
        conn.commit()
        conn.close()
        return redirect('/add-dish')

    # Handle dish addition or update
    if request.method == 'POST' and not request.form.get('action'):
        name = request.form['name'].strip()
        ingredients_data = request.form.getlist('ingredient')
        quantities = request.form.getlist('quantity')
        ingredient_map = []
        cost_price = 0
        dish_quantity = int(request.form['dish_quantity'])  # Number of dishes being added

        try:
            # Check if dish already exists
            c.execute("SELECT id, ingredients FROM dishes WHERE name = ?", (name,))
            existing_dish = c.fetchone()

            if existing_dish:
                dish_id, old_ingredients_str = existing_dish
                # Restore stock from old ingredients
                old_ingredients = old_ingredients_str.split(",")
                for item in old_ingredients:
                    ing_name, qty = item.split(":")
                    c.execute("UPDATE ingredients SET quantity_in_stock = quantity_in_stock + ? WHERE name = ?", (float(qty), ing_name))
                # Delete old dish entry
                c.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))

            # Process ingredients and calculate cost price
            for ing, qty in zip(ingredients_data, quantities):
                ing = ing.strip()
                qty = qty.strip()
                if not ing or not qty:
                    continue  # Skip if quantity is empty or not provided
                try:
                    qty = float(qty)
                except ValueError:
                    raise ValueError(f"Invalid quantity for ingredient '{ing}'")

                c.execute("SELECT price_per_unit, quantity_in_stock FROM ingredients WHERE name = ?", (ing,))
                row = c.fetchone()
                if not row:
                    raise ValueError(f"Ingredient '{ing}' does not exist in inventory")

                price, stock_qty = row
                if stock_qty < qty:
                    raise ValueError(f"Not enough stock for {ing} (available: {stock_qty}, needed: {qty})")

                cost_price += price * qty
                ingredient_map.append(f"{ing}:{qty}")

                if stock_qty < low_stock_threshold:
                    low_stock_warnings.append(f"⚠️ {ing} stock is low: {stock_qty} units left")

            if not ingredient_map:
                raise ValueError("Please enter quantity for at least one ingredient.")

            selling_price = round(cost_price * 1.15, 2)

            # Insert/Update dish in the dishes table
            c.execute("INSERT INTO dishes (name, ingredients, cost_price, selling_price) VALUES (?, ?, ?, ?)",
                      (name, ",".join(ingredient_map), cost_price, selling_price))

            # Insert/Update dish inventory
            c.execute("INSERT OR REPLACE INTO dish_inventory (dish_name, quantity_in_stock) VALUES (?, ?)",
                      (name, dish_quantity))

            # Deduct ingredient stock
            for item in ingredient_map:
                ing, qty = item.split(":")
                c.execute("UPDATE ingredients SET quantity_in_stock = quantity_in_stock - ? WHERE name = ?", (float(qty), ing))

            conn.commit()

        except ValueError as ve:
            error = str(ve)

    # Always reload ingredients and dishes after any POST or on GET
    c.execute("SELECT name, quantity_in_stock FROM ingredients")
    ingredient_list = c.fetchall()

    c.execute("SELECT name FROM dishes")
    existing_dishes = [row[0] for row in c.fetchall()]

    # Check for low stock warnings
    low_stock_warnings = []
    for name, stock_qty in ingredient_list:
        if stock_qty < low_stock_threshold:
            low_stock_warnings.append(f"⚠️ {name} stock is low: {stock_qty} units left")

    conn.close()

    return render_template('add_dish.html',
                           ingredient_list=ingredient_list,  # name + stock qty
                           warnings=low_stock_warnings,
                           error=error,
                           existing_dishes=existing_dishes)




@app.route('/sales')
def sales():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        SELECT d.id, d.name, COUNT(s.id) as total_sales
        FROM sales s
        JOIN dishes d ON s.dish_id = d.id
        GROUP BY s.dish_id
    ''')
    results = c.fetchall()

    priority_queue = []
    profit_loss_data = []

    for dish in results:
        dish_id, dish_name, total_sales = dish
        c.execute("SELECT cost_price, selling_price FROM dishes WHERE id = ?", (dish_id,))
        cost_price, selling_price = c.fetchone()
        total_revenue = total_sales * selling_price
        total_cost = total_sales * cost_price
        profit = total_revenue - total_cost
        loss = max(0, -profit)

        profit_loss_data.append({
            'name': dish_name,
            'total_sales': total_sales,
            'cost_price': cost_price,
            'selling_price': selling_price,
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'profit': profit,
            'loss': loss
        })

        heapq.heappush(priority_queue, (-profit, dish_name, total_sales, profit))

    highest_profit_dish = None
    if priority_queue:
        top = heapq.heappop(priority_queue)
        highest_profit_dish = {
            'name': top[1],
            'total_sales': top[2],
            'total_profit': top[3]
        }

    c.execute('''
        SELECT d.name, COUNT(s.id) AS total_sales
        FROM sales s
        JOIN dishes d ON s.dish_id = d.id
        GROUP BY s.dish_id
        ORDER BY total_sales DESC
        LIMIT 20
    ''')
    top_dishes = c.fetchall()
    conn.close()

    return render_template(
        'sales.html',
        profit_loss_data=profit_loss_data,
        highest_profit_dish=highest_profit_dish,
        top_dishes=top_dishes
    )

@app.route('/sell-dish', methods=['GET', 'POST'])
def sell_dish():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    error = None

    if request.method == 'POST':
        dish_id = int(request.form['dish_id'])
        quantity = int(request.form['quantity'])

        # Fetch dish ingredients
        c.execute("SELECT ingredients FROM dishes WHERE id = ?", (dish_id,))
        result = c.fetchone()
        if not result:
            error = "Dish not found."
        else:
            ing_string = result[0]
            ingredients = ing_string.split(',')

            # Check if all ingredients are available in required quantity
            for item in ingredients:
                name, qty = item.split(':')
                qty = float(qty) * quantity
                c.execute("SELECT quantity_in_stock FROM ingredients WHERE name = ?", (name,))
                stock = c.fetchone()
                if not stock or stock[0] < qty:
                    error = f"Not enough stock for {name}. Required: {qty}, Available: {stock[0] if stock else 0}"
                    break

            # If no errors, deduct and insert sales
            if not error:
                for item in ingredients:
                    name, qty = item.split(':')
                    qty = float(qty) * quantity
                    c.execute("UPDATE ingredients SET quantity_in_stock = quantity_in_stock - ? WHERE name = ?", (qty, name))

                for _ in range(quantity):
                    c.execute("INSERT INTO sales (dish_id, quantity) VALUES (?, ?)", (dish_id, 1))

                conn.commit()
                conn.close()
                return redirect('/sales')

    # Always fetch dishes before rendering the page
    c.execute("SELECT id, name FROM dishes")
    dishes = c.fetchall()
    conn.close()
    return render_template('sell.html', dishes=dishes, error=error)

@app.route('/delete-ingredient/<int:ingredient_id>', methods=['GET', 'POST'])
def delete_ingredient(ingredient_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Delete ingredient from the ingredients table
    c.execute("DELETE FROM ingredients WHERE id = ?", (ingredient_id,))
    conn.commit()
    
    conn.close()
    
    return redirect('/inventory')  # Redirect to the inventory page after deletion
@app.route('/dish-availability')
def dish_availability():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Retrieve all dishes and their ingredients
    c.execute("SELECT id, name, ingredients FROM dishes")
    dishes = c.fetchall()

    availability_data = []

    for dish_id, name, ing_string in dishes:
        ingredients = ing_string.split(',')
        min_possible = float('inf')

        for item in ingredients:
            if ':' not in item:
                continue  # Skip malformed ingredient strings

            ing_name, qty_str = item.split(':', 1)
            ing_name = ing_name.strip()
            try:
                qty = float(qty_str.strip())
            except ValueError:
                min_possible = 0
                break

            if qty <= 0:
                continue  # Skip zero or negative quantity ingredients

            # Check stock quantity for the current ingredient
            c.execute("SELECT quantity_in_stock FROM ingredients WHERE name = ?", (ing_name,))
            result = c.fetchone()
            if result:
                stock_qty = result[0]
                if stock_qty < qty:
                    min_possible = 0  # Not enough stock
                    break
                else:
                    possible = stock_qty // qty
                    min_possible = min(min_possible, possible)
            else:
                min_possible = 0  # Ingredient missing
                break

        if min_possible <= 0 or min_possible == float('inf'):
            availability_data.append((name, 'Unavailable'))
        else:
            availability_data.append((name, int(min_possible)))

    conn.close()
    return render_template('dish_availability.html', availability=availability_data)

@app.route('/dish/<int:dish_id>', methods=['GET', 'POST'])
def dish_details(dish_id):
    conn = sqlite3.connect('hotel.db')
    c = conn.cursor()

    # Get the dish details
    c.execute('SELECT name, description FROM dishes WHERE id = ?', (dish_id,))
    dish = c.fetchone()

    # Get reviews for this dish
    c.execute('SELECT * FROM dish_reviews WHERE dish_id = ?', (dish_id,))
    reviews = c.fetchall()

    # Get the average rating for the dish
    c.execute('SELECT average_rating, total_reviews FROM dish_ratings WHERE dish_id = ?', (dish_id,))
    rating_data = c.fetchone()

    # If the form is submitted, save the review
    if request.method == 'POST':
        customer_id = 1  # This should be the logged-in customer's ID
        dish_rating = int(request.form['dish_rating'])
        dish_review = request.form['dish_review']

        # Save the review to the database
        c.execute('''
            INSERT INTO dish_reviews (customer_id, dish_id, rating, review_text)
            VALUES (?, ?, ?, ?)
        ''', (customer_id, dish_id, dish_rating, dish_review))

        # Update the average rating for the dish
        c.execute('''
            SELECT AVG(rating), COUNT(*) FROM dish_reviews WHERE dish_id = ?
        ''', (dish_id,))
        avg_rating, total_reviews = c.fetchone()

        # Update dish ratings table
        c.execute('''
            INSERT INTO dish_ratings (dish_id, average_rating, total_reviews)
            VALUES (?, ?, ?)
            ON CONFLICT(dish_id) DO UPDATE SET
            average_rating = ?, total_reviews = ?
        ''', (dish_id, avg_rating, total_reviews, avg_rating, total_reviews))

        conn.commit()

    conn.close()
    return render_template('dish_details.html', dish=dish, reviews=reviews, average_rating=rating_data[0], total_reviews=rating_data[1])
@app.route('/submit_review/<int:dish_id>', methods=['GET', 'POST'])
def submit_review(dish_id):
    conn = sqlite3.connect('hotel.db')
    conn.row_factory = sqlite3.Row  # Enables dict-style access
    c = conn.cursor()

    # Fetch dish info with id and name
    c.execute("SELECT id, name FROM dishes WHERE id = ?", (dish_id,))
    dish = c.fetchone()

    if dish is None:
        conn.close()
        return "Dish not found", 404

    if request.method == 'POST':
        rating = request.form['rating']
        review_text = request.form['review_text']

        c.execute('''
            INSERT INTO dish_reviews (customer_id, dish_id, rating, review_text)
            VALUES (?, ?, ?, ?)
        ''', (1, dish_id, rating, review_text))  # Assume customer_id=1
        conn.commit()
        conn.close()
        return redirect(url_for('dish_list'))

    conn.close()
    return render_template('submit_review.html', dish=dish, dish_id=dish_id)


@app.route('/dishes')
def dish_list():
    conn = sqlite3.connect('hotel.db')
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM dishes")
    dishes = c.fetchall()

    # Get reviews for each dish
    reviews = {}
    for dish in dishes:
        c.execute('''
            SELECT rating, review_text FROM dish_reviews WHERE dish_id = ?
        ''', (dish[0],))
        reviews[dish[0]] = c.fetchall()

    conn.close()

    return render_template('dish_list.html', dishes=dishes, reviews=reviews)
@app.route('/check-availability', methods=['GET'])
def check_availability():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Fetch all dishes and their availability
    c.execute("SELECT dish_name, quantity_in_stock FROM dish_inventory")
    available_dishes = c.fetchall()

    conn.close()

    # This return statement must be inside the function
    return render_template('check_availability.html', available_dishes=available_dishes)

if __name__ == "__main__":
    app.run(debug=True)

