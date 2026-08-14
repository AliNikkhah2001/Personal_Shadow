#!/usr/bin/env python3
"""Download Food-101 dataset subset for testing.

Downloads a small subset of Food-101 for testing the calorie vision estimator.
"""

from __future__ import annotations

import tarfile
import urllib.request
from pathlib import Path

from tqdm import tqdm

FOOD101_URL = "http://data.vision.ee.ethz.ch/cvl/food-101.tar.gz"
FOOD101_META_URL = "https://raw.githubusercontent.com/google-research-datasets/Nutrition5k/main/dataset/dishes/metadata_cafe1.csv"


def download_with_progress(url: str, dest: Path, desc: str = "Downloading"):
    """Download file with progress bar."""
    def download_hook(block_num, block_size, total_size):
        if not hasattr(download_hook, 'pbar'):
            download_hook.pbar = tqdm(total=total_size, unit='B', unit_scale=True, desc=desc)
        download_hook.pbar.update(block_size)

    urllib.request.urlretrieve(url, dest, reporthook=download_hook)
    if hasattr(download_hook, 'pbar'):
        download_hook.pbar.close()


def download_food101_subset(output_dir: str = "data/food101",
                            max_classes: int = 10,
                            images_per_class: int = 5) -> Path:
    """Download and extract a subset of Food-101.

    Args:
        output_dir: Where to extract
        max_classes: Number of classes to download
        images_per_class: Images per class to keep
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Check if already extracted
    images_dir = out_path / "food-101" / "images"
    if images_dir.exists() and any(images_dir.iterdir()):
        print(f"Food-101 already extracted at {images_dir}")
        return images_dir

    # Download
    tar_path = out_path / "food-101.tar.gz"
    if not tar_path.exists():
        print("Downloading Food-101 dataset (~5GB)...")
        download_with_progress(FOOD101_URL, tar_path, "Food-101")

    # Extract
    print("Extracting Food-101...")
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(out_path)

    print(f"Extracted to {out_path / 'food-101'}")
    return images_dir


def create_food101_test_set(images_dir: Path,
                            output_dir: str = "test_results/food101_subset",
                            max_classes: int = 10,
                            images_per_class: int = 5) -> list[dict]:
    """Create a curated test subset from Food-101.

    Selects diverse food classes and creates ground truth compatible format.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Select diverse classes that our estimator can potentially detect
# Based on our 17 food classes: rice, pasta, bread, meat, chicken, fish, egg,
    # vegetable, salad, fruit, tomato, potato, cheese, yogurt, stew, soup, mixed
    # target_classes = [  # unused, kept for reference
    #     "rice", "pasta", "bread", "meat", "chicken", "fish", "egg",
    #     "vegetable", "salad", "fruit", "tomato", "potato",
    #     "cheese", "yogurt", "stew", "soup", "mixed",
    # ]

    # Map Food-101 classes to our classes
    class_mapping = {
        "rice": ["fried_rice", "jambalaya", "risotto"],
        "pasta": ["spaghetti_bolognese", "spaghetti_carbonara", "lasagna", "ravioli", "gnocchi"],
        "bread": ["bread_pudding", "croissant", "bagel", "pretzel"],
        "meat": ["steak", "prime_rib", "beef_tartare", "beef_carpaccio", "hamburger"],
        "chicken": ["chicken_curry", "chicken_quesadilla", "chicken_wings"],
        "fish": ["fish_and_chips", "grilled_salmon", "sashimi", "tuna_tartare"],
        "egg": ["eggs_benedict", "omelette", "deviled_eggs"],
        "vegetable": ["vegetable_stir_fry", "ratatouille", "spring_rolls"],
        "salad": ["caesar_salad", "greek_salad", "caprese_salad", "iceberg_lettuce"],
        "fruit": ["apple_pie", "strawberry_shortcake", "fruit_salad"],
        "tomato": ["tomato_soup", "bruschetta"],
        "potato": ["french_fries", "baked_potato", "potato_salad"],
        "cheese": ["cheese_plate", "grilled_cheese_sandwich", "macaroni_and_cheese"],
        "yogurt": ["frozen_yogurt", "yogurt_parfait"],
        "stew": ["beef_stew", "chili_con_carne"],
        "soup": ["french_onion_soup", "miso_soup", "clam_chowder", "hot_and_sour_soup"],
    }

    # Find matching Food-101 classes
    images_root = Path(images_dir)
    food101_classes = [d.name for d in images_root.iterdir() if d.is_dir()]

    matched_classes = {}
    for our_class, f101_classes in class_mapping.items():
        for f101 in f101_classes:
            if f101 in food101_classes:
                matched_classes[our_class] = f101
                break

    print(f"Found {len(matched_classes)} matching classes: {list(matched_classes.keys())}")

    # Copy selected images and create ground truth
    gt_list = []
    for our_class, f101_class in matched_classes.items():
        class_dir = images_root / f101_class
        if not class_dir.exists():
            continue

        images = list(class_dir.glob("*.jpg"))[:images_per_class]
        for i, img in enumerate(images):
            dest_name = f"{our_class}_{f101_class}_{i}.jpg"
            dest_path = Path(output_dir) / dest_name

            # Copy
            import shutil
            shutil.copy2(img, dest_path)

            # Create basic ground truth (no real weight/kcal for Food-101)
            gt_list.append({
                "image_path": str(dest_path),
                "food_class": our_class,
                "bbox": [0, 0, 0, 0],  # Unknown - full image
                "weight_grams": 100,  # Placeholder
                "kcal": 0,  # Unknown
                "reference_object": None,
                "pixels_per_cm": None,
            })

    # Save ground truth
    import json
    gt_path = Path(output_dir) / "ground_truth.json"
    with open(gt_path, "w") as f:
        json.dump(gt_list, f, indent=2)

    print(f"Created test set with {len(gt_list)} images at {output_dir}")
    print(f"Ground truth saved to {gt_path}")

    return gt_list


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download Food-101 subset for testing")
    parser.add_argument("--output", default="data/food101", help="Output directory")
    parser.add_argument("--max-classes", type=int, default=10, help="Max classes")
    parser.add_argument("--images-per-class", type=int, default=5, help="Images per class")
    parser.add_argument("--subset-only", action="store_true", help="Only create subset from existing download")
    args = parser.parse_args()

    if not args.subset_only:
        download_food101_subset(args.output, args.max_classes, args.images_per_class)

    images_dir = Path(args.output) / "food-101" / "images"
    if images_dir.exists():
        create_food101_test_set(
            images_dir,
            output_dir="test_results/food101_test",
            max_classes=args.max_classes,
            images_per_class=args.images_per_class
        )
    else:
        print(f"Images directory not found: {images_dir}")


if __name__ == "__main__":
    main()
