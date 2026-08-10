"""Nutrition and ingredient management handler."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, ClassVar

from core_sys import db
from handlers import ActionHandler


class NutritionHandler(ActionHandler):
    """Handles ingredient, composite food, and recipe management."""

    actions: ClassVar[dict[str, str]] = {
        "manage_nutrition": "manage_nutrition",
        "estimate_calories_opencv": "estimate_calories_opencv",
    }

    def manage_nutrition(self, req: dict[str, Any]) -> str:
        sub = req.get("sub")
        if sub == "get_all":
            return self._get_all()
        if sub == "add_ingredient":
            return self._add_ingredient(req)
        if sub == "delete_ingredient":
            return self._delete_ingredient(req)
        if sub == "add_composite":
            return self._add_composite(req)
        if sub == "delete_composite":
            return self._delete_composite(req)
        return json.dumps({"error": "Unknown nutrition sub-action"})

    def estimate_calories_opencv(self, req: dict[str, Any]) -> str:
        """Estimate calories from food image using OpenCV.
        
        Future scope: This is a placeholder for computer vision based
        calorie estimation. Requires trained models for:
        - Food detection/classification
        - Instance segmentation
        - Volume estimation
        """
        image_path = req.get("image_path")
        if not image_path:
            return json.dumps({"error": "No image path provided"})
        
        # This is a framework - actual implementation would use trained models
        return json.dumps({
            "status": "framework_ready",
            "message": "OpenCV calorie estimation framework is ready. Requires trained models for production use.",
            "components_needed": [
                "Food detection model (YOLO/EfficientDet)",
                "Instance segmentation model (Mask R-CNN)",
                "Reference object detection for scale",
                "Nutrition database integration"
            ],
            "estimated_detections": []
        })

    def _get_all(self) -> str:
        db.c.execute(
            "SELECT id, name, kcal, protein, fat, carbs, serving_size, serving_unit, category, image_path, is_iranian FROM ingredients ORDER BY name"
        )
        ingredients = [
            {
                "id": r[0],
                "name": r[1],
                "kcal": r[2],
                "protein": r[3],
                "fat": r[4],
                "carbs": r[5],
                "serving_size": r[6],
                "serving_unit": r[7],
                "category": r[8],
                "image_path": r[9],
                "is_iranian": r[10],
            }
            for r in db.c.fetchall()
        ]

        db.c.execute("SELECT id, name, image_path, instructions, prep_time_min, cook_time_min, servings FROM composite_foods ORDER BY name")
        composites = []
        for c_id, c_name, c_img, c_instructions, c_prep, c_cook, c_servings in db.c.fetchall():
            db.c.execute(
                "SELECT i.name, ri.amount_grams, i.kcal, i.protein, i.fat, i.carbs "
                "FROM recipe_ingredients ri JOIN ingredients i ON ri.ingredient_id = i.id "
                "WHERE ri.composite_food_id = ?",
                (c_id,),
            )
            parts = [
                {
                    "name": r[0],
                    "amount_grams": r[1],
                    "kcal": (r[2] * r[1] / 100.0),
                    "protein": (r[3] * r[1] / 100.0),
                    "fat": (r[4] * r[1] / 100.0),
                    "carbs": (r[5] * r[1] / 100.0),
                }
                for r in db.c.fetchall()
            ]
            total_kcal = sum(p["kcal"] for p in parts)
            total_protein = sum(p["protein"] for p in parts)
            total_fat = sum(p["fat"] for p in parts)
            total_carbs = sum(p["carbs"] for p in parts)
            per_serving_kcal = total_kcal / c_servings if c_servings > 0 else total_kcal
            composites.append(
                {
                    "id": c_id,
                    "name": c_name,
                    "image_path": c_img,
                    "instructions": c_instructions,
                    "prep_time_min": c_prep,
                    "cook_time_min": c_cook,
                    "servings": c_servings,
                    "parts": parts,
                    "kcal": total_kcal,
                    "protein": total_protein,
                    "fat": total_fat,
                    "carbs": total_carbs,
                    "per_serving_kcal": per_serving_kcal,
                }
            )

        return json.dumps({"ingredients": ingredients, "composite_foods": composites})

    def _add_ingredient(self, req: dict[str, Any]) -> str:
        try:
            db.c.execute(
                "INSERT INTO ingredients (uuid, modified_at, name, kcal, protein, fat, carbs, serving_size, serving_unit, category, image_path, is_iranian) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    __import__("uuid").uuid4().hex,
                    datetime.now().isoformat(),
                    req.get("name"),
                    float(req.get("kcal") or 0),
                    float(req.get("protein") or 0),
                    float(req.get("fat") or 0),
                    float(req.get("carbs") or 0),
                    req.get("serving_size", 100),
                    req.get("serving_unit", "g"),
                    req.get("category", "General"),
                    req.get("image_path", ""),
                    req.get("is_iranian", False),
                ),
            )
            db.safe_commit()
        except sqlite3.IntegrityError:
            pass
        return self._get_all()

    def _delete_ingredient(self, req: dict[str, Any]) -> str:
        db.c.execute("DELETE FROM ingredients WHERE id=?", (req.get("id"),))
        db.c.execute("DELETE FROM recipe_ingredients WHERE ingredient_id=?", (req.get("id"),))
        db.safe_commit()
        return self._get_all()

    def _add_composite(self, req: dict[str, Any]) -> str:
        import uuid as uuid_mod

        c_uuid = uuid_mod.uuid4().hex
        try:
            db.c.execute(
                "INSERT INTO composite_foods (uuid, modified_at, name, image_path, instructions, prep_time_min, cook_time_min, servings) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (c_uuid, datetime.now().isoformat(), req.get("name"), req.get("image_path", ""), req.get("instructions", ""), int(req.get("prep_time_min") or 0), int(req.get("cook_time_min") or 0), int(req.get("servings") or 1)),
            )
            c_id = db.c.lastrowid
            for part in req.get("parts", []):
                db.c.execute(
                    "INSERT INTO recipe_ingredients (uuid, modified_at, composite_food_id, ingredient_id, amount_grams) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        uuid_mod.uuid4().hex,
                        datetime.now().isoformat(),
                        c_id,
                        part["ingredient_id"],
                        part["amount_grams"],
                    ),
                )
            db.safe_commit()
        except sqlite3.IntegrityError:
            pass
        return self._get_all()

    def _delete_composite(self, req: dict[str, Any]) -> str:
        db.c.execute("DELETE FROM composite_foods WHERE id=?", (req.get("id"),))
        db.c.execute("DELETE FROM recipe_ingredients WHERE composite_food_id=?", (req.get("id"),))
        db.safe_commit()
        return self._get_all()
