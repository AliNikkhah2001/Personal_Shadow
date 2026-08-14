"""OpenCV calorie estimation engine for Mind Palace OS.

Pipeline: reference-object scale detection -> food segmentation -> food
classification -> volume estimation -> weight -> calories + macros.

Pure OpenCV/NumPy implementation with hooks for ML model integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import cv2
import numpy as np


@dataclass
class FoodDetection:
    """Represents a detected food item with nutrition estimates."""

    name: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, w, h
    estimated_weight_grams: float
    estimated_kcal: float
    estimated_macros: dict[str, float]  # protein, fat, carbs
    volume_cm3: float = 0.0
    pixels_per_cm: float = 0.0
    area_pixels: int = 0
    food_name: str = ""


@dataclass
class NutritionInfo:
    """Nutrition values per 100 g."""

    kcal: float
    protein: float
    fat: float
    carbs: float


# name -> (density g/cm3, average height cm, NutritionInfo per 100g)
_FOOD_PROFILE: dict[str, tuple[float, float, NutritionInfo]] = {
    "rice": (0.85, 2.0, NutritionInfo(130, 2.7, 0.3, 28.0)),
    "pasta": (0.90, 2.5, NutritionInfo(157, 5.8, 0.9, 30.8)),
    "bread": (0.35, 4.0, NutritionInfo(265, 8.5, 1.2, 53.0)),
    "meat": (1.05, 3.0, NutritionInfo(250, 26.0, 17.0, 0.0)),
    "chicken": (1.05, 3.0, NutritionInfo(165, 31.0, 3.6, 0.0)),
    "fish": (1.05, 3.0, NutritionInfo(206, 22.0, 12.0, 0.0)),
    "egg": (1.03, 3.5, NutritionInfo(155, 13.0, 11.0, 1.1)),
    "vegetable": (0.60, 2.5, NutritionInfo(25, 1.5, 0.2, 4.0)),
    "salad": (0.40, 3.0, NutritionInfo(15, 1.0, 0.2, 3.0)),
    "fruit": (0.85, 3.0, NutritionInfo(52, 0.3, 0.2, 14.0)),
    "tomato": (0.95, 2.0, NutritionInfo(18, 0.9, 0.2, 3.9)),
    "potato": (0.75, 2.5, NutritionInfo(77, 2.0, 0.1, 17.0)),
    "cheese": (1.05, 2.0, NutritionInfo(265, 18.0, 21.0, 1.5)),
    "yogurt": (1.02, 2.0, NutritionInfo(60, 3.5, 3.3, 4.0)),
    "stew": (1.00, 3.0, NutritionInfo(150, 8.5, 9.0, 7.5)),
    "soup": (1.00, 4.0, NutritionInfo(45, 2.0, 1.0, 6.0)),
    "mixed": (0.85, 2.5, NutritionInfo(150, 8.0, 6.0, 15.0)),
    "unknown": (0.85, 2.0, NutritionInfo(150, 8.0, 6.0, 15.0)),
}

# Persian keyword maps for lookups against the ingredients table.
# Composite dishes (stew, soup) are checked before vegetables, since names
# like "قورمه سبزی" contain vegetable keywords but are stews.
_PERSIAN_KEYWORDS: dict[str, list[str]] = {
    "rice": ["برنج", "چلو", "کته"],
    "stew": ["خورشت", "خورش", "قورمه", "قیمه", "فسنجان"],
    "soup": ["سوپ", "آش"],
    "pasta": ["ماکارونی", "پاستا"],
    "bread": ["نان", "بربری", "سنگک", "تافتون"],
    "meat": ["گوشت", "کباب", "جوجه", "مرغ"],
    "chicken": ["مرغ", "جوجه"],
    "fish": ["ماهی", "قزل"],
    "egg": ["تخم", "املت"],
    "vegetable": ["سبزی", "کاهو", "سالاد", "خیار", "گوجه"],
    "salad": ["سالاد", "شیرازی"],
    "fruit": ["میوه", "سیب", "موز", "پرتقال"],
    "tomato": ["گوجه", "رب"],
    "potato": ["سیب زمینی", "سیب‌زمینی"],
    "cheese": ["پنیر"],
    "yogurt": ["ماست"],
    "mixed": ["مخلوط"],
}


class FoodCalorieEstimator:
    """Estimates calories from food images using computer vision."""

    # Reference object sizes in cm: (width, height) or (diameter, diameter)
    REFERENCE_OBJECTS: ClassVar[dict[str, tuple[float, float]]] = {
        "credit_card": (8.56, 5.40),
        "coin_us_quarter": (2.43, 2.43),
        "coin_eu_2euro": (2.58, 2.58),
        "standard_plate": (26.0, 26.0),
    }

    # Canonical display names per detected food class
    DEFAULT_FOOD_NAMES: ClassVar[dict[str, str]] = {
        "rice": "Rice",
        "pasta": "Pasta",
        "bread": "Bread",
        "meat": "Meat",
        "chicken": "Chicken",
        "fish": "Fish",
        "egg": "Egg",
        "vegetable": "Vegetable",
        "salad": "Salad",
        "fruit": "Fruit",
        "tomato": "Tomato",
        "potato": "Potato",
        "cheese": "Cheese",
        "yogurt": "Yogurt",
        "stew": "Stew",
        "soup": "Soup",
        "mixed": "Mixed Food",
        "unknown": "Unknown",
    }

    FOOD_DENSITIES: ClassVar[dict[str, float]] = {k: v[0] for k, v in _FOOD_PROFILE.items()}

    _HEIGHTS_CM: ClassVar[dict[str, float]] = {k: v[1] for k, v in _FOOD_PROFILE.items()}

    DEFAULT_NUTRITION: ClassVar[dict[str, NutritionInfo]] = {k: v[2] for k, v in _FOOD_PROFILE.items()}

    # HSV ranges used for food segmentation
    _FOOD_HSV_RANGES: ClassVar[list[tuple[tuple[int, int, int], tuple[int, int, int]]]] = [
        ((10, 50, 50), (25, 255, 200)),  # brown / cooked meats
        ((35, 50, 50), (85, 255, 255)),  # green vegetables
        ((0, 50, 50), (15, 255, 255)),  # red / orange
        ((160, 50, 50), (180, 255, 255)),  # purple-red
        ((15, 50, 50), (35, 255, 255)),  # yellow
        ((0, 0, 180), (180, 35, 255)),  # white foods
    ]

    def __init__(self, nutrition_db: dict[str, NutritionInfo] | None = None, food_names: dict[str, str] | None = None):
        self.nutrition_db: dict[str, NutritionInfo] = nutrition_db or dict(self.DEFAULT_NUTRITION)
        self.food_names: dict[str, str] = dict(self.DEFAULT_FOOD_NAMES)
        if food_names:
            self.food_names.update(food_names)
        self.detector: Any = None
        self.segmenter: Any = None
        self.default_pixels_per_cm = 8.0

    def resolve_food_name(self, name: str) -> str:
        """Map a detected class to a concrete food name (incl. DB-sourced)."""
        return self.food_names.get(name, name)

    # ------------------------------------------------------------------ models

    def load_models(self, detection_model_path: str | None = None, segmentation_model_path: str | None = None):
        """Hook for loading ML models (ONNX/TFLite). Falls back to CV heuristics."""
        if detection_model_path:
            try:
                import onnxruntime as ort  # type: ignore[import-not-found]

                self.detector = ort.InferenceSession(detection_model_path)
            except (ImportError, OSError):
                self.detector = None
        if segmentation_model_path:
            try:
                import onnxruntime as ort  # type: ignore[import-not-found]

                self.segmenter = ort.InferenceSession(segmentation_model_path)
            except (ImportError, OSError):
                self.segmenter = None

    # ------------------------------------------------------------- scale / ref

    def detect_reference_object(self, image: np.ndarray) -> tuple[float, str] | None:
        """Detect a reference object and return (pixels_per_cm, object_name).

        Tries: credit card (aspect 1.586 white rectangle), plate (large
        ellipse/circle), ArUco marker (if contributed modules available).
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        img_area = image.shape[0] * image.shape[1]
        card_w_cm, card_h_cm = self.REFERENCE_OBJECTS["credit_card"]
        best: tuple[float, str] | None = None
        best_score = 0.0

        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:12]:
            area = cv2.contourArea(cnt)
            if area < img_area * 0.002:  # smaller than a coin at close range
                continue

            # A plate is a light-colored, roughly circular boundary, not a
            # solid colored blob. Check the interior brightness before trusting
            # the ellipse fit.
            mask = np.zeros(image.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            mean_val = float(cv2.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), mask=mask)[0])
            is_plate_like = mean_val > 170 and 0.8 < area / cv2.contourArea(cv2.convexHull(cnt)) < 1.0

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4:
                # Quadrilateral -> candidate credit card, not a plate
                _x, _y, w, h = cv2.boundingRect(cnt)
                if w < 10 or h < 10:
                    continue
                aspect = w / h if w > h else h / w
                ratio_error = abs(aspect - card_w_cm / card_h_cm) / (card_w_cm / card_h_cm)
                if ratio_error < 0.35:
                    score = area / img_area
                    if score > best_score:
                        best_score = score
                        long_side = max(w, h)
                        ppcm = long_side / card_w_cm
                        best = (ppcm, "credit_card")
                continue

            # Plate detection: large, bright ellipse contour
            if is_plate_like and len(cnt) >= 5:
                ellipse = cv2.fitEllipse(cnt)
                (_cx, _cy), (d1, d2), _ = ellipse
                if d1 < 20 or d2 < 20:
                    continue
                if 0.8 < d1 / d2 < 1.25 and d1 > image.shape[0] * 0.25:
                    ppcm = (d1 + d2) / 2 / self.REFERENCE_OBJECTS["standard_plate"][0]
                    if 3.0 < ppcm < 60.0:
                        return (ppcm, "standard_plate")

            # Coin detection (small, bright, near-circular contour) for close-ups
            if is_plate_like and 5 <= len(cnt) <= 200:
                ellipse = cv2.fitEllipse(cnt)
                (_cx, _cy), (d1, d2), _ = ellipse
                if d1 < 12 or d2 < 12:
                    continue
                aspect = max(d1, d2) / min(d1, d2)
                if 1.0 <= aspect < 1.35 and 0.08 < max(d1, d2) / image.shape[1] < 0.45:
                    mean_d = (d1 + d2) / 2
                    for coin_name, (cd, _ch) in (
                        ("coin_eu_2euro", self.REFERENCE_OBJECTS["coin_eu_2euro"]),
                        ("coin_us_quarter", self.REFERENCE_OBJECTS["coin_us_quarter"]),
                    ):
                        ppcm = mean_d / cd
                        if 3.0 < ppcm < 80.0:
                            return (ppcm, coin_name)

        if best is not None:
            return best
        return None

    # ------------------------------------------------------------ segmentation

    def segment_food(self, image: np.ndarray) -> list[tuple[np.ndarray, tuple[int, int, int, int]]]:
        """Segment food blobs -> list of (mask, bbox)."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        combined = np.zeros(image.shape[:2], dtype=np.uint8)
        for lower, upper in self._FOOD_HSV_RANGES:
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            combined = cv2.bitwise_or(combined, mask)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = max(2000, image.shape[0] * image.shape[1] * 0.005)
        max_area = image.shape[0] * image.shape[1] * 0.5

        results: list[tuple[np.ndarray, tuple[int, int, int, int]]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (min_area < area < max_area):
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            aspect = w / h if h > 0 else 1.0
            if area <= 0 or not (0.2 < aspect < 5.0):
                continue
            mask = np.zeros(image.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            results.append((mask, (int(x), int(y), int(w), int(h))))

        results.sort(key=lambda item: np.count_nonzero(item[0]), reverse=True)
        return results[:10]

    # ------------------------------------------------------------ classification

    def classify_food(self, image: np.ndarray, bbox: tuple[int, int, int, int]) -> tuple[str, float]:
        """Classify food from ROI HSV statistics -> (name, confidence)."""
        x, y, w, h = bbox
        roi = image[y : y + h, x : x + w]
        if roi.size == 0:
            return "unknown", 0.0

        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        avg_hue = float(np.mean(hsv_roi[:, :, 0]))
        avg_sat = float(np.mean(hsv_roi[:, :, 1]))
        avg_val = float(np.mean(hsv_roi[:, :, 2]))

        if avg_sat < 35:
            name = "rice" if avg_val > 190 else "potato"
        elif avg_hue <= 8 or avg_hue >= 172:
            name = "tomato" if avg_sat > 140 else "meat"
        elif 8 < avg_hue <= 22:
            name = "meat" if avg_sat < 120 else "stew"
        elif 22 < avg_hue <= 38:
            name = "cheese" if avg_val > 200 else "potato"
        elif 38 < avg_hue <= 85:
            name = "vegetable"
        elif 85 < avg_hue <= 140:
            name = "fruit"
        else:
            name = "mixed"

        distinctiveness = min(1.0, avg_sat / 255.0 * 0.6 + 0.4)
        confidence = max(0.35, min(0.95, distinctiveness))
        return name, confidence

    # ------------------------------------------------------------ volume / weight

    def estimate_food_volume(self, mask: np.ndarray, pixels_per_cm: float, name: str) -> float:
        """Estimate volume in cm³ from mask area and per-class height."""
        area_pixels = float(np.count_nonzero(mask))
        area_cm2 = area_pixels / (pixels_per_cm**2)
        height_cm = self._HEIGHTS_CM.get(name, self._HEIGHTS_CM["unknown"])
        return area_cm2 * height_cm

    def nutrition_for(self, name: str) -> NutritionInfo:
        """Look up nutrition per 100 g, falling back to defaults."""
        info = self.nutrition_db.get(name)
        if info is None:
            info = self.DEFAULT_NUTRITION.get(name, self.DEFAULT_NUTRITION["unknown"])
        return info

    # ------------------------------------------------------------------ pipeline

    def estimate_calories(self, image: np.ndarray) -> list[FoodDetection]:
        """Main pipeline: scale -> segment -> classify -> volume -> calories."""
        ref_result = self.detect_reference_object(image)
        if ref_result is None:
            pixels_per_cm = self.default_pixels_per_cm
        else:
            pixels_per_cm, _ref_name = ref_result

        results: list[FoodDetection] = []
        for mask, bbox in self.segment_food(image):
            _x, _y, _w, _h = bbox
            name, confidence = self.classify_food(image, bbox)

            volume_cm3 = self.estimate_food_volume(mask, pixels_per_cm, name)
            density = self.FOOD_DENSITIES.get(name, self.FOOD_DENSITIES["unknown"])
            weight_grams = volume_cm3 * density

            info = self.nutrition_for(name)
            factor = weight_grams / 100.0
            results.append(
                FoodDetection(
                    name=name,
                    confidence=confidence,
                    bbox=bbox,
                    estimated_weight_grams=round(weight_grams, 1),
                    estimated_kcal=round(info.kcal * factor, 1),
                    estimated_macros={
                        "protein": round(info.protein * factor, 1),
                        "fat": round(info.fat * factor, 1),
                        "carbs": round(info.carbs * factor, 1),
                    },
                    volume_cm3=round(volume_cm3, 1),
                    pixels_per_cm=round(pixels_per_cm, 2),
                    area_pixels=int(np.count_nonzero(mask)),
                    food_name=self.resolve_food_name(name),
                )
            )

        results.sort(key=lambda d: d.confidence, reverse=True)
        return results

    def estimate_calories_with_ref(self, image: np.ndarray) -> tuple[list[FoodDetection], str | None]:
        """Pipeline result including which reference object was used (if any)."""
        ref_result = self.detect_reference_object(image)
        ref_name = None
        if ref_result is not None:
            _, ref_name = ref_result
            self.default_pixels_per_cm = ref_result[0]
        return self.estimate_calories(image), ref_name

    def process_image_file(self, image_path: str) -> list[FoodDetection]:
        """Process an image file and return calorie estimates."""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
        return self.estimate_calories(image)

    def draw_results(self, image: np.ndarray, detections: list[FoodDetection]) -> np.ndarray:
        """Draw bounding boxes and nutrition labels on the image."""
        output = image.copy()
        for det in detections:
            x, y, w, h = det.bbox
            cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 0), 3)
            label = f"{det.food_name or det.name}: ~{det.estimated_kcal:.0f} kcal ({det.estimated_weight_grams:.0f}g)"
            sub = f"vol {det.volume_cm3:.0f} cm3 | {det.confidence:.0%}"
            text_y = y - 10 if y > 44 else y + h + 44
            bar_y1, bar_y2 = text_y - 26, text_y + 24
            bar_x1, bar_x2 = x + 3, x + 3 + max(200, len(label) * 9)
            bar = output[bar_y1:bar_y2, bar_x1:bar_x2]
            output[bar_y1:bar_y2, bar_x1:bar_x2] = (bar * 0.35).astype(np.uint8)
            cv2.putText(output, label, (x + 8, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(output, sub, (x + 8, text_y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 255, 200), 1)
        return output


def _avg_matching_rows(
    rows: list[tuple[str, float, float, float, float]],
) -> NutritionInfo | None:
    if not rows:
        return None
    n = len(rows)
    return NutritionInfo(
        kcal=sum(r[1] for r in rows) / n,
        protein=sum(r[2] for r in rows) / n,
        fat=sum(r[3] for r in rows) / n,
        carbs=sum(r[4] for r in rows) / n,
    )


def build_nutrition_db_from_rows(
    rows: list[tuple[str, float, float, float, float]],
) -> tuple[dict[str, NutritionInfo], dict[str, str]]:
    """Map ingredient rows (name, kcal, protein, fat, carbs) to food classes.

    Matches Persian ingredient names against per-class keyword lists.
    Returns (nutrition_db, food_names), where food_names maps each class to
    the most representative ingredient name found.
    """
    by_class: dict[str, list[tuple[str, float, float, float, float]]] = {}
    for row in rows:
        name = str(row[0] or "").strip()
        for food_class, keywords in _PERSIAN_KEYWORDS.items():
            if any(kw in name for kw in keywords):
                by_class.setdefault(food_class, []).append(row)
                break

    nutrition_db: dict[str, NutritionInfo] = {}
    food_names: dict[str, str] = {}
    for food_class, class_rows in by_class.items():
        info = _avg_matching_rows(class_rows)
        if info is not None:
            nutrition_db[food_class] = info
            food_names[food_class] = class_rows[0][0]
    return nutrition_db, food_names


def create_estimator_from_db(db_connection) -> FoodCalorieEstimator:
    """Create an estimator seeded with nutrition data from the ingredients table."""
    cursor = db_connection.cursor()
    try:
        cursor.execute("SELECT name, kcal, protein, fat, carbs FROM ingredients")
        rows = cursor.fetchall()
    except Exception:
        rows = []
    nutrition_db, food_names = build_nutrition_db_from_rows(rows)
    return FoodCalorieEstimator(nutrition_db or None, food_names)
