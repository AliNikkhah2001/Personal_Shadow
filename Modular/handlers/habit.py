"""Habit tracking handler."""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime
from typing import Any, ClassVar

from core_sys import db
from handlers import ActionHandler


class HabitHandler(ActionHandler):
    """Handles habit definitions and daily habit logging."""

    actions: ClassVar[dict[str, str]] = {
        "manage_habit": "manage_habit",
    }

    def manage_habit(self, req: dict[str, Any]) -> str:
        sub = req.get("sub")
        if sub == "add":
            self._add(req)
        elif sub == "edit":
            self._edit(req)
        elif sub == "delete":
            self._delete(req)
        elif sub == "toggle_log":
            self._toggle_log(req)
        db.safe_commit()
        return json.dumps(
            {
                "habits": self._get_habits(),
                "habit_logs": self._get_habit_logs(),
            }
        )

    def _add(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "INSERT INTO habits (uuid, modified_at, name, type, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                uuid_mod.uuid4().hex,
                datetime.now().isoformat(),
                req.get("name"),
                req.get("type", "Positive"),
                datetime.now().isoformat(),
            ),
        )

    def _edit(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "UPDATE habits SET name=?, type=?, modified_at=? WHERE id=?",
            (req.get("name"), req.get("type"), datetime.now().isoformat(), req.get("id")),
        )

    def _delete(self, req: dict[str, Any]) -> None:
        habit_uuid = db.c.execute("SELECT uuid FROM habits WHERE id=?", (req.get("id"),)).fetchone()
        if habit_uuid:
            db.c.execute("DELETE FROM habits WHERE id=?", (req.get("id"),))
            db.c.execute("DELETE FROM habit_logs WHERE habit_id=?", (req.get("id"),))
            db.c.execute(
                "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                ("habits", habit_uuid[0], datetime.now().isoformat()),
            )

    def _toggle_log(self, req: dict[str, Any]) -> None:
        hid, dt, st = req.get("habit_id"), req.get("date"), req.get("status", 1)
        existing = db.c.execute("SELECT id FROM habit_logs WHERE habit_id=? AND date=?", (hid, dt)).fetchone()
        if existing:
            db.c.execute(
                "UPDATE habit_logs SET status=?, modified_at=? WHERE id=?",
                (st, datetime.now().isoformat(), existing[0]),
            )
        else:
            db.c.execute(
                "INSERT INTO habit_logs (uuid, modified_at, habit_id, date, status) VALUES (?, ?, ?, ?, ?)",
                (uuid_mod.uuid4().hex, datetime.now().isoformat(), hid, dt, st),
            )

    def _get_habits(self) -> list[dict[str, Any]]:
        return [
            {"id": r[0], "name": r[1], "type": r[2]}
            for r in db.c.execute("SELECT id, name, type FROM habits").fetchall()
        ]

    def _get_habit_logs(self) -> list[dict[str, Any]]:
        return [
            {"habit_id": r[0], "date": r[1], "status": r[2]}
            for r in db.c.execute("SELECT habit_id, date, status FROM habit_logs").fetchall()
        ]
