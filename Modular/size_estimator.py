"""
Size Estimation Module for Calorie Vision System

Integrates MiDaS depth estimation with reference object detection
to provide metric depth, volume, and weight estimation for food items.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import cv2
import numpy as np

try:
    import importlib.util
    TORCH_AVAILABLE = importlib.util.find_spec('torch') is not None
    if TORCH_AVAILABLE:
        import torch
        import torch.nn.functional
        from torchvision import transforms
    else:
        torch = None  # type: ignore
        F = None  # type: ignore
        transforms = None  # type: ignore
except ImportError:
    TORCH_AVAILABLE = False
    torch = None  # type: ignore
    F = None  # type: ignore
    transforms = None  # type: ignore

from opencv_calorie_estimator import FoodCalorieEstimator, FoodDetection


@dataclass
class SizeEstimation:
    """Size estimation result for a detected food item."""
    food_name: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, w, h

    # 2D measurements
    area_pixels: int
    bbox_area_pixels: int

    # 3D measurements (metric)
    depth_mean: float          # Mean depth in meters
    depth_median: float        # Median depth in meters
    volume_cm3: float          # Estimated volume in cm³
    weight_grams: float        # Estimated weight in grams

    # Nutrition estimates
    estimated_kcal: float
    estimated_macros: dict[str, float]  # protein, fat, carbs

    # Reference object info
    reference_object: str | None = None
    pixels_per_cm: float = 0.0

    # Quality metrics
    depth_std: float = 0.0


class SizeEstimator:
    """
    Size estimator using MiDaS depth estimation + reference object calibration.
    """

    # Reference object sizes in cm
    REFERENCE_OBJECTS: ClassVar[dict[str, tuple[float, float]]] = {
        "credit_card": (8.56, 5.40),      # width, height in cm
        "coin_us_quarter": (2.43, 2.43),  # diameter in cm
        "coin_eu_2euro": (2.58, 2.58),
        "a4_paper": (29.7, 21.0),         # width, height in cm
        "standard_plate": (26.0, 26.0),   # diameter in cm
        "us_dollar": (15.6, 6.6),         # width, height in cm
    }

    # Food density (g/cm³) for volume-to-weight conversion
    FOOD_DENSITIES: ClassVar[dict[str, float]] = {
        "rice": 0.85,
        "pasta": 0.90,
        "bread": 0.35,
        "meat": 1.05,
        "chicken": 1.05,
        "fish": 1.05,
        "egg": 1.03,
        "vegetable": 0.60,
        "salad": 0.40,
        "fruit": 0.85,
        "tomato": 0.95,
        "potato": 0.75,
        "cheese": 1.05,
        "yogurt": 1.02,
        "stew": 1.00,
        "soup": 1.00,
        "burger": 0.90,
        "pizza": 0.70,
        "default": 0.85,
    }

    # Food height estimates (cm) for volume estimation from 2D area
    FOOD_HEIGHTS: ClassVar[dict[str, float]] = {
        "rice": 2.0,
        "pasta": 2.5,
        "bread": 4.0,
        "meat": 3.0,
        "chicken": 3.0,
        "fish": 3.0,
        "egg": 3.5,
        "vegetable": 2.5,
        "salad": 3.0,
        "fruit": 3.0,
        "tomato": 2.0,
        "potato": 2.5,
        "cheese": 2.0,
        "yogurt": 2.0,
        "stew": 3.0,
        "soup": 4.0,
        "burger": 3.0,
        "pizza": 2.0,
        "default": 2.5,
    }

    def __init__(self, nutrition_db: dict | None = None, device: str = "cpu"):
        self.nutrition_db = nutrition_db or {}
        self.device = device
        self.midas = None
        self.midas_transform = None
        self.food_estimator = FoodCalorieEstimator(nutrition_db)

        # Load MiDaS model
        self._load_midas()

        # Reference object detector (from opencv_calorie_estimator)
        self.food_estimator = FoodCalorieEstimator(nutrition_db)

    def _load_midas(self):
        """Load MiDaS depth estimation model."""
        try:
            import os

            import torch
            os.environ["TORCH_HUB_TRUST_REPO"] = "1"
            self.midas = torch.hub.load("intel-isl/MiDaS", "MiDaS", trust_repo=True)
            self.midas.eval()

            # Setup transforms
            import torchvision.transforms as transforms
            self.midas_transform = transforms.Compose([
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])
            print("MiDaS loaded successfully")
        except Exception as e:
            print(f"Warning: Could not load MiDaS: {e}")
            self.midas = None

    def estimate_depth(self, image: np.ndarray) -> np.ndarray:
        """
        Estimate depth map using MiDaS.

        Args:
            image: Input image (BGR format)
        Returns:
            Depth map (same size as input image, relative depth values)
        """
        if self.midas is None:
            return np.zeros(image.shape[:2], dtype=np.float32)

        import torch
        import torchvision.transforms as transforms

        # Convert BGR to RGB
        h, w = image.shape[:2]

        # Resize to multiple of 32, max 384px
        scale = min(384 / max(h, w), 1.0)
        new_h, new_w = int(h * scale), int(w * scale)
        new_h = ((new_h + 31) // 32) * 32
        new_w = ((new_w + 31) // 32) * 32

        img_resized = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), (new_w, new_h))

        # Preprocess
        input_tensor = transforms.ToTensor()(img_resized).unsqueeze(0)
        input_tensor = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])(input_tensor)

        # Run inference

        with torch.no_grad():
            prediction = self.midas(input_tensor)

            # Resize back to original size
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=(h, w),
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        depth_map = prediction.cpu().numpy()
        return depth_map

    def detect_reference_objects(self, image: np.ndarray) -> list[tuple[str, float, tuple]]:
        """
        Detect reference objects in image and return (name, pixels_per_cm, bbox).
        Uses the reference object detection from opencv_calorie_estimator.
        """
        # Use the reference object detection from FoodCalorieEstimator
        ref_result = self.food_estimator.detect_reference_object(image)
        if ref_result:
            pixels_per_cm, ref_name = ref_result
            # For now return simplified result
            return [(ref_name, pixels_per_cm, (0, 0, 0, 0))]
        return []

    def estimate_size(self, image: np.ndarray, detection: FoodDetection,
                      depth_map: np.ndarray = None) -> SizeEstimation:
        """
        Estimate size, volume, weight, and nutrition for a detected food item.
        """
        if depth_map is None:
            depth_map = self.estimate_depth(image)

        x, y, w, h = detection.bbox
        bbox_area = w * h

        # Get depth statistics for the food region
        y1, y2 = max(0, y), min(image.shape[0], y + h)
        x1, x2 = max(0, x), min(image.shape[1], x + w)

        roi_depth = depth_map[y1:y2, x1:x2]
        if roi_depth.size == 0:
            roi_depth = depth_map

        # Depth statistics (relative depth from MiDaS)
        depth_std = float(np.std(roi_depth))

        # Get reference object for metric conversion
        ref_objects = self.detect_reference_objects(image)
        pixels_per_cm = 8.0  # Default fallback
        ref_name = None

        if ref_objects:
            pixels_per_cm, ref_name = ref_objects[0][1], ref_objects[0][0]
        else:
            # Try to get from food estimator
            ref_result = self.food_estimator.detect_reference_object(image)
            if ref_result:
                pixels_per_cm, ref_name = ref_result

        # For now, use pixels_per_cm for area conversion
        # Estimate 2D area in cm²
        roi_mask = np.zeros(depth_map.shape[:2], dtype=np.uint8)
        x, y, w, h = detection.bbox
        cv2.rectangle(roi_mask, (x, y), (x + w, y + h), 255, -1)

        # Get depth values for the food region
        area_pixels = w * h
        area_cm2 = area_pixels / (pixels_per_cm ** 2) if pixels_per_cm > 0 else 0

        # Estimate volume using food-specific height
        food_class = detection.name.lower()
        height_cm = self.FOOD_HEIGHTS.get(food_class, self.FOOD_HEIGHTS["default"])
        volume_cm3 = area_cm2 * height_cm

        # Estimate weight
        density = self.FOOD_DENSITIES.get(food_class, self.FOOD_DENSITIES["default"])
        weight_grams = volume_cm3 * density

        # Get nutrition info
        nutrition = self.food_estimator.nutrition_for(food_class)
        factor = weight_grams / 100.0
        estimated_kcal = nutrition.kcal * factor
        estimated_macros = {
            "protein": nutrition.protein * factor,
            "fat": nutrition.fat * factor,
            "carbs": nutrition.carbs * factor,
        }

        return SizeEstimation(
            food_name=detection.food_name or detection.name,
            confidence=detection.confidence,
            bbox=detection.bbox,
            area_pixels=area_pixels,
            bbox_area_pixels=bbox_area,
            depth_mean=float(np.mean(depth_map)),
            depth_median=float(np.median(depth_map)),
            volume_cm3=round(volume_cm3, 1),
            weight_grams=round(weight_grams, 1),
            estimated_kcal=round(estimated_kcal, 1),
            estimated_macros=estimated_macros,
            reference_object=ref_name,
            pixels_per_cm=pixels_per_cm,
            depth_std=depth_std,
        )


def create_size_estimator_from_db(db_connection) -> SizeEstimator:
    """Create size estimator with nutrition data from database."""
    cursor = db_connection.cursor()
    try:
        cursor.execute("SELECT name, kcal, protein, fat, carbs FROM ingredients")
        rows = cursor.fetchall()
    except Exception:
        rows = []

    nutrition_db = {}
    for row in rows:
        name = str(row[0] or "").strip()
        nutrition_db[name.lower()] = {
            "kcal_per_100g": row[1],
            "protein_per_100g": row[2],
            "fat_per_100g": row[3],
            "carbs_per_100g": row[4],
        }

    return SizeEstimator(nutrition_db)


# Convenience function for easy use
def estimate_food_size(image_path: str, db_path: str = "second_brain.db") -> list[SizeEstimation]:
    """
    Convenience function to estimate food size from an image file.

    Args:
        image_path: Path to image file
        db_path: Path to SQLite database with ingredients

    Returns:
        List of SizeEstimation objects
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    estimator = create_size_estimator_from_db(conn)

    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")

    # Detect food
    detections = estimator.food_estimator.estimate_calories(image)
    detections = estimator.food_estimator.estimator.estimate_calories(image)

    # Estimate depth
    depth_map = estimator.estimate_depth(image)

    # Estimate size for each detection
    results = []
    for det in detections:
        size_est = estimator.estimate_size(image, det, depth_map)
        results.append(size_est)

    return results


# Add missing imports at top

# Re-export
__all__ = [
    "SizeEstimation",
    "SizeEstimator",
    "create_size_estimator_from_db",
    "estimate_food_size",
]
