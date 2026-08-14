"""OpenCV calorie estimation engine for Mind Palace OS.

Pipeline: reference-object scale detection -> food segmentation -> food
classification -> volume estimation -> weight -> calories + macros.

Pure OpenCV/NumPy implementation with hooks for ML model integration.
"""

from __future__ import annotations

import contextlib
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

    # HSV ranges used for food segmentation - TIGHTENED to exclude skin tones
    # Skin tones typically: H 0-20, S 20-150, V 50-255
    # We exclude low-saturation warm colors that match skin
    _FOOD_HSV_RANGES: ClassVar[list[tuple[tuple[int, int, int], tuple[int, int, int]]]] = [
        ((10, 100, 50), (25, 255, 200)),   # brown / cooked meats - higher saturation
        ((35, 80, 50), (85, 255, 255)),    # green vegetables
        ((0, 120, 50), (15, 255, 255)),    # red / orange - higher saturation
        ((160, 120, 50), (180, 255, 255)), # purple-red
        ((15, 100, 50), (35, 255, 255)),   # yellow - higher saturation
        ((0, 0, 220), (180, 25, 255)),     # white foods - higher value threshold
    ]

    # Explicit skin-tone exclusion ranges (will be subtracted from food mask)
    _SKIN_HSV_RANGES: ClassVar[list[tuple[tuple[int, int, int], tuple[int, int, int]]]] = [
        ((0, 15, 40), (30, 160, 255)),     # typical skin tones
        ((0, 10, 80), (35, 100, 255)),     # lighter skin tones
        ((0, 5, 150), (20, 60, 255)),      # very pale skin
    ]

    def __init__(self, nutrition_db: dict[str, NutritionInfo] | None = None, food_names: dict[str, str] | None = None):
        self.nutrition_db: dict[str, NutritionInfo] = nutrition_db or dict(self.DEFAULT_NUTRITION)
        self.food_names: dict[str, str] = dict(self.DEFAULT_FOOD_NAMES)
        if food_names:
            self.food_names.update(food_names)
        self.detector: Any = None
        self.segmenter: Any = None
        self.default_pixels_per_cm = 8.0

        # Load face detector for exclusion
        self._face_cascade = None
        with contextlib.suppress(Exception):
            self._face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")

        # Load eye cascade for additional face confirmation
        self._eye_cascade = None
        with contextlib.suppress(Exception):
            self._eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

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

        Tries multiple strategies:
        1. Credit card: bright white/light rectangle with aspect ~1.586
        2. Plate: large light-colored circular/elliptical region
        3. Coin: small bright circular region
        4. A4 paper: large white rectangle with aspect ~1.414
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        img_area = image.shape[0] * image.shape[1]
        _img_h, _img_w = image.shape[:2]

        _best_result = None
        _best_score = 0.0

        # Strategy 1: Detect credit card - bright rectangular region with correct aspect ratio
        # Look for light-colored rectangular regions
        white_mask = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 50, 255]))
        # Also try light gray
        light_mask = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 60, 255]))
        combined_mask = cv2.bitwise_or(white_mask, light_mask)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        img_area = image.shape[0] * image.shape[1]
        card_w_cm, card_h_cm = self.REFERENCE_OBJECTS["credit_card"]
        card_aspect = card_w_cm / card_h_cm  # ~1.586

        best_card = None
        best_card_score = 0.0

        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:20]:
            area = cv2.contourArea(cnt)
            if area < img_area * 0.0005:  # Lower threshold for cards
                continue

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(cnt)
                if w < 15 or h < 15:
                    continue
                aspect = w / h if w > h else h / w
                ratio_error = abs(aspect - card_aspect) / card_aspect

                # Check if region is bright
                mask = np.zeros(image.shape[:2], dtype=np.uint8)
                cv2.drawContours(mask, [cnt], -1, 255, -1)
                mean_val = float(cv2.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), mask=mask)[0])

                if ratio_error < 0.4 and mean_val > 150:  # Bright enough
                    score = area / img_area
                    if score > best_card_score:
                        best_card_score = score
                        long_side = max(w, h)
                        ppcm = long_side / card_w_cm
                        if 5.0 < ppcm < 50.0:  # Reasonable range
                            best_card = (ppcm, "credit_card")

        # Strategy 2: Detect plate - large bright circular/elliptical region
        # Use Hough circles on bright regions
        bright_mask = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 60, 255]))
        bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
        bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))

        # Find large circular contours
        plate_contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        _best_plate = None
        for cnt in sorted(plate_contours, key=cv2.contourArea, reverse=True)[:10]:
            area = cv2.contourArea(cnt)
            if area < img_area * 0.02:  # Plate should be at least 2% of image
                continue

            if len(cnt) >= 5:
                ellipse = cv2.fitEllipse(cnt)
                (_cx, _cy), (d1, d2), _angle = ellipse

                # Check if it's roughly circular and large enough
                if 0.7 < d1 / d2 < 1.3 and d1 > image.shape[0] * 0.15:
                    # Check brightness
                    mask = np.zeros(image.shape[:2], dtype=np.uint8)
                    cv2.drawContours(mask, [cnt], -1, 255, -1)
                    mean_val = float(cv2.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), mask=mask)[0])

                    if mean_val > 150:
                        ppcm = (d1 + d2) / 2 / self.REFERENCE_OBJECTS["standard_plate"][0]
                        if 3.0 < ppcm < 60.0:
                            return (ppcm, "standard_plate")

        # Strategy 3: Coin detection - small bright circles
        # Use Hough circles on bright regions
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=50,
                                   param1=50, param2=30, minRadius=10, maxRadius=80)

        if circles is not None:
            circles = np.uint16(np.around(circles))
            for circle in circles[0, :]:
                x, y, r = circle
                # Check if bright
                mask = np.zeros(image.shape[:2], dtype=np.uint8)
                cv2.circle(mask, (x, y), r, 255, -1)
                mean_val = float(cv2.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), mask=mask)[0])

                if mean_val > 150:
                    for coin_name, (cd, _ch) in (
                        ("coin_eu_2euro", self.REFERENCE_OBJECTS["coin_eu_2euro"]),
                        ("coin_us_quarter", self.REFERENCE_OBJECTS["coin_us_quarter"]),
                    ):
                        ppcm = (2 * r) / cd
                        if 3.0 < ppcm < 80.0:
                            return (ppcm, coin_name)

        # Strategy 4: A4 paper - large white rectangle with aspect ~1.414
        # (Can be added if needed)

        # Fallback: Use the best card detection if found
        if best_card:
            return best_card

        return None

# ------------------------------------------------------------ segmentation


    # ------------------------------------------------------------ segmentation

    def _get_face_mask(self, image: np.ndarray) -> np.ndarray:
        """Create a mask of face regions to exclude from food detection."""
        face_mask = np.zeros(image.shape[:2], dtype=np.uint8)
        if self._face_cascade is None:
            return face_mask

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

        for (x, y, w, h) in faces:
            # Expand face region slightly to cover hair/neck
            pad = int(max(w, h) * 0.3)
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(image.shape[1], x + w + pad)
            y2 = min(image.shape[0], y + h + pad)
            cv2.rectangle(face_mask, (x1, y1), (x2, y2), 255, -1)

        return face_mask

    def _get_reference_object_mask(self, image: np.ndarray) -> np.ndarray:
        """Create a mask of reference objects (card, plate, coin) to exclude from food detection."""
        ref_mask = np.zeros(image.shape[:2], dtype=np.uint8)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        img_area = image.shape[0] * image.shape[1]
        card_w_cm, card_h_cm = self.REFERENCE_OBJECTS["credit_card"]

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < img_area * 0.002:
                continue

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

            # Credit card: quadrilateral with correct aspect ratio AND light color
            if len(approx) == 4:
                _x, _y, w, h = cv2.boundingRect(cnt)
                if w < 10 or h < 10:
                    continue
                aspect = w / h if w > h else h / w
                ratio_error = abs(aspect - card_w_cm / card_h_cm) / (card_w_cm / card_h_cm)
                if ratio_error < 0.35:
                    # Credit cards are typically light-colored (white/cream)
                    mask = np.zeros(image.shape[:2], dtype=np.uint8)
                    cv2.drawContours(mask, [cnt], -1, 255, -1)
                    mean_val = float(cv2.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), mask=mask)[0])
                    if mean_val > 180:  # Card must be bright
                        cv2.drawContours(ref_mask, [cnt], -1, 255, -1)
                    continue

            # Plate: large bright ellipse
            if len(cnt) >= 5:
                ellipse = cv2.fitEllipse(cnt)
                (_cx, _cy), (d1, d2), _ = ellipse
                if d1 < 20 or d2 < 20:
                    continue
                # Check brightness
                mask = np.zeros(image.shape[:2], dtype=np.uint8)
                cv2.drawContours(mask, [cnt], -1, 255, -1)
                mean_val = float(cv2.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), mask=mask)[0])
                if mean_val > 170 and 0.8 < d1 / d2 < 1.25 and d1 > image.shape[0] * 0.25:
                    cv2.drawContours(ref_mask, [cnt], -1, 255, -1)
                    continue

            # Coin: small bright circle
            if len(cnt) >= 5 and len(cnt) <= 200:
                ellipse = cv2.fitEllipse(cnt)
                (_cx, _cy), (d1, d2), _ = ellipse
                if d1 < 12 or d2 < 12:
                    continue
                aspect = max(d1, d2) / min(d1, d2)
                if 1.0 <= aspect < 1.35 and 0.08 < max(d1, d2) / image.shape[1] < 0.45:
                    mask = np.zeros(image.shape[:2], dtype=np.uint8)
                    cv2.drawContours(mask, [cnt], -1, 255, -1)
                    mean_val = float(cv2.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), mask=mask)[0])
                    if mean_val > 170:
                        cv2.drawContours(ref_mask, [cnt], -1, 255, -1)

        return ref_mask

    def _compute_texture_score(self, image: np.ndarray, mask: np.ndarray) -> float:
        """Compute texture score - food typically has more texture than skin/paintings."""
        if mask is None or np.count_nonzero(mask) < 100:
            return 0.0

        # Use Laplacian variance as texture measure
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        masked_gray = cv2.bitwise_and(gray, gray, mask=mask)

        # Compute Laplacian on masked region
        laplacian = cv2.Laplacian(masked_gray, cv2.CV_64F)
        # Only compute variance on masked pixels
        mask_bool = mask > 0
        if not np.any(mask_bool):
            return 0.0
        texture_var = np.var(laplacian[mask_bool])

        # Normalize: food typically has variance > 100, skin ~50-100, flat paintings < 50
        return min(1.0, texture_var / 500.0)

    def _compute_color_variance(self, image: np.ndarray, mask: np.ndarray) -> float:
        """Compute color variance in HSV - food typically has more color variation."""
        if mask is None or np.count_nonzero(mask) < 100:
            return 0.0

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        # Compute hue variance in masked region
        mask_bool = mask > 0
        if not np.any(mask_bool):
            return 0.0
        hue_vals = hsv[mask_bool, 0].astype(float)
        # Handle hue circularity
        hue_var = np.var(hue_vals)
        sat_var = np.var(hsv[mask_bool, 1].astype(float))

        # Food typically has more color variation
        return min(1.0, (hue_var + sat_var) / 5000.0)

    def _compute_uniformity_penalty(self, image: np.ndarray, mask: np.ndarray) -> float:
        """Compute penalty for uniform color regions (penalty 0-1, higher = more uniform = less food-like)."""
        if mask is None or np.count_nonzero(mask) < 100:
            return 1.0

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask_bool = mask > 0
        if not np.any(mask_bool):
            return 1.0

        # Check saturation uniformity - skin/paintings often have uniform saturation
        sat_vals = hsv[mask_bool, 1].astype(float)
        sat_std = np.std(sat_vals)

        # Check value uniformity
        val_vals = hsv[mask_bool, 2].astype(float)
        val_std = np.std(val_vals)

        # Low std = uniform = likely not food
        uniformity = 1.0 - min(1.0, (sat_std + val_std) / 80.0)
        return uniformity

    def segment_food(self, image: np.ndarray) -> list[tuple[np.ndarray, tuple[int, int, int, int]]]:
        """Segment food blobs -> list of (mask, bbox). Excludes faces and skin tones."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        combined = np.zeros(image.shape[:2], dtype=np.uint8)
        for lower, upper in self._FOOD_HSV_RANGES:
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            combined = cv2.bitwise_or(combined, mask)

        # Subtract skin tones
        skin_mask = np.zeros(image.shape[:2], dtype=np.uint8)
        for lower, upper in self._SKIN_HSV_RANGES:
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            skin_mask = cv2.bitwise_or(skin_mask, mask)

        # Subtract face regions
        face_mask = self._get_face_mask(image)
        exclusion_mask = cv2.bitwise_or(skin_mask, face_mask)

        # Also exclude reference objects (card, plate, coin) from food detection
        ref_mask = self._get_reference_object_mask(image)
        exclusion_mask = cv2.bitwise_or(exclusion_mask, ref_mask)

        # Remove excluded regions from food mask
        combined = cv2.bitwise_and(combined, cv2.bitwise_not(exclusion_mask))

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = max(2000, image.shape[0] * image.shape[1] * 0.005)
        max_area = image.shape[0] * image.shape[1] * 0.5

        results: list[tuple[np.ndarray, tuple[int, int, int, int], float]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (min_area < area < max_area):
                continue
            _x, _y, w, h = cv2.boundingRect(cnt)
            aspect = w / h if h > 0 else 1.0
            if area <= 0 or not (0.2 < aspect < 5.0):
                continue

            # Create mask for this contour
            mask = np.zeros(image.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)

            # Compute food-likeness score
            texture_score = self._compute_texture_score(image, mask)
            color_score = self._compute_color_variance(image, mask)
            uniformity_penalty = self._compute_uniformity_penalty(image, mask)
            food_score = (texture_score * 0.5 + color_score * 0.3 + (1.0 - uniformity_penalty) * 0.2)

            # Reject if region overlaps significantly with skin-tone regions
            skin_overlap = np.count_nonzero(cv2.bitwise_and(mask, skin_mask)) / np.count_nonzero(mask)
            if skin_overlap > 0.3:
                continue

            # Only keep regions that look like food (threshold adjustable)
            if food_score < 0.3:
                continue

            results.append((mask, (int(_x), int(_y), int(w), int(h)), food_score))

        # Sort by food score first, then by area
        results.sort(key=lambda item: (item[2], np.count_nonzero(item[0])), reverse=True)
        return [(mask, bbox) for mask, bbox, _ in results[:10]]

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
