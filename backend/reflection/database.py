import random
import sqlite3

import pandas as pd


def create_transactions_db(
    db_name: str = "products.db",
    n_products: int = 100,
    n_txns_per_product: int = 50,
) -> None:
    """
    Create an SQLite DB with a single 'transactions' table (event-sourced).
    All analytics must be derived from this table (no views).
    """
    conn = sqlite3.connect(db_name)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS transactions")

    cur.execute("""
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        brand TEXT NOT NULL,
        category TEXT NOT NULL,
        color TEXT NOT NULL,

        action TEXT NOT NULL,
        qty_delta INTEGER DEFAULT 0,
        unit_price REAL,
        notes TEXT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    brands = ["Nike", "Adidas", "Puma", "Reebok", "New Balance"]
    categories = ["shoes", "hoodie", "t-shirt", "hat", "backpack"]
    colors = ["black", "white", "red", "blue", "green"]

    rng = random.Random(42)
    product_catalog = []
    for pid in range(1, n_products + 1):
        name = f"{rng.choice(brands)} {rng.choice(categories)}"
        brand = name.split()[0]
        category = name.split()[1]
        color = rng.choice(colors)
        base_price = round(rng.uniform(20.0, 150.0), 2)
        product_catalog.append((pid, name, brand, category, color, base_price))

    for (pid, name, brand, category, color, base_price) in product_catalog:
        initial_stock = rng.randint(5, 50)
        cur.execute("""
            INSERT INTO transactions (
                product_id, product_name, brand, category, color,
                action, qty_delta, unit_price, notes
            ) VALUES (?, ?, ?, ?, ?, 'insert', ?, ?, ?)
        """, (pid, name, brand, category, color, initial_stock, base_price,
              f"Initial insert with stock={initial_stock}, price={base_price}"))

        current_price = base_price

        for _ in range(n_txns_per_product - 1):
            event_type = rng.choices(
                ["restock", "sale", "price_update"],
                weights=[0.25, 0.6, 0.15],
                k=1,
            )[0]

            if event_type == "restock":
                qty = rng.randint(1, 25)
                cur.execute("""
                    INSERT INTO transactions (
                        product_id, product_name, brand, category, color,
                        action, qty_delta, unit_price, notes
                    ) VALUES (?, ?, ?, ?, ?, 'restock', ?, NULL, ?)
                """, (pid, name, brand, category, color, qty,
                      f"Restock +{qty} units"))

            elif event_type == "sale":
                qty = -rng.randint(1, 10)
                cur.execute("""
                    INSERT INTO transactions (
                        product_id, product_name, brand, category, color,
                        action, qty_delta, unit_price, notes
                    ) VALUES (?, ?, ?, ?, ?, 'sale', ?, ?, ?)
                """, (pid, name, brand, category, color, qty, current_price,
                      f"Sale {-qty} units at {current_price}"))

            else:
                delta = round(rng.uniform(-5.0, 5.0), 2)
                current_price = max(1.0, round(current_price + delta, 2))
                cur.execute("""
                    INSERT INTO transactions (
                        product_id, product_name, brand, category, color,
                        action, qty_delta, unit_price, notes
                    ) VALUES (?, ?, ?, ?, ?, 'price_update', 0, ?, ?)
                """, (pid, name, brand, category, color, current_price,
                      f"Price update to {current_price}"))

    conn.commit()
    conn.close()

    print(f"SQLite database '{db_name}' created with a single 'transactions' table (event-sourced).")


def get_schema(db_path: str) -> str:
    """Return only the schema that the agent should use: 'transactions' table."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(transactions)")
    rows = cur.fetchall()
    conn.close()
    return "table name: transactions\n" + "\n".join([f"{r[1]} ({r[2]})" for r in rows])


def execute_sql(query: str, db_path: str) -> pd.DataFrame:
    """Execute any SELECT over the event-sourced 'transactions' table."""
    q = query.strip().removeprefix("```sql").removesuffix("```").strip()
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(q, conn)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})
    finally:
        conn.close()
