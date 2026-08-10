"""Goal management handler."""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime
from typing import Any, ClassVar

from core_sys import db
from handlers import ActionHandler


class GoalHandler(ActionHandler):
    """Handles cascading goal CRUD operations."""

    actions: ClassVar[dict[str, str]] = {
        "manage_goal": "manage_goal",
    }

    def __init__(self, bridge: Any) -> None:
        super().__init__(bridge)

    def manage_goal(self, req: dict[str, Any]) -> str:
        sub = req.get("sub")
        if sub == "add":
            self._add(req)
        elif sub == "delete":
            self._delete(req)
        db.safe_commit()
        return json.dumps(
            {
                "goals": self.bridge.get_goals_tree(),
                "flat_goals": self.bridge.get_flat_goals(),
            }
        )

    def _add(self, req: dict[str, Any]) -> None:
        deadline = req.get("deadline")
        db.c.execute(
            "INSERT INTO cascading_goals (uuid, modified_at, parent_id, title, category, target_hours, deadline) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                uuid_mod.uuid4().hex,
                datetime.now().isoformat(),
                req.get("parent_id"),
                req.get("title"),
                req.get("category"),
                float(req.get("target_hours") or 0),
                deadline.replace("T", " ") if deadline else None,
            ),
        )

    def _delete(self, req: dict[str, Any]) -> None:
        goal_uuid = db.c.execute("SELECT uuid FROM cascading_goals WHERE id=?", (req.get("id"),)).fetchone()
        if goal_uuid:
            db.c.execute("DELETE FROM cascading_goals WHERE id=?", (req.get("id"),))
            db.c.execute(
                "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                ("cascading_goals", goal_uuid[0], datetime.now().isoformat()),
            )
