import sqlite3
import time

import requests

DB_PATH = "second_brain.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS ingredients (id INTEGER PRIMARY KEY, name TEXT UNIQUE, emoji TEXT, kcal REAL, protein REAL, fat REAL, carbs REAL, data_source TEXT);
        CREATE TABLE IF NOT EXISTS exercises (id INTEGER PRIMARY KEY, name TEXT UNIQUE, category TEXT, emoji TEXT, description TEXT, data_source TEXT);
    ''')
    conn.commit()
    return conn, c

def fetch_factual_foods(c):
    print("🌍 Fetching factual nutritional data from OpenFoodFacts API...")
    # Fetching common whole foods from verified scans
    url = "https://us.openfoodfacts.org/cgi/search.pl?search_terms=raw%20whole&search_simple=1&action=process&sort_by=unique_scans_n&page_size=100&json=true"

    try:
        response = requests.get(url, headers={'User-Agent': 'MindPalaceOS/1.0'})
        data = response.json()

        products = data.get("products", [])
        added = 0

        for p in products:
            name = p.get("product_name", "").title()
            nutriments = p.get("nutriments", {})

            kcal = nutriments.get("energy-kcal_100g", 0)
            protein = nutriments.get("proteins_100g", 0)
            fat = nutriments.get("fat_100g", 0)
            carbs = nutriments.get("carbohydrates_100g", 0)

            if name and kcal > 0:
                # Basic emoji assignment based on keywords
                emoji = "🍏" if "apple" in name.lower() else "🥩" if "beef" in name.lower() else "🍗" if "chicken" in name.lower() else "🥛" if "milk" in name.lower() else "🌾" if "oat" in name.lower() else "🍽️"

                try:
                    c.execute("INSERT INTO ingredients (name, emoji, kcal, protein, fat, carbs, data_source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (name, emoji, float(kcal), float(protein), float(fat), float(carbs), "OpenFoodFacts"))
                    added += 1
                except sqlite3.IntegrityError:
                    pass # Skip duplicates

        print(f"✅ Successfully injected {added} real food items into the database.")
    except Exception as e:
        print(f"❌ Failed to fetch food data: {e}")

def fetch_factual_exercises(c):
    print("🏋️‍♂️ Fetching factual exercise data from Wger REST API...")
    url = "https://wger.de/api/v2/exercise/?language=2&limit=100" # Language 2 = English

    # Wger category mapping
    categories = { 8: "Arms", 9: "Legs", 10: "Abs", 11: "Chest", 12: "Back", 13: "Shoulders", 14: "Calves", 15: "Cardio" }

    try:
        response = requests.get(url, headers={'Accept': 'application/json'})
        data = response.json()

        exercises = data.get("results", [])
        added = 0

        for ex in exercises:
            name = ex.get("name")
            cat_id = ex.get("category")
            category = categories.get(cat_id, "General")
            desc = ex.get("description", "").replace("<p>", "").replace("</p>", "")[:200]

            emoji = "💪" if category in ["Arms", "Shoulders", "Chest", "Back"] else "🦵" if category in ["Legs", "Calves"] else "🏃" if category == "Cardio" else "🏋️"

            if name:
                try:
                    c.execute("INSERT INTO exercises (name, category, emoji, description, data_source) VALUES (?, ?, ?, ?, ?)",
                              (name, category, emoji, desc, "Wger API"))
                    added += 1
                except sqlite3.IntegrityError:
                    pass

        print(f"✅ Successfully injected {added} real exercises into the database.")
    except Exception as e:
        print(f"❌ Failed to fetch exercise data: {e}")

if __name__ == "__main__":
    conn, c = init_db()
    fetch_factual_foods(c)
    time.sleep(1) # Be polite to APIs
    fetch_factual_exercises(c)
    conn.commit()
    conn.close()
    print("🎉 Database seeding complete! You can now search these in your app.")
