"""AI Food Detection Handler - OpenCV-based food recognition with bounding boxes."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, ClassVar

import cv2
import numpy as np

from calorie_tracker import CalorieSessionTracker
from handlers import ActionHandler
from opencv_calorie_estimator import FoodCalorieEstimator, create_estimator_from_db
from vision_tracker import StreamState

try:
    from core_sys import db as _core_db
except ImportError:  # pragma: no cover - tests may run without core_sys
    _core_db = None


class FoodDetectionHandler(ActionHandler):
    """Handles AI-based food detection from images with bounding boxes and calorie estimation."""

    actions: ClassVar[dict[str, str]] = {
        "detect_food": "detect_food",
        "estimate_food_calories": "estimate_food_calories",
        "reset_food_session": "reset_session",
    }

    def __init__(self, bridge):
        super().__init__(bridge)
        self.food_cascade = None
        self.model_loaded = False
        self.session_tracker = CalorieSessionTracker(min_confirmations=2)
        self._estimator = None
        self._load_models()

    @property
    def estimator(self) -> FoodCalorieEstimator:
        """Lazily build the calorie estimator (seeded from the ingredients DB)."""
        if self._estimator is None:
            try:
                self._estimator = create_estimator_from_db(_core_db.conn) if _core_db is not None else FoodCalorieEstimator()
            except Exception:
                self._estimator = FoodCalorieEstimator()
        return self._estimator

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

            results = self.estimator.estimate_calories(image)
            detections = [self._to_payload(d) for d in results]

            # Draw bounding boxes on image
            annotated_image = self.estimator.draw_results(image, results)

            # Encode annotated image back to base64
            _, buffer = cv2.imencode(".jpg", annotated_image)
            annotated_base64 = base64.b64encode(buffer).decode("utf-8")

            # Feed the live session tracker so repeated scans accumulate
            if req.get("use_vision_feed") or req.get("track_session"):
                self.session_tracker.add_scan(detections)

            payload = {
                "detections": detections,
                "annotated_image": annotated_base64,
                "image_width": image.shape[1],
                "image_height": image.shape[0],
            }
            if req.get("include_summary"):
                payload["session"] = self.session_tracker.summary()
            return json.dumps(payload)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @staticmethod
    def _to_payload(d) -> dict[str, Any]:
        """Convert a FoodDetection to the JSON payload shape."""
        return {
            "bbox": list(d.bbox),
            "food_type": d.name,
            "confidence": round(d.confidence, 3),
            "estimated_calories": int(d.estimated_kcal),
            "estimated_kcal": d.estimated_kcal,
            "estimated_weight_grams": int(d.estimated_weight_grams),
            "estimated_macros": d.estimated_macros,
            "volume_cm3": d.volume_cm3,
            "pixels_per_cm": d.pixels_per_cm,
            "area_pixels": d.area_pixels,
        }

    def reset_session(self, req: dict[str, Any] | None = None) -> str:
        """Clear the accumulated calorie session."""
        self.session_tracker.reset()
        return json.dumps({"status": "reset"})

    def estimate_food_calories(self, req: dict[str, Any]) -> str:
        """Estimate calories for a specific food item from image."""
        return self.detect_food(req)


# Legacy compatibility function
def estimate_calories_opencv(req: dict[str, Any]) -> str:
    """Legacy function for backward compatibility."""
    handler = FoodDetectionHandler(None)
    return handler.detect_food(req)
