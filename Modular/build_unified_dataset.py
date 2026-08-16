#!/usr/bin/env python3
"""
Build unified YOLOv8-seg dataset from UEC Food 100, Food-101, and FoodSeg103.
"""

import os
import json
import cv2
import numpy as np
import shutil
from pathlib import Path
from PIL import Image
import pandas as pd
from tqdm import tqdm
import random

# Set seed for reproducibility
random.seed(42)
np.random.seed(42)

# Load unified class mapping
with open("data/datasets/unified_class_mapping.json") as f:
    unified_mapping = json.load(f)

unified_classes = unified_mapping["unified_classes"]
class_to_unified_id = unified_mapping["class_to_unified_id"]
source_mapping = unified_mapping["source_mapping"]

print(f"Unified classes: {len(unified_classes)}")

# Output directory
OUTPUT_DIR = Path("data/datasets/unified_food_dataset_yolo")
for split in ["train", "val", "test"]:
    (OUTPUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

# ============================================================
# 1. Process UEC Food 100 (bbox annotations)
# ============================================================
print("\n=== Processing UEC Food 100 ===")

uec_path = Path("data/datasets/UECFOOD100/UECFOOD100")
uec_category = {}
with open("data/datasets/UECFOOD100/category.txt") as f:
    for line in f:
        if line.strip() and not line.startswith("id"):
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                uec_category[int(parts[0])] = parts[1]

uec_samples = []  # (img_path, unified_class_id, bbox, dataset_name)

for class_dir in sorted(uec_path.iterdir()):
    if not class_dir.is_dir() or class_dir.name == "README.txt":
        continue
    
    class_id = int(class_dir.name)
    class_name = uec_category.get(class_id, class_dir.name)
    
    # Get unified class ID
    unified_id = source_mapping.get(f"uec:{class_name}") or source_mapping.get(f"uec:{class_id}")
    if unified_id is None:
        print(f"  Warning: No unified mapping for UEC class {class_id} ({class_name})")
        continue
    
    # Read bbox annotations
    bb_file = class_dir / "bb_info.txt"
    bboxes = {}
    if bb_file.exists():
        with open(bb_file) as f:
            for line in f:
                if line.strip() and not line.startswith("img"):
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        img_name = parts[0]
                        x1, y1, x2, y2 = map(int, parts[1:5])
                        bboxes[img_name] = (x1, y1, x2, y2)
    
    # Process images
    for img_file in class_dir.glob("*.jpg"):
        img_name = img_file.stem
        bbox = bboxes.get(img_name)
        uec_samples.append((img_file, unified_id, bbox, "uec"))

print(f"  Total UEC samples: {len(uec_samples)}")

# ============================================================
# 2. Process Food-101 (no annotations, classification only)
# ============================================================
print("\n=== Processing Food-101 ===")

food101_path = Path("data/datasets/food-101/food-101/images")
food101_samples = []

for class_dir in sorted(food101_path.iterdir()):
    if not class_dir.is_dir():
        continue
    
    class_name = class_dir.name
    unified_id = source_mapping.get(f"food101:{class_name}")
    if unified_id is None:
        print(f"  Warning: No unified mapping for Food-101 class {class_name}")
        continue
    
    for img_file in class_dir.glob("*.jpg"):
        food101_samples.append((img_file, unified_id, None, "food101"))

print(f"  Total Food-101 samples: {len(food101_samples)}")

# ============================================================
# 3. Process FoodSeg103 (segmentation masks)
# ============================================================
print("\n=== Processing FoodSeg103 ===")

foodseg103_path = Path("data/datasets/FoodSeg103_extracted")
foodseg103_classes = {
    1: "candy", 2: "egg_tart", 3: "french_fries", 4: "chocolate", 5: "biscuit", 6: "popcorn", 7: "pudding", 8: "ice_cream", 9: "cheese_butter", 10: "cake", 11: "wine", 12: "milkshake", 13: "coffee", 14: "juice", 15: "milk", 16: "tea", 17: "almond", 18: "red_beans", 19: "cashew", 20: "dried_cranberries", 21: "soy", 22: "walnut", 23: "peanut", 24: "egg", 25: "apple", 26: "date", 27: "apricot", 28: "avocado", 29: "banana", 30: "strawberry", 31: "cherry", 32: "blueberry", 33: "raspberry", 34: "mango", 35: "olives", 36: "peach", 37: "lemon", 38: "pear", 39: "fig", 40: "pineapple", 41: "grape", 42: "kiwi", 43: "melon", 44: "orange", 45: "watermelon", 46: "steak", 47: "pork", 48: "chicken_duck", 49: "sausage", 50: "fried_meat", 51: "lamb", 52: "sauce", 53: "crab", 54: "fish", 55: "shellfish", 56: "shrimp", 57: "soup", 58: "bread", 59: "corn", 60: "hamburg", 61: "pizza", 62: "hanamaki_baozi", 63: "wonton_dumplings", 64: "pasta", 65: "noodles", 66: "rice", 67: "pie", 68: "tofu", 69: "eggplant", 70: "potato", 71: "garlic", 72: "cauliflower", 73: "tomato", 74: "kelp", 75: "seaweed", 76: "spring_onion", 77: "rape", 78: "ginger", 79: "okra", 80: "lettuce", 81: "pumpkin", 82: "cucumber", 83: "white_radish", 84: "carrot", 85: "asparagus", 86: "bamboo_shoots", 87: "broccoli", 88: "celery_stick", 89: "cilantro_mint", 90: "snow_peas", 91: "cabbage", 92: "bean_sprouts", 93: "onion", 94: "pepper", 95: "green_beans", 96: "french_beans", 97: "king_oyster_mushroom", 98: "shiitake", 99: "enoki_mushroom", 100: "oyster_mushroom", 101: "white_button_mushroom", 102: "salad", 103: "other_ingredients"
}

foodseg103_samples = []

for img_file in (foodseg103_path / "images").glob("*.jpg"):
    # Find corresponding mask
    mask_file = foodseg103_path / "masks" / f"{img_file.stem}.png"
    if not mask_file.exists():
        continue
    
    # Load mask to find classes present
    mask = cv2.imread(str(mask_file), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        continue
    
    # Get unique class IDs in mask (excluding 0=background)
    class_ids = np.unique(mask)
    class_ids = class_ids[class_ids > 0]
    
    if len(class_ids) == 0:
        continue
    
    # For each class in the image, create a sample
    for class_id in class_ids:
        class_name = foodseg103_classes.get(int(class_id))
        if class_name is None:
            continue
        
        unified_id = source_mapping.get(f"foodseg103:{class_name}") or source_mapping.get(f"foodseg103:{class_id}")
        if unified_id is None:
            continue
        
        foodseg103_samples.append((img_file, unified_id, mask_file, "foodseg103"))

print(f"  Total FoodSeg103 samples: {len(foodseg103_samples)}")

# ============================================================
# 4. Combine and split by class
# ============================================================
print("\n=== Combining and splitting by class ===")

all_samples = uec_samples + food101_samples + foodseg103_samples
print(f"Total samples: {len(all_samples)}")

# Group by unified class ID
class_samples = {}
for sample in all_samples:
    class_id = sample[1]
    if class_id not in class_samples:
        class_samples[class_id] = []
    class_samples[class_id].append(sample)

# Check class distribution
print(f"\nClasses with samples: {len(class_samples)}")
for class_id in sorted(class_samples.keys()):
    class_name = unified_classes[class_id]
    count = len(class_samples[class_id])
    sources = set(s[3] for s in class_samples[class_id])
    print(f"  Class {class_id} ({class_name}): {count} samples from {sources}")

# Split each class: 70% train, 15% val, 15% test
train_samples = []
val_samples = []
test_samples = []

for class_id, samples in class_samples.items():
    random.shuffle(samples)
    n = len(samples)
    n_train = int(n * 0.7)
    n_val = int(n * 0.15)
    
    train_samples.extend(samples[:n_train])
    val_samples.extend(samples[n_train:n_train + n_val])
    test_samples.extend(samples[n_train + n_val:])

print(f"\nSplit: Train={len(train_samples)}, Val={len(val_samples)}, Test={len(test_samples)}")

# ============================================================
# 5. Convert to YOLO format and save
# ============================================================
print("\n=== Converting to YOLO format ===")

def bbox_to_yolo_polygon(bbox, img_w, img_h):
    """Convert bbox (x1, y1, x2, y2) to YOLO polygon format (normalized)."""
    x1, y1, x2, y2 = bbox
    # Create rectangle polygon: top-left, top-right, bottom-right, bottom-left
    poly = [
        x1 / img_w, y1 / img_h,
        x2 / img_w, y1 / img_h,
        x2 / img_w, y2 / img_h,
        x1 / img_w, y2 / img_h,
    ]
    return poly

def mask_to_yolo_polygons(mask_path, img_w, img_h, target_class_id):
    """Convert segmentation mask to YOLO polygons for a specific class."""
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return []
    
    # Resize mask to match image if needed
    if mask.shape[1] != img_w or mask.shape[0] != img_h:
        mask = cv2.resize(mask, (img_w, img_h), interpolation=cv2.INTER_NEAREST)
    
    # Create binary mask for target class
    binary_mask = (mask == target_class_id).astype(np.uint8) * 255
    
    # Find contours
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    polygons = []
    for contour in contours:
        if len(contour) < 3:
            continue
        # Approximate polygon
        epsilon = 0.005 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) < 3:
            continue
        
        # Normalize
        poly = []
        for point in approx:
            x, y = point[0]
            poly.append(x / img_w)
            poly.append(y / img_h)
        polygons.append(poly)
    
    return polygons

def process_split(samples, split_name):
    """Process a split and save images + labels."""
    img_dir = OUTPUT_DIR / "images" / split_name
    label_dir = OUTPUT_DIR / "labels" / split_name
    
    saved = 0
    for sample in tqdm(samples, desc=f"Processing {split_name}"):
        img_path, unified_id, annotation, source = sample
        unified_id = int(unified_id)
        
        # Read image
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        img_h, img_w = img.shape[:2]
        
        # Generate output filename
        stem = f"{source}_{img_path.stem}"
        out_img = img_dir / f"{stem}.jpg"
        out_label = label_dir / f"{stem}.txt"
        
        # Copy image
        cv2.imwrite(str(out_img), img)
        
        # Create label
        polygons = []
        if source == "uec" and annotation is not None:
            # Bbox to polygon
            poly = bbox_to_yolo_polygon(annotation, img_w, img_h)
            polygons.append(poly)
        elif source == "foodseg103" and annotation is not None:
            # Mask to polygons
            # Need to know which class_id in the mask corresponds to this unified_id
            # For FoodSeg103, we stored the mask file path, need to find the class_id
            mask = cv2.imread(str(annotation), cv2.IMREAD_GRAYSCALE)
            if mask is not None:
                # Find which class_id in mask maps to this unified_id
                class_ids = np.unique(mask)
                class_ids = class_ids[class_ids > 0]
                for cid in class_ids:
                    class_name = foodseg103_classes.get(int(cid))
                    if class_name and (source_mapping.get(f"foodseg103:{class_name}") == unified_id or source_mapping.get(f"foodseg103:{cid}") == unified_id):
                        polys = mask_to_yolo_polygons(annotation, img_w, img_h, int(cid))
                        polygons.extend(polys)
                        break
        # Food-101 has no annotations - skip label file (background/classification only)
        
        if polygons:
            with open(out_label, "w") as f:
                for poly in polygons:
                    line = f"{unified_id} " + " ".join(f"{x:.6f}" for x in poly)
                    f.write(line + "\n")
            saved += 1
        else:
            # For samples without segmentation (Food-101), create a dummy label file
            # or skip - YOLOv8-seg needs segmentation labels
            # We'll create a minimal label for classification
            # For now, skip Food-101 samples without masks
            if source != "food101":
                with open(out_label, "w") as f:
                    pass  # Empty label
            # Remove the image since we can't train segmentation without mask
            out_img.unlink(missing_ok=True)
    
    print(f"  {split_name}: Saved {saved} samples with segmentation")
    return saved

train_count = process_split(train_samples, "train")
val_count = process_split(val_samples, "val")
test_count = process_split(test_samples, "test")

# ============================================================
# 6. Create dataset.yaml
# ============================================================
print("\n=== Creating dataset.yaml ===")

yaml_content = f"""path: {OUTPUT_DIR.absolute()}
train: images/train
val: images/val
test: images/test

nc: {len(unified_classes)}
names: {unified_classes}
"""

with open(OUTPUT_DIR / "dataset.yaml", "w") as f:
    f.write(yaml_content)

print(f"Saved dataset.yaml to {OUTPUT_DIR / 'dataset.yaml'}")

# ============================================================
# 7. Save class stats
# ============================================================
stats = {
    "total_unified_classes": len(unified_classes),
    "total_samples": len(all_samples),
    "train_samples": train_count,
    "val_samples": val_count,
    "test_samples": test_count,
    "class_distribution": {}
}

for class_id, samples in class_samples.items():
    class_name = unified_classes[class_id]
    stats["class_distribution"][class_name] = {
        "total": len(samples),
        "train": sum(1 for s in samples if s in train_samples),
        "val": sum(1 for s in samples if s in val_samples),
        "test": sum(1 for s in samples if s in test_samples),
        "sources": list(set(s[3] for s in samples))
    }

with open(OUTPUT_DIR / "dataset_stats.json", "w") as f:
    json.dump(stats, f, indent=2)

print("\n=== Dataset Build Complete ===")
print(f"Output: {OUTPUT_DIR}")
print(f"Train: {train_count}, Val: {val_count}, Test: {test_count}")
print(f"Classes with >=100 samples: {sum(1 for v in stats['class_distribution'].values() if v['total'] >= 100)}")
print(f"Classes with >=50 samples: {sum(1 for v in stats['class_distribution'].values() if v['total'] >= 50)}")