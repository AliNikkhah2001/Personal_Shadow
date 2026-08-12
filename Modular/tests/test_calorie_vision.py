"""Tests for the calorie vision machine (estimator engine, tracker, handler)."""

from __future__ import annotations

import base64
import json

import cv2
import numpy as np

from calorie_tracker import CalorieSessionTracker
from handlers.food_detection import FoodDetectionHandler, estimate_calories_opencv
from opencv_calorie_estimator import (
    FoodCalorieEstimator,
    build_nutrition_db_from_rows,
    create_estimator_from_db,
)


def _black_image(w=640, h=480) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_reference_credit_card_scale():
    """A white rectangle sized like a credit card yields ~correct px/cm."""
    img = _black_image()
    cv2.rectangle(img, (50, 350), (170, 426), (240, 240, 240), -1)
    result = FoodCalorieEstimator().detect_reference_object(img)
    assert result is not None
    ppcm, name = result
    assert name == "credit_card"
    assert 10 < ppcm < 20
    card_w_cm = 120 / ppcm
    assert abs(card_w_cm - 8.56) < 0.3


def test_reference_plate_scale():
    """A solid light plate disk yields the standard 26cm plate scale."""
    img = _black_image()
    cv2.circle(img, (320, 240), 150, (210, 210, 210), -1)
    result = FoodCalorieEstimator().detect_reference_object(img)
    assert result is not None
    ppcm, name = result
    assert name == "standard_plate"
    assert abs(ppcm - 300 / 26.0) < 2.0


def test_green_blob_classified_with_calories():
    """A green blob on black is detected as food with kcal and macros."""
    img = _black_image()
    cv2.rectangle(img, (180, 140), (360, 300), (0, 200, 0), -1)
    dets = FoodCalorieEstimator().estimate_calories(img)
    assert dets
    det = dets[0]
    assert det.name in ("vegetable", "mixed")
    assert det.estimated_kcal > 0
    assert det.estimated_weight_grams > 0
    assert det.volume_cm3 > 0
    assert set(det.estimated_macros) == {"protein", "fat", "carbs"}


def test_detection_volume_scales_with_pixels_per_cm():
    """Bigger scale (closer camera) shrinks physical volume."""
    est = FoodCalorieEstimator()
    img = _black_image()
    cv2.rectangle(img, (180, 140), (360, 300), (0, 200, 0), -1)
    mask, _bbox = est.segment_food(img)[0]
    vol_far = est.estimate_food_volume(mask, pixels_per_cm=10, name="vegetable")
    vol_near = est.estimate_food_volume(mask, pixels_per_cm=20, name="vegetable")
    assert vol_far > vol_near * 3


def test_nutrition_db_seeding_from_persian_rows():
    """Ingredient rows with Persian names map to food classes by keyword."""
    rows = [
        ("برنج پخته (چلو)", 130.0, 2.7, 0.3, 28.0),
        ("قورمه سبزی", 145.0, 8.5, 9.0, 7.5),
        ("ماست کیر", 60.0, 3.5, 3.3, 4.0),
    ]
    db_rows = build_nutrition_db_from_rows(rows)
    assert "rice" in db_rows
    assert abs(db_rows["rice"].kcal - 130.0) < 1e-6
    assert "stew" in db_rows
    assert "yogurt" in db_rows
    est = FoodCalorieEstimator(db_rows)
    assert est.nutrition_for("rice").kcal == 130.0


def test_create_estimator_from_db(tmp_path):
    """create_estimator_from_db pulls calories from the ingredients table."""
    import sqlite3

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.execute(
        "CREATE TABLE ingredients (name TEXT, kcal REAL, protein REAL, fat REAL, carbs REAL)"
    )
    conn.execute("INSERT INTO ingredients VALUES ('پنیر لایق', 265.0, 18.0, 21.0, 1.5)")
    conn.commit()
    est = create_estimator_from_db(conn)
    assert est.nutrition_for("cheese").kcal == 265.0


def test_handler_payload_backward_compat():
    """detect_food returns old + new fields, annotated image, and valid session."""
    img = _black_image()
    cv2.rectangle(img, (180, 140), (360, 300), (0, 200, 0), -1)
    success, encoded = cv2.imencode(".jpg", img)
    assert success
    payload = base64.b64encode(encoded).decode("ascii")

    handler = FoodDetectionHandler(None)
    result = json.loads(
        handler.detect_food({"image_base64": payload, "track_session": True, "include_summary": True})
    )
    assert result["annotated_image"]
    assert result["detections"]
    det = result["detections"][0]
    assert det["estimated_calories"] > 0
    assert det["estimated_kcal"] > 0
    assert det["estimated_weight_grams"] > 0
    assert "estimated_macros" in det
    assert result["session"]["scans_total"] == 1
    # min_confirmations=2 -> not yet in confirmed foods
    assert result["session"]["foods"] == []


def test_session_tracker_confirmation_filtering():
    """Foods are only counted after min_confirmations scans."""
    tracker = CalorieSessionTracker(min_confirmations=2)
    det = {
        "food_type": "vegetable",
        "estimated_kcal": 100.0,
        "estimated_weight_grams": 50.0,
        "estimated_macros": {"protein": 2.0, "fat": 1.0, "carbs": 5.0},
    }
    tracker.add_scan([det])
    assert tracker.summary()["foods"] == []
    tracker.add_scan([det])
    summary = tracker.summary()
    assert len(summary["foods"]) == 1
    assert summary["foods"][0]["avg_kcal"] == 100.0
    assert summary["total_kcal"] == 100.0


def test_session_tracker_reset():
    tracker = CalorieSessionTracker(min_confirmations=1)
    tracker.add_scan([{"food_type": "rice", "estimated_kcal": 200.0}])
    assert tracker.summary()["total_kcal"] == 200.0
    tracker.reset()
    assert tracker.summary()["total_kcal"] == 0.0
    assert tracker.summary()["foods"] == []


def test_tracker_ignores_case_variants_food_type_key():
    """Tracker accepts both old (food_type) and new (name) keys."""
    tracker = CalorieSessionTracker(min_confirmations=1)
    tracker.add_scan([{"name": "meat", "estimated_kcal": 300.0}])
    assert tracker.summary()["foods"][0]["food_type"] == "meat"


def test_legacy_estimate_calories_opencv():
    result = json.loads(estimate_calories_opencv({}))
    assert "error" in result
