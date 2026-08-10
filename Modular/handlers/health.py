"""Health management handler."""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime
from typing import Any, ClassVar

from core_sys import db
from handlers import ActionHandler


class HealthHandler(ActionHandler):
    """Handles health profiles, logs, foods, activities, and plans."""

    actions: ClassVar[dict[str, str]] = {
        "manage_health": "manage_health",
        "save_body_scan": "save_body_scan",
    }

    def manage_health(self, req: dict[str, Any]) -> str:
        sub = req.get("sub")
        if sub == "save_profile":
            self._save_profile(req)
        elif sub == "log_entry":
            self._log_entry(req)
        elif sub == "delete_log":
            self._delete_log(req)
        elif sub == "save_food":
            self._save_food(req)
        elif sub == "save_activity":
            self._save_activity(req)
        elif sub == "save_plan":
            self._save_plan(req)
        elif sub == "delete_plan":
            self._delete_plan(req)
        return json.dumps(
            {
                "health_logs": self._get_health_logs(),
                "custom_foods": self._get_custom_foods(),
                "custom_activities": self._get_custom_activities(),
                "health_plans": self._get_health_plans(),
            }
        )

    def save_body_scan(self, req: dict[str, Any]) -> str:
        data = req.get("data", {})
        today_str = datetime.now().date().isoformat()

        db.c.execute("SELECT id, data_json FROM health_profile ORDER BY id DESC LIMIT 1")
        prof_row = db.c.fetchone()
        prof_data = json.loads(prof_row[1]) if prof_row else {}

        if data.get("weight"):
            prof_data["weight"] = data["weight"]
        if data.get("bmr"):
            prof_data["bmr"] = data["bmr"]

        if prof_row:
            db.c.execute(
                "UPDATE health_profile SET data_json=?, modified_at=? WHERE id=?",
                (json.dumps(prof_data), datetime.now().isoformat(), prof_row[0]),
            )
        else:
            db.c.execute(
                "INSERT INTO health_profile (uuid, modified_at, data_json) VALUES (?, ?, ?)",
                (uuid_mod.uuid4().hex, datetime.now().isoformat(), json.dumps(prof_data)),
            )

        db.c.execute(
            "INSERT INTO health_logs (uuid, modified_at, log_type, date, data_json) VALUES (?, ?, ?, ?, ?)",
            (uuid_mod.uuid4().hex, datetime.now().isoformat(), "body_scan", today_str, json.dumps(data)),
        )
        db.safe_commit()

        h_prof = db.c.execute("SELECT data_json FROM health_profile ORDER BY id DESC LIMIT 1").fetchone()
        h_logs = [
            {"type": r[0], "date": r[1], "data": json.loads(r[2])}
            for r in db.c.execute("SELECT log_type, date, data_json FROM health_logs").fetchall()
        ]

        return json.dumps(
            {
                "status": "success",
                "health_profile": json.loads(h_prof[0]) if h_prof else {},
                "health_logs": h_logs,
            }
        )

    def _save_profile(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "INSERT INTO health_profile (uuid, modified_at, data_json) VALUES (?, ?, ?)",
            (uuid_mod.uuid4().hex, datetime.now().isoformat(), json.dumps(req.get("data"))),
        )

    def _log_entry(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "INSERT INTO health_logs (uuid, modified_at, log_type, date, data_json) VALUES (?, ?, ?, ?, ?)",
            (
                uuid_mod.uuid4().hex,
                datetime.now().isoformat(),
                req.get("log_type"),
                req.get("date"),
                json.dumps(req.get("data")),
            ),
        )

    def _delete_log(self, req: dict[str, Any]) -> None:
        log_uuid = db.c.execute("SELECT uuid FROM health_logs WHERE id=?", (req.get("id"),)).fetchone()
        if log_uuid:
            db.c.execute("DELETE FROM health_logs WHERE id=?", (req.get("id"),))
            db.c.execute(
                "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                ("health_logs", log_uuid[0], datetime.now().isoformat()),
            )

    def _save_food(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "INSERT OR REPLACE INTO custom_foods (uuid, modified_at, name, kcal, protein, fat, carbs, category) "
            "VALUES (COALESCE((SELECT uuid FROM custom_foods WHERE name=?), ?), ?, ?, ?, ?, ?, ?, ?)",
            (
                req.get("name"),
                uuid_mod.uuid4().hex,
                datetime.now().isoformat(),
                req.get("name"),
                req.get("kcal"),
                req.get("protein"),
                req.get("fat"),
                req.get("carbs"),
                req.get("category"),
            ),
        )

    def _save_activity(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "INSERT OR REPLACE INTO custom_activities (uuid, modified_at, name, met, category) "
            "VALUES (COALESCE((SELECT uuid FROM custom_activities WHERE name=?), ?), ?, ?, ?, ?)",
            (
                req.get("name"),
                uuid_mod.uuid4().hex,
                datetime.now().isoformat(),
                req.get("name"),
                req.get("met"),
                req.get("category"),
            ),
        )

    def _save_plan(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "INSERT OR REPLACE INTO health_plans (uuid, modified_at, type, title, details) "
            "VALUES (COALESCE((SELECT uuid FROM health_plans WHERE title=?), ?), ?, ?, ?, ?)",
            (
                req.get("title"),
                uuid_mod.uuid4().hex,
                datetime.now().isoformat(),
                req.get("type"),
                req.get("title"),
                req.get("details"),
            ),
        )

    def _delete_plan(self, req: dict[str, Any]) -> None:
        plan_uuid = db.c.execute("SELECT uuid FROM health_plans WHERE id=?", (req.get("id"),)).fetchone()
        if plan_uuid:
            db.c.execute("DELETE FROM health_plans WHERE id=?", (req.get("id"),))
            db.c.execute(
                "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                ("health_plans", plan_uuid[0], datetime.now().isoformat()),
            )

    def _get_health_logs(self) -> list[dict[str, Any]]:
        return [
            {"id": r[0], "type": r[1], "date": r[2], "data": json.loads(r[3])}
            for r in db.c.execute(
                "SELECT id, log_type, date, data_json FROM health_logs ORDER BY modified_at DESC"
            ).fetchall()
        ]

    def _get_custom_foods(self) -> list[dict[str, Any]]:
        return [
            {"id": r[0], "name": r[1], "kcal": r[2], "protein": r[3], "fat": r[4], "carbs": r[5], "category": r[6]}
            for r in db.c.execute("SELECT id, name, kcal, protein, fat, carbs, category FROM custom_foods").fetchall()
        ]

    def _get_custom_activities(self) -> list[dict[str, Any]]:
        return [
            {"id": r[0], "name": r[1], "met": r[2], "category": r[3]}
            for r in db.c.execute("SELECT id, name, met, category FROM custom_activities").fetchall()
        ]

    def _get_health_plans(self) -> list[dict[str, Any]]:
        return [
            {"id": r[0], "type": r[1], "title": r[2], "details": r[3]}
            for r in db.c.execute("SELECT id, type, title, details FROM health_plans").fetchall()
        ]
