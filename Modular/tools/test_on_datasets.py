#!/usr/bin/env python3
"""Dataset testing framework for food calorie vision estimator.

Supports testing on Food-101, Nutrition5k, and custom datasets.
Computes detection accuracy, calorie estimation error, and generates reports.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from opencv_calorie_estimator import FoodCalorieEstimator, create_estimator_from_db


@dataclass
class GroundTruth:
    """Ground truth annotation for a test image."""
    image_path: str
    food_class: str
    bbox: tuple[int, int, int, int]  # x, y, w, h
    weight_grams: float
    kcal: float
    reference_object: str | None = None  # "credit_card", "plate", "coin"
    pixels_per_cm: float | None = None


@dataclass
class DetectionResult:
    """Result from running estimator on an image."""
    image_path: str
    detected: bool
    food_class: str
    food_name: str
    confidence: float
    bbox: tuple[int, int, int, int]
    estimated_kcal: float
    estimated_weight: float
    estimated_macros: dict
    volume_cm3: float
    pixels_per_cm: float
    ref_object: str | None
    processing_time_ms: float


@dataclass
class TestMetrics:
    """Aggregated test metrics."""
    total_images: int = 0
    detected_count: int = 0
    correct_class: int = 0

    # Calorie estimation
    kcal_errors: list = field(default_factory=list)
    weight_errors: list = field(default_factory=list)

    # Per-class breakdown
    per_class: dict = field(default_factory=dict)

    # Reference object detection
    ref_detected: int = 0
    ref_total: int = 0
    ref_ppcm_errors: list = field(default_factory=list)


class DatasetTester:
    """Main testing framework for food vision estimator."""

    def __init__(self, estimator: FoodCalorieEstimator | None = None,
                 output_dir: str = "test_results"):
        self.estimator = estimator or FoodCalorieEstimator()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.annotated_dir = self.output_dir / "annotated"
        self.annotated_dir.mkdir(parents=True, exist_ok=True)
        self.metrics = TestMetrics()

    def load_ground_truth(self, gt_file: str) -> list[GroundTruth]:
        """Load ground truth from JSON or CSV file."""
        gt_list = []
        path = Path(gt_file)

        if path.suffix == ".json":
            with open(path) as f:
                data = json.load(f)
            for item in data:
                gt_list.append(GroundTruth(
                    image_path=item["image_path"],
                    food_class=item["food_class"],
                    bbox=tuple(item["bbox"]),
                    weight_grams=item.get("weight_grams", 100),
                    kcal=item.get("kcal", 0),
                    reference_object=item.get("reference_object"),
                    pixels_per_cm=item.get("pixels_per_cm"),
                ))
        elif path.suffix == ".csv":
            with open(path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    gt_list.append(GroundTruth(
                        image_path=row["image_path"],
                        food_class=row["food_class"],
                        bbox=tuple(map(int, row["bbox"].split(";"))),
                        weight_grams=float(row.get("weight_grams", 100)),
                        kcal=float(row.get("kcal", 0)),
                        reference_object=row.get("reference_object") or None,
                        pixels_per_cm=float(row["pixels_per_cm"]) if row.get("pixels_per_cm") else None,
                    ))
        return gt_list

    def run_on_image(self, image_path: str, gt: GroundTruth | None = None) -> DetectionResult:
        """Run estimator on a single image."""
        start = time.time()
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")

        # Run estimator
        detections, ref_name = self.estimator.estimate_calories_with_ref(image)
        elapsed = (time.time() - start) * 1000

        if not detections:
            return DetectionResult(
                image_path=image_path,
                detected=False,
                food_class="",
                food_name="",
                confidence=0.0,
                bbox=(0, 0, 0, 0),
                estimated_kcal=0.0,
                estimated_weight=0.0,
                estimated_macros={},
                volume_cm3=0.0,
                pixels_per_cm=0.0,
                ref_object=ref_name,
                processing_time_ms=elapsed,
            )

        # Take highest confidence detection
        best = max(detections, key=lambda d: d.confidence)

        return DetectionResult(
            image_path=image_path,
            detected=True,
            food_class=best.name,
            food_name=best.food_name or best.name,
            confidence=best.confidence,
            bbox=best.bbox,
            estimated_kcal=best.estimated_kcal,
            estimated_weight=best.estimated_weight_grams,
            estimated_macros=best.estimated_macros,
            volume_cm3=best.volume_cm3,
            pixels_per_cm=best.pixels_per_cm,
            ref_object=ref_name,
            processing_time_ms=elapsed,
        )

    def evaluate(self, gt_list: list[GroundTruth], save_annotated: bool = True) -> TestMetrics:
        """Evaluate estimator on ground truth list."""
        self.metrics = TestMetrics()

        for gt in gt_list:
            self.metrics.total_images += 1
            try:
                result = self.run_on_image(gt.image_path, gt)
            except Exception as e:
                print(f"Error on {gt.image_path}: {e}")
                continue

            if result.detected:
                self.metrics.detected_count += 1

                # Class accuracy (simple string match)
                if result.food_class.lower() == gt.food_class.lower():
                    self.metrics.correct_class += 1

                # Calorie error (relative)
                if gt.kcal > 0:
                    kcal_error = abs(result.estimated_kcal - gt.kcal) / gt.kcal
                    self.metrics.kcal_errors.append(kcal_error)

                # Weight error
                if gt.weight_grams > 0:
                    weight_error = abs(result.estimated_weight - gt.weight_grams) / gt.weight_grams
                    self.metrics.weight_errors.append(weight_error)

                # Per-class tracking
                cls = gt.food_class.lower()
                if cls not in self.metrics.per_class:
                    self.metrics.per_class[cls] = {"total": 0, "correct": 0, "kcal_errors": []}
                self.metrics.per_class[cls]["total"] += 1
                if result.food_class.lower() == cls:
                    self.metrics.per_class[cls]["correct"] += 1
                if gt.kcal > 0:
                    self.metrics.per_class[cls]["kcal_errors"].append(
                        abs(result.estimated_kcal - gt.kcal) / gt.kcal
                    )

                # Reference object detection
                if gt.reference_object:
                    self.metrics.ref_total += 1
                    if result.ref_object == gt.reference_object:
                        self.metrics.ref_detected += 1
                    if gt.pixels_per_cm and result.pixels_per_cm > 0:
                        ppcm_error = abs(result.pixels_per_cm - gt.pixels_per_cm) / gt.pixels_per_cm
                        self.metrics.ref_ppcm_errors.append(ppcm_error)

                # Save annotated image
                if save_annotated:
                    self.save_annotated(gt.image_path, result, gt)
            else:
                print(f"No detection: {gt.image_path}")

        return self.metrics

    def save_annotated(self, image_path: str, result: DetectionResult, gt: GroundTruth | None = None):
        """Save annotated image with detection and ground truth overlay."""
        image = cv2.imread(image_path)
        if image is None:
            return

        # Draw detection
        if result.detected:
            x, y, w, h = result.bbox
            color = (0, 255, 0)  # Green for detection
            cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)
            label = f"DET: {result.food_name} ({result.confidence:.2f})"
            cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # Draw kcal
            kcal_label = f"~{result.estimated_kcal:.0f} kcal | {result.estimated_weight:.0f}g"
            cv2.putText(image, kcal_label, (x, y + h + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Draw ground truth if available
        if gt:
            x, y, w, h = gt.bbox
            color = (255, 0, 0)  # Blue for ground truth
            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
            label = f"GT: {gt.food_class}"
            cv2.putText(image, label, (x, y - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            if gt.kcal > 0:
                gt_label = f"GT: {gt.kcal:.0f} kcal | {gt.weight_grams:.0f}g"
                cv2.putText(image, gt_label, (x, y + h + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Add reference object info
        if result.ref_object:
            ref_text = f"Ref: {result.ref_object} ({result.pixels_per_cm:.1f} px/cm)"
            cv2.putText(image, ref_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        out_name = f"annotated_{Path(image_path).stem}.jpg"
        out_path = self.annotated_dir / out_name
        cv2.imwrite(str(out_path), image)

    def generate_report(self, output_file: str = "test_report.json") -> dict:
        """Generate comprehensive test report."""
        m = self.metrics
        report = {
            "summary": {
                "total_images": m.total_images,
                "detected": m.detected_count,
                "detection_rate": m.detected_count / max(1, m.total_images),
                "classification_accuracy": m.correct_class / max(1, m.detected_count),
            },
            "calorie_estimation": {
                "mean_relative_error": float(np.mean(m.kcal_errors)) if m.kcal_errors else 0,
                "median_relative_error": float(np.median(m.kcal_errors)) if m.kcal_errors else 0,
                "mape": float(np.mean(m.kcal_errors) * 100) if m.kcal_errors else 0,
            },
            "weight_estimation": {
                "mean_relative_error": float(np.mean(m.weight_errors)) if m.weight_errors else 0,
                "median_relative_error": float(np.median(m.weight_errors)) if m.weight_errors else 0,
            },
            "reference_object": {
                "detected": m.ref_detected,
                "total": m.ref_total,
                "detection_rate": m.ref_detected / max(1, m.ref_total),
                "mean_ppcm_error": float(np.mean(m.ref_ppcm_errors)) if m.ref_ppcm_errors else 0,
            },
            "per_class": {},
        }

        for cls, data in m.per_class.items():
            report["per_class"][cls] = {
                "total": data["total"],
                "correct": data["correct"],
                "accuracy": data["correct"] / max(1, data["total"]),
                "mean_kcal_error": float(np.mean(data["kcal_errors"])) if data["kcal_errors"] else 0,
            }

        # Save JSON report
        out_path = self.output_dir / output_file
        with open(out_path, "w") as f:
            json.dump(report, f, indent=2)

        # Save CSV summary
        csv_path = self.output_dir / "metrics_summary.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value"])
            writer.writerow(["total_images", m.total_images])
            writer.writerow(["detected", m.detected_count])
            writer.writerow(["detection_rate", f"{m.detected_count / max(1, m.total_images):.3f}"])
            writer.writerow(["classification_accuracy", f"{m.correct_class / max(1, m.detected_count):.3f}"])
            writer.writerow(["calorie_mape", f"{float(np.mean(m.kcal_errors) * 100) if m.kcal_errors else 0:.2f}%"])
            writer.writerow(["weight_mape", f"{float(np.mean(m.weight_errors) * 100) if m.weight_errors else 0:.2f}%"])
            writer.writerow(["ref_detection_rate", f"{m.ref_detected / max(1, m.ref_total):.3f}"])

        return report


def create_sample_ground_truth():
    """Create sample ground truth for our synthetic test images."""
    gt = [
        GroundTruth(
            image_path="samples/calorie_vision/input/test_card_only.jpg",
            food_class="rice",
            bbox=(260, 200, 120, 76),
            weight_grams=75,
            kcal=120,
            reference_object="credit_card",
            pixels_per_cm=14.37,
        ),
        GroundTruth(
            image_path="samples/calorie_vision/input/test_plate_card_veg.jpg",
            food_class="vegetable",
            bbox=(240, 180, 160, 120),
            weight_grams=120,
            kcal=30,
            reference_object="standard_plate",
            pixels_per_cm=11.55,
        ),
        GroundTruth(
            image_path="samples/calorie_vision/input/test_coin_only.jpg",
            food_class="potato",
            bbox=(292, 212, 56, 56),
            weight_grams=50,
            kcal=40,
            reference_object="coin_eu_2euro",
            pixels_per_cm=21.73,
        ),
        GroundTruth(
            image_path="samples/calorie_vision/input/test_plate_coin_meat.jpg",
            food_class="meat",
            bbox=(250, 190, 140, 100),
            weight_grams=150,
            kcal=375,
            reference_object="standard_plate",
            pixels_per_cm=11.89,
        ),
        GroundTruth(
            image_path="samples/calorie_vision/input/test_card_rice.jpg",
            food_class="rice",
            bbox=(270, 240, 180, 120),
            weight_grams=100,
            kcal=130,
            reference_object="credit_card",
            pixels_per_cm=14.37,
        ),
    ]
    return gt


def main():
    print("=" * 60)
    print("Food Calorie Vision - Dataset Testing Framework")
    print("=" * 60)

    # Create estimator with DB nutrition
    try:
        import sqlite3
        conn = sqlite3.connect("second_brain.db")
        estimator = create_estimator_from_db(conn)
        print(f"Using DB-backed estimator with {len(estimator.food_names)} food names")
    except Exception as e:
        print(f"DB failed, using defaults: {e}")
        estimator = FoodCalorieEstimator()

    # Create tester
    tester = DatasetTester(estimator, output_dir="test_results/dataset_eval")

    # Load ground truth
    gt_list = create_sample_ground_truth()
    print(f"Loaded {len(gt_list)} ground truth annotations")

    # Run evaluation
    print("\nRunning evaluation...")
    metrics = tester.evaluate(gt_list, save_annotated=True)

    # Generate report
    print("\nGenerating report...")
    tester.generate_report("dataset_eval_report.json")

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total images:          {metrics.total_images}")
    print(f"Detected:              {metrics.detected_count} ({metrics.detected_count/max(1,metrics.total_images)*100:.1f}%)")
    print(f"Classification acc:    {metrics.correct_class/max(1,metrics.detected_count)*100:.1f}%")
    print(f"Calorie MAPE:          {float(np.mean(metrics.kcal_errors)*100) if metrics.kcal_errors else 0:.1f}%")
    print(f"Weight MAPE:           {float(np.mean(metrics.weight_errors)*100) if metrics.weight_errors else 0:.1f}%")
    print(f"Ref detection rate:    {metrics.ref_detected}/{metrics.ref_total} ({metrics.ref_detected/max(1,metrics.ref_total)*100:.1f}%)")
    print(f"Mean ref ppcm error:   {float(np.mean(metrics.ref_ppcm_errors)*100) if metrics.ref_ppcm_errors else 0:.1f}%")

    print("\nPer-class breakdown:")
    for cls, data in metrics.per_class.items():
        print(f"  {cls:12s}: {data['correct']}/{data['total']} acc={data['correct']/data['total']*100:.1f}% kcal_err={np.mean(data['kcal_errors'])*100 if data['kcal_errors'] else 0:.1f}%")

    print("\nReport saved to: test_results/dataset_eval/dataset_eval_report.json")
    print("Annotated images:   test_results/dataset_eval/annotated/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
