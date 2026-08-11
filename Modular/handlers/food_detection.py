"""AI Food Detection Handler - OpenCV-based food recognition with bounding boxes."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, ClassVar

import cv2
import numpy as np

from handlers import ActionHandler
from vision_tracker import StreamState


class FoodDetectionHandler(ActionHandler):
    """Handles AI-based food detection from images with bounding boxes and calorie estimation."""

    actions: ClassVar[dict[str, str]] = {
        "detect_food": "detect_food",
        "estimate_food_calories": "estimate_food_calories",
    }

    def __init__(self, bridge):
        super().__init__(bridge)
        self.food_cascade = None
        self.model_loaded = False
        self._load_models()

    def _load_models(self):
        """Load food detection models."""
        try:
            # Try to load pre-trained food detection model
            # In production, this would load a trained YOLO/MobileNet model
            # For now, we'll use contour-based detection as fallback
            self.model_loaded = True
        except Exception as e:
            print(f"[FoodDetection] Model load warning: {e}")
            self.model_loaded = False

    def detect_food(self, req: dict[str, Any]) -> str:
        """Detect food items in an image and return bounding boxes with calorie estimates."""
        try:
            image_data = req.get("image_base64")
            image_path = req.get("image_path")
            use_vision_feed = req.get("use_vision_feed", False)

            if use_vision_feed:
                if not hasattr(self.bridge, "vision"):
                    return json.dumps({"error": "Vision feed not available"})
                if not self.bridge.vision.tmr.isActive():
                    self.bridge.vision.start(force=True)
                with StreamState.lock:
                    image = None if StreamState.frame is None else StreamState.frame.copy()
                if image is None:
                    return json.dumps({"status": "warming_up", "detections": []})
            elif image_data:
                # Decode base64 image
                img_bytes = base64.b64decode(image_data)
                nparr = np.frombuffer(img_bytes, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            elif image_path and os.path.exists(image_path):
                image = cv2.imread(image_path)
            else:
                return json.dumps({"error": "No image provided"})

            if image is None:
                return json.dumps({"error": "Failed to load image"})

            detections = self._detect_food_items(image)

            # Draw bounding boxes on image
            annotated_image = self._draw_detections(image, detections)

            # Encode annotated image back to base64
            _, buffer = cv2.imencode(".jpg", annotated_image)
            annotated_base64 = base64.b64encode(buffer).decode("utf-8")

            return json.dumps(
                {
                    "detections": detections,
                    "annotated_image": annotated_base64,
                    "image_width": image.shape[1],
                    "image_height": image.shape[0],
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _detect_food_items(self, image: np.ndarray) -> list[dict[str, Any]]:
        """Detect food items using contour analysis and color-based segmentation."""
        detections = []

        # Convert to HSV for better color segmentation
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Define food color ranges in HSV
        food_ranges = [
            # Brown/cooked foods (meat, bread, fried)
            ((10, 50, 50), (25, 255, 200)),
            # Green vegetables
            ((35, 50, 50), (85, 255, 255)),
            # Red/orange foods (tomatoes, carrots, peppers)
            ((0, 50, 50), (15, 255, 255)),
            ((160, 50, 50), (180, 255, 255)),
            # Yellow foods (corn, cheese, eggs)
            ((15, 50, 50), (35, 255, 255)),
            # White foods (rice, potatoes, dairy)
            ((0, 0, 180), (180, 30, 255)),
        ]

        # Combine masks
        combined_mask = np.zeros(image.shape[:2], dtype=np.uint8)
        for lower, upper in food_ranges:
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            combined_mask = cv2.bitwise_or(combined_mask, mask)

        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)

        # Find contours
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter contours by area
        min_area = 5000  # Minimum pixel area for a food item
        max_area = image.shape[0] * image.shape[1] * 0.5  # Max 50% of image

        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area < area < max_area:
                x, y, w, h = cv2.boundingRect(contour)

                # Calculate aspect ratio
                aspect_ratio = w / h if h > 0 else 1
                if 0.3 < aspect_ratio < 3.0:  # Reasonable food shapes
                    # Estimate food type based on color
                    roi = image[y : y + h, x : x + w]
                    food_type = self._classify_food_color(roi)
                    calories = self._estimate_calories(food_type, w, h, image.shape[0])

                    detections.append(
                        {
                            "bbox": [int(x), int(y), int(w), int(h)],
                            "food_type": food_type,
                            "confidence": min(0.95, 0.5 + (area / (image.shape[0] * image.shape[1])) * 0.5),
                            "estimated_calories": calories,
                            "estimated_weight_grams": self._estimate_weight(w, h, image.shape[0]),
                            "area_pixels": int(area),
                        }
                    )

        # Sort by confidence
        detections.sort(key=lambda d: d["confidence"], reverse=True)

        # Return top 10 detections
        return detections[:10]

    def _classify_food_color(self, roi: np.ndarray) -> str:
        """Classify food type based on dominant color in ROI."""
        if roi.size == 0:
            return "Unknown"

        # Calculate average color in HSV
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        avg_hue = np.mean(hsv_roi[:, :, 0])
        avg_sat = np.mean(hsv_roi[:, :, 1])
        avg_val = np.mean(hsv_roi[:, :, 2])

        # Simple classification based on HSV
        if avg_sat < 30:  # Low saturation = white/gray
            if avg_val > 200:
                return "Rice / White Food"
            return "Potato / Starch"
        elif 0 <= avg_hue <= 15 or avg_hue >= 165:  # Red
            if avg_sat > 150:
                return "Tomato / Red Pepper"
            return "Cooked Meat"
        elif 15 < avg_hue <= 35:  # Orange/Yellow
            return "Carrot / Corn / Egg"
        elif 35 < avg_hue <= 85:  # Green
            return "Vegetable / Salad"
        elif 85 < avg_hue <= 130:  # Blue/Purple
            return "Eggplant / Berry"
        else:
            return "Mixed Food"

    def _estimate_calories(self, food_type: str, w: int, h: int, img_height: int) -> int:
        """Estimate calories based on food type and relative size."""
        # Base calories per 100g for different food types
        calorie_map = {
            "Rice / White Food": 130,
            "Potato / Starch": 77,
            "Tomato / Red Pepper": 18,
            "Cooked Meat": 250,
            "Carrot / Corn / Egg": 86,
            "Vegetable / Salad": 25,
            "Eggplant / Berry": 35,
            "Mixed Food": 150,
            "Unknown": 150,
        }

        base_cal = calorie_map.get(food_type, 150)

        # Estimate portion size relative to image
        relative_area = (w * h) / (img_height * img_height)
        portion_multiplier = max(0.5, min(3.0, relative_area * 10))

        return int(base_cal * portion_multiplier)

    def _estimate_weight(self, w: int, h: int, img_height: int) -> int:
        """Estimate food weight in grams based on bounding box size."""
        relative_area = (w * h) / (img_height * img_height)
        # Rough estimate: 1% of image height squared ≈ 50g
        return int(relative_area * 5000)

    def _draw_detections(self, image: np.ndarray, detections: list[dict[str, Any]]) -> np.ndarray:
        """Draw bounding boxes and labels on image."""
        annotated = image.copy()

        for det in detections:
            x, y, w, h = det["bbox"]
            food_type = det["food_type"]
            calories = det["estimated_calories"]
            confidence = det["confidence"]

            # Draw bounding box
            color = (0, 255, 0)  # Green
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)

            # Draw label background
            label = f"{food_type}: ~{calories} kcal ({confidence:.0%})"
            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(annotated, (x, y - label_h - 10), (x + label_w + 10, y), (0, 255, 0), -1)

            # Draw label text
            cv2.putText(annotated, label, (x + 5, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        return annotated

    def estimate_food_calories(self, req: dict[str, Any]) -> str:
        """Estimate calories for a specific food item from image."""
        # This is a simplified version - in production would use a trained model
        return self.detect_food(req)


# Legacy compatibility function
def estimate_calories_opencv(req: dict[str, Any]) -> str:
    """Legacy function for backward compatibility."""
    handler = FoodDetectionHandler(None)
    return handler.detect_food(req)
