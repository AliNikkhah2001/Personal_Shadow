#!/usr/bin/env python3
"""Batch evaluate calorie vision estimator on sample images.

Runs the estimator on all images in samples/calorie_vision/input/,
saves annotated images to samples/calorie_vision/annotated/,
and writes a CSV of results.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import cv2

from opencv_calorie_estimator import FoodCalorieEstimator, create_estimator_from_db

try:
    import sqlite3
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False


def main():
    in_dir = Path("samples/calorie_vision/input")
    out_dir = Path("samples/calorie_vision/annotated")
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_dir.exists():
        print(f"Input directory {in_dir} does not exist. Run fetch_sample_images.py first.")
        return 1

    images = sorted(in_dir.glob("*"))
    if not images:
        print(f"No images found in {in_dir}")
        return 1

    # Build estimator with DB nutrition if available
    estimator = None
    if _DB_AVAILABLE:
        try:
            conn = sqlite3.connect("second_brain.db")
            estimator = create_estimator_from_db(conn)
            print(f"Using DB-backed estimator with {len(estimator.food_names)} mapped food names")
        except Exception as e:
            print(f"DB estimator failed, using defaults: {e}")
            estimator = FoodCalorieEstimator()
    else:
        estimator = FoodCalorieEstimator()

    csv_path = out_dir / "results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "filename",
            "ref_object",
            "pixels_per_cm",
            "detected_food",
            "food_name",
            "confidence",
            "kcal",
            "weight_g",
            "protein_g",
            "fat_g",
            "carbs_g",
            "volume_cm3",
        ])

        for img_path in images:
            print(f"\nProcessing: {img_path.name}")
            img = cv2.imread(str(img_path))
            if img is None:
                print(f"  Could not read {img_path.name}")
                continue

            # Run estimator
            try:
                detections, ref_name = estimator.estimate_calories_with_ref(img)
            except Exception as e:
                print(f"  Estimator error: {e}")
                writer.writerow([img_path.name, "error", "", "", "", "", "", "", "", "", "", ""])
                continue

            if not detections:
                print(f"  No food detected (ref: {ref_name or 'none'})")
                writer.writerow([img_path.name, ref_name or "none", "", "", "", "", "", "", "", "", "", ""])
                # Still save annotated (will be blank)
                out_img = estimator.draw_results(img, [])
            else:
                print(f"  Found {len(detections)} items (ref: {ref_name or 'none'})")
                out_img = estimator.draw_results(img, detections)

                for d in detections:
                    writer.writerow([
                        img_path.name,
                        ref_name or "none",
                        f"{d.pixels_per_cm:.2f}",
                        d.name,
                        d.food_name or d.name,
                        f"{d.confidence:.3f}",
                        f"{d.estimated_kcal:.1f}",
                        f"{d.estimated_weight_grams:.1f}",
                        f"{d.estimated_macros.get('protein', 0):.1f}",
                        f"{d.estimated_macros.get('fat', 0):.1f}",
                        f"{d.estimated_macros.get('carbs', 0):.1f}",
                        f"{d.volume_cm3:.1f}",
                    ])

            # Save annotated
            out_path = out_dir / f"annotated_{img_path.name}"
            cv2.imwrite(str(out_path), out_img)
            print(f"  Saved: {out_path.name}")

    print(f"\nResults written to {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
