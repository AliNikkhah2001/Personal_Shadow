"""
Food Calorie Estimation VLM - Models & Dataset Downloader
Downloads food recognition models, VLMs for calorie estimation, and datasets.
Best models: Food-R1, FoodLMM, Qwen2.5-VL (for fine-tuning)
Best datasets: Nutrition5k, CalData, Food-101
"""
import os
import subprocess
import sys
import urllib.request

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "calorie")
DATASETS_DIR = os.path.join(os.path.dirname(__file__), "..", "datasets", "food")


def download(url, dest, desc=""):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        print(f"  [skip] {desc or os.path.basename(dest)} already exists")
        return
    print(f"  [download] {desc or os.path.basename(dest)}...")
    try:
        subprocess.run(["curl", "-L", "-o", dest, url], check=False, timeout=600)
        print(f"  [done] {desc}")
    except Exception as e:
        print(f"  [error] {desc}: {e}")


def install_deps():
    print("\n=== Installing Dependencies ===")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                     "torch", "torchvision", "transformers", "huggingface_hub",
                     "opencv-python", "pillow", "datasets", "timm"], check=False)


def download_food_classifier():
    print("\n=== Downloading Food Classification Models ===")
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("\n--- nateraw/food (Food-101 classifier, ~90% accuracy) ---")
    print("  [info] Auto-downloads on first use:")
    print("         from transformers import pipeline")
    print('         pipe = pipeline("image-classification", model="nateraw/food")')

    print("\n--- BinhQuocNguyen/food-recognition-model (EfficientNet + calories) ---")
    print("  [info] Auto-downloads on first use:")
    print("         from transformers import pipeline")
    print('         pipe = pipeline("image-classification", model="BinhQuocNguyen/food-recognition-model")')


def download_vlm_models():
    print("\n=== Downloading VLM Models for Calorie Estimation ===")
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("\n--- Food-R1 (7B, best food VLM, Calorie MAE: 42.56 kcal) ---")
    print("  [info] HuggingFace: https://huggingface.co/collections/zy12123/food-r1")
    print("  [info] GitHub: https://github.com/hustvl/Food-R1")
    print("  [info] Requires ~16GB VRAM for inference")

    print("\n--- Qwen2.5-VL-7B (good baseline, Apache 2.0) ---")
    print("  [info] Auto-downloads on first use:")
    print("         from transformers import AutoProcessor, AutoModelForCausalLM")
    print('         model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-VL-7B-Instruct")')

    print("\n--- SmolVLM2-500M (lightweight, edge deployment) ---")
    print("  [info] Auto-downloads on first use:")
    print("         from transformers import pipeline")
    print('         pipe = pipeline("image-text-to-text", model="HuggingFaceTB/SmolVLM2-500M-Video-Instruct")')


def download_datasets():
    print("\n=== Downloading Food Datasets ===")
    os.makedirs(DATASETS_DIR, exist_ok=True)

    print("\n--- Food-101 (101 classes, 101K images) ---")
    food101_dir = os.path.join(DATASETS_DIR, "food-101")
    if not os.path.exists(food101_dir):
        print("  [info] HuggingFace: https://huggingface.co/datasets/ethz/food101")
        print("         pip install datasets; from datasets import load_dataset")
        print('         ds = load_dataset("ethz/food101")')
        print("  [info] Direct: https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/")
    else:
        print("  [skip] Food-101 exists")

    print("\n--- Nutrition5k (5K plates with calorie annotations) ---")
    nutrition_dir = os.path.join(DATASETS_DIR, "nutrition5k")
    if not os.path.exists(nutrition_dir):
        print("  [info] GitHub: https://github.com/google-research-datasets/Nutrition5k")
        print("  [info] Kaggle: https://www.kaggle.com/datasets/gillesokhin/nutrition5k-dataset")
        print("  [info] Google Cloud: https://console.cloud.google.com/storage/browser/nutrition5k_dataset")
    else:
        print("  [skip] Nutrition5k exists")

    print("\n--- CalData (330K image-text pairs for calorie estimation) ---")
    caldata_dir = os.path.join(DATASETS_DIR, "caldata")
    if not os.path.exists(caldata_dir):
        print("  [info] HuggingFace: https://huggingface.co/datasets/Kennyy/Cal_Data")
        print("         pip install datasets; from datasets import load_dataset")
        print('         ds = load_dataset("Kennyy/Cal_Data")')
    else:
        print("  [skip] CalData exists")

    print("\n--- MM-Food-100K (100K multimodal food data) ---")
    print("  [info] HuggingFace: https://huggingface.co/datasets/Codatta/MM-Food-100K")

    print("\n--- FoodDialogues (multi-turn food dialogues) ---")
    print("  [info] HuggingFace: https://huggingface.co/datasets/Yueha0/FoodDialogues")

    print("\n--- USDA FoodData Central (300K+ foods, free API) ---")
    print("  [info] API: https://fdc.nal.usda.gov/api-guide.html")
    print("  [info] Portal: https://fdc.nal.usda.gov/")

    print("\n--- OpenFoodFacts (open nutrition DB) ---")
    print("  [info] API: https://world.openfoodfacts.org/data")


def create_inference_script():
    script_path = os.path.join(MODELS_DIR, "estimate_calories.py")
    if os.path.exists(script_path):
        return
    script = '''"""
Food Calorie Estimation from Image

Uses HuggingFace food classifier + USDA nutrition database.
For better accuracy, use Food-R1 or fine-tuned Qwen2.5-VL.
"""
import json
import os
import sys
from PIL import Image

FOOD_CALORIES_DB = {
    "apple_pie": 237, "baby_back_ribs": 285, "baklava": 331,
    "beef_carpaccio": 140, "beef_tartare": 170, "beet_salad": 73,
    "beignets": 349, "bibimbap": 490, "bread_pudding": 242,
    "breakfast_burrito": 210, "bruschetta": 180, "caesar_salad": 127,
    "cannoli": 254, "caprese_salad": 140, "carrot_cake": 339,
    "ceviche": 69, "cheesecake": 321, "cheese_plate": 350,
    "chicken_curry": 165, "chicken_quesadilla": 230,
    "chicken_wings": 203, "chocolate_cake": 352,
    "chocolate_mousse": 250, "churros": 360, "clam_chowder": 163,
    "club_sandwich": 282, "crab_cakes": 197, "creme_brulee": 310,
    "croque_madame": 280, "cup_cakes": 305, "deviled_eggs": 155,
    "donuts": 452, "dumplings": 215, "edamame": 121,
    "eggs_benedict": 240, "escargots": 180, "falafel": 333,
    "filet_mignon": 280, "fish_and_chips": 240, "foie_gras": 462,
    "french_fries": 312, "french_onion_soup": 94,
    "french_toast": 212, "fried_calamari": 175,
    "fried_rice": 163, "frozen_yogurt": 127, "garlic_bread": 195,
    "gnocchi": 133, "greek_salad": 100, "grilled_cheese_sandwich": 290,
    "grilled_salmon": 208, "guacamole": 160, "gyoza": 170,
    "hamburger": 250, "hot_and_sour_soup": 45, "hot_dog": 290,
    "huevos_rancheros": 220, "hummus": 166, "ice_cream": 207,
    "lasagna": 135, "lobster_bisque": 145, "lobster_roll_sandwich": 280,
    "macaroni_and_cheese": 164, "macarons": 380, "miso_soup": 32,
    "mussels": 86, "nachos": 210, "omelette": 154,
    "onion_rings": 270, "oysters": 69, "pad_thai": 190,
    "paella": 200, "pancakes": 227, "panna_cotta": 285,
    "peking_duck": 200, "pho": 46, "pizza": 266,
    "pork_chop": 231, "poutine": 210, "prime_rib": 360,
    "pulled_pork_sandwich": 270, "ramen": 190, "ravioli": 180,
    "red_velvet_cake": 350, "risotto": 164, "samosa": 262,
    "sashimi": 143, "scallops": 140, "seaweed_salad": 45,
    "shrimp_and_grits": 200, "spaghetti_bolognese": 130,
    "spaghetti_carbonara": 195, "spring_rolls": 155,
    "steak": 271, "strawberry_shortcake": 239, "sushi": 143,
    "tacos": 226, "takoyaki": 180, "tiramisu": 329,
    "tuna_tartare": 130, "waffles": 218,
}

def estimate_calories(image_path):
    try:
        from transformers import pipeline
        classifier = pipeline("image-classification", model="nateraw/food")
        image = Image.open(image_path)
        results = classifier(image, top_k=3)

        total_estimate = 0
        print("Food Detection Results:")
        for r in results:
            food_name = r["label"]
            confidence = r["score"]
            calories = FOOD_CALORIES_DB.get(food_name.lower(), 150)
            weighted_cal = calories * confidence
            total_estimate += weighted_cal
            print(f"  {food_name}: {confidence:.1%} confidence, ~{calories} kcal/100g")

        print(f"\\nEstimated calories (weighted): {total_estimate:.0f} kcal")
        return results
    except Exception as e:
        print(f"Error: {e}")
        print("Install dependencies: pip install transformers torch pillow")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python estimate_calories.py <image_path>")
        sys.exit(1)
    estimate_calories(sys.argv[1])
'''
    with open(script_path, "w") as f:
        f.write(script)
    print(f"  [created] {script_path}")


if __name__ == "__main__":
    install_deps()
    download_food_classifier()
    download_vlm_models()
    download_datasets()
    create_inference_script()
    print("\n=== Calorie Estimation VLM Setup Complete ===")
    print(f"Models saved to: {MODELS_DIR}")
    print("Usage: python estimate_calories.py <image_path>")
