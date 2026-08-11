"""Data import script for nutrition database.

Imports food data from OpenFoodFacts API and supports manual entry
of Persian/Iranian food data (SAMAR dataset).
"""

import sqlite3
import time
from pathlib import Path

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

DB_PATH = "second_brain.db"


def init_db():
    """Initialize database connection."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    return conn, c


def fetch_openfoodfacts(c, max_items: int = 200) -> int:
    """Fetch food data from OpenFoodFacts API."""
    if not REQUESTS_AVAILABLE:
        print("⚠️ requests library not available, skipping OpenFoodFacts import")
        return 0

    print("🌍 Fetching nutritional data from OpenFoodFacts API...")
    url = "https://us.openfoodfacts.org/cgi/search.pl?search_terms=&search_simple=1&action=process&sort_by=unique_scans_n&page_size=500&json=true"

    try:
        response = requests.get(url, headers={"User-Agent": "MindPalaceOS/1.0"}, timeout=30)
        data = response.json()

        products = data.get("products", [])
        added = 0

        for p in products:
            if added >= max_items:
                break

            name = p.get("product_name", "").strip()
            if not name:
                continue

            nutriments = p.get("nutriments", {})

            kcal = nutriments.get("energy-kcal_100g", 0)
            protein = nutriments.get("proteins_100g", 0)
            fat = nutriments.get("fat_100g", 0)
            carbs = nutriments.get("carbohydrates_100g", 0)

            if kcal <= 0:
                continue

            # Determine category based on keywords
            category = categorize_food(name)

            # Assign emoji based on category
            emoji_map = {
                "Fruits": "🍎",
                "Vegetables": "🥕",
                "Meat": "🥩",
                "Poultry": "🍗",
                "Fish": "🐟",
                "Dairy": "🥛",
                "Grains": "🌾",
                "Legumes": "🫘",
                "Nuts": "🥜",
                "Oils": "🫒",
                "Beverages": "🥤",
                "Sweets": "🍬",
                "Condiments": "🧂",
                "Prepared": "🍽️",
                "General": "🍽️",
            }
            emoji_map.get(category, "🍽️")

            try:
                c.execute(
                    """INSERT INTO ingredients (uuid, modified_at, name, kcal, protein, fat, carbs,
                       serving_size, serving_unit, category, image_path, is_iranian)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        __import__("uuid").uuid4().hex,
                        __import__("datetime").datetime.now().isoformat(),
                        name.title(),
                        float(kcal),
                        float(protein),
                        float(fat),
                        float(carbs),
                        100,
                        "g",
                        category,
                        "",
                        0,
                    ),
                )
                added += 1
            except sqlite3.IntegrityError:
                pass  # Skip duplicates

        print(f"✅ Successfully imported {added} food items from OpenFoodFacts")
        return added
    except Exception as e:
        print(f"❌ Failed to fetch food data: {e}")
        return 0


def categorize_food(name: str) -> str:
    """Categorize food based on name keywords."""
    name_lower = name.lower()

    categories = {
        "Fruits": [
            "apple",
            "banana",
            "orange",
            "berry",
            "grape",
            "mango",
            "pineapple",
            "peach",
            "pear",
            "melon",
            "kiwi",
            "plum",
            "cherry",
            "apricot",
            "fig",
            "date",
            "pomegranate",
            "watermelon",
            "cantaloupe",
            "honeydew",
        ],
        "Vegetables": [
            "carrot",
            "broccoli",
            "spinach",
            "kale",
            "lettuce",
            "tomato",
            "cucumber",
            "pepper",
            "onion",
            "garlic",
            "potato",
            "sweet potato",
            "yam",
            "squash",
            "zucchini",
            "eggplant",
            "asparagus",
            "celery",
            "mushroom",
            "cauliflower",
            "cabbage",
            "brussels",
        ],
        "Meat": ["beef", "pork", "lamb", "veal", "venison", "steak", "roast", "ground"],
        "Poultry": ["chicken", "turkey", "duck", "goose", "quail"],
        "Fish": [
            "salmon",
            "tuna",
            "cod",
            "tilapia",
            "halibut",
            "trout",
            "bass",
            "mackerel",
            "sardine",
            "anchovy",
            "shrimp",
            "crab",
            "lobster",
            "scallop",
            "clam",
            "mussel",
        ],
        "Dairy": [
            "milk",
            "cheese",
            "yogurt",
            "butter",
            "cream",
            "cottage cheese",
            "mozzarella",
            "cheddar",
            "parmesan",
            "feta",
            "ricotta",
        ],
        "Grains": [
            "rice",
            "wheat",
            "oats",
            "quinoa",
            "barley",
            "corn",
            "bread",
            "pasta",
            "noodle",
            "cereal",
            "flour",
            "couscous",
            "bulgur",
            "farro",
        ],
        "Legumes": ["bean", "lentil", "chickpea", "pea", "soy", "tofu", "tempeh", "edamame", "hummus"],
        "Nuts": ["almond", "walnut", "cashew", "pistachio", "pecan", "hazelnut", "macadamia", "peanut", "nut butter"],
        "Oils": [
            "olive oil",
            "coconut oil",
            "avocado oil",
            "vegetable oil",
            "canola oil",
            "sesame oil",
            "ghee",
            "butter",
        ],
        "Beverages": ["water", "coffee", "tea", "juice", "soda", "beer", "wine", "alcohol"],
        "Sweets": ["chocolate", "candy", "cookie", "cake", "pie", "ice cream", "honey", "sugar", "syrup", "jam"],
        "Condiments": [
            "salt",
            "pepper",
            "vinegar",
            "soy sauce",
            "ketchup",
            "mustard",
            "mayonnaise",
            "sauce",
            "dressing",
            "spice",
            "herb",
        ],
        "Prepared": ["soup", "stew", "curry", "pizza", "burger", "sandwich", "salad", "sushi", "taco", "burrito"],
    }

    for cat, keywords in categories.items():
        if any(kw in name_lower for kw in keywords):
            return cat
    return "General"


def import_samar_csv(c, csv_path: str) -> int:
    """Import Iranian food data from SAMAR CSV file.

    Expected CSV columns: name, kcal, protein, fat, carbs, category, serving_size, serving_unit
    """
    import csv

    if not Path(csv_path).exists():
        print(f"⚠️ SAMAR CSV file not found at {csv_path}")
        return 0

    print(f"🇮🇷 Importing Iranian food data from {csv_path}...")
    added = 0

    try:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").strip()
                if not name:
                    continue

                try:
                    kcal = float(row.get("kcal", 0))
                    protein = float(row.get("protein", 0))
                    fat = float(row.get("fat", 0))
                    carbs = float(row.get("carbs", 0))
                    serving_size = float(row.get("serving_size", 100))
                    serving_unit = row.get("serving_unit", "g")
                    category = row.get("category", "Iranian")
                except ValueError:
                    continue

                if kcal <= 0:
                    continue

                try:
                    c.execute(
                        """INSERT INTO ingredients (uuid, modified_at, name, kcal, protein, fat, carbs,
                           serving_size, serving_unit, category, image_path, is_iranian)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            __import__("uuid").uuid4().hex,
                            __import__("datetime").datetime.now().isoformat(),
                            name,
                            kcal,
                            protein,
                            fat,
                            carbs,
                            serving_size,
                            serving_unit,
                            category,
                            "",
                            1,
                        ),
                    )
                    added += 1
                except sqlite3.IntegrityError:
                    pass

        print(f"✅ Successfully imported {added} Iranian food items from SAMAR")
        return added
    except Exception as e:
        print(f"❌ Failed to import SAMAR data: {e}")
        return 0


def create_sample_samar_csv(output_path: str = "samar_foods.csv"):
    """Create a sample SAMAR CSV template with common Iranian foods."""
    import csv

    samar_foods = [
        {
            "name": "برنج پخته (چلو)",
            "kcal": 130,
            "protein": 2.7,
            "fat": 0.3,
            "carbs": 28,
            "category": "Grains",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "برنج برشت (کته)",
            "kcal": 150,
            "protein": 3.0,
            "fat": 1.5,
            "carbs": 32,
            "category": "Grains",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "نان بربری",
            "kcal": 265,
            "protein": 8.5,
            "fat": 1.2,
            "carbs": 53,
            "category": "Grains",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "نان سنگک",
            "kcal": 255,
            "protein": 9.0,
            "fat": 1.0,
            "carbs": 52,
            "category": "Grains",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "نان لavaş",
            "kcal": 250,
            "protein": 8.0,
            "fat": 1.0,
            "carbs": 52,
            "category": "Grains",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "ماست کیر",
            "kcal": 60,
            "protein": 3.5,
            "fat": 3.3,
            "carbs": 4.0,
            "category": "Dairy",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "ماست پرچرب",
            "kcal": 95,
            "protein": 3.3,
            "fat": 5.0,
            "carbs": 4.5,
            "category": "Dairy",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "پنیر لایق",
            "kcal": 265,
            "protein": 18,
            "fat": 21,
            "carbs": 1.5,
            "category": "Dairy",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "قورمه سبزی",
            "kcal": 145,
            "protein": 8.5,
            "fat": 9.0,
            "carbs": 7.5,
            "category": "Prepared",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "قیمه",
            "kcal": 155,
            "protein": 9.0,
            "fat": 8.5,
            "carbs": 10,
            "category": "Prepared",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "قرمه سبزی با برنج",
            "kcal": 180,
            "protein": 7.5,
            "fat": 8.0,
            "carbs": 20,
            "category": "Prepared",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "گhéymeh با برنج",
            "kcal": 190,
            "protein": 8.0,
            "fat": 7.5,
            "carbs": 22,
            "category": "Prepared",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "پلو سبزی",
            "kcal": 165,
            "protein": 5.5,
            "fat": 4.0,
            "carbs": 28,
            "category": "Prepared",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "باقل پلو",
            "kcal": 175,
            "protein": 6.0,
            "fat": 4.5,
            "carbs": 29,
            "category": "Prepared",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "زرشک پلو با مرغ",
            "kcal": 195,
            "protein": 12,
            "fat": 6.0,
            "carbs": 24,
            "category": "Prepared",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "کباب کوکوب",
            "kcal": 220,
            "protein": 18,
            "fat": 16,
            "carbs": 1.0,
            "category": "Meat",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "جوجه کباب",
            "kcal": 180,
            "protein": 22,
            "fat": 10,
            "carbs": 1.5,
            "category": "Poultry",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "سیب زمینی سرخ‌کرده",
            "kcal": 312,
            "protein": 3.4,
            "fat": 15,
            "carbs": 41,
            "category": "Vegetables",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "ادمه",
            "kcal": 65,
            "protein": 4.5,
            "fat": 0.2,
            "carbs": 11,
            "category": "Legumes",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "نخود",
            "kcal": 164,
            "protein": 8.9,
            "fat": 2.6,
            "carbs": 27,
            "category": "Legumes",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "عدس",
            "kcal": 116,
            "protein": 9.0,
            "fat": 0.4,
            "carbs": 20,
            "category": "Legumes",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "لوبیا",
            "kcal": 127,
            "protein": 8.7,
            "fat": 0.5,
            "carbs": 23,
            "category": "Legumes",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "پنیر ترشیده",
            "kcal": 110,
            "protein": 11,
            "fat": 7.0,
            "carbs": 1.0,
            "category": "Dairy",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "کره",
            "kcal": 717,
            "protein": 0.9,
            "fat": 81,
            "carbs": 0.1,
            "category": "Oils",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "ماست و خیار",
            "kcal": 55,
            "protein": 2.5,
            "fat": 3.0,
            "carbs": 3.5,
            "category": "Prepared",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "شله زرد",
            "kcal": 210,
            "protein": 2.5,
            "fat": 6.0,
            "carbs": 37,
            "category": "Sweets",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "حلوا",
            "kcal": 320,
            "protein": 4.0,
            "fat": 15,
            "carbs": 45,
            "category": "Sweets",
            "serving_size": 100,
            "serving_unit": "g",
        },
        {
            "name": "زولبیا و بامیه",
            "kcal": 380,
            "protein": 3.5,
            "fat": 18,
            "carbs": 52,
            "category": "Sweets",
            "serving_size": 100,
            "serving_unit": "g",
        },
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["name", "kcal", "protein", "fat", "carbs", "category", "serving_size", "serving_unit"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samar_foods)

    print(f"✅ Created sample SAMAR CSV at {output_path}")


def main():
    """Main entry point."""
    conn, c = init_db()

    # Create sample SAMAR CSV if it doesn't exist
    samar_path = "samar_foods.csv"
    if not Path(samar_path).exists():
        create_sample_samar_csv(samar_path)

    # Import from OpenFoodFacts
    fetch_openfoodfacts(c, max_items=200)
    time.sleep(1)

    # Import from SAMAR CSV
    import_samar_csv(c, samar_path)

    conn.commit()
    conn.close()
    print("🎉 Database seeding complete!")


if __name__ == "__main__":
    main()
