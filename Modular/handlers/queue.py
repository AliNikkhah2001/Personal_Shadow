"""Focus queue management handler."""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime
from typing import Any, ClassVar

from core_sys import db
from handlers import ActionHandler


class QueueHandler(ActionHandler):
    """Handles focus queue CRUD operations."""

    actions: ClassVar[dict[str, str]] = {
        "manage_queue": "manage_queue",
    }

    def manage_queue(self, req: dict[str, Any]) -> str:
        sub = req.get("sub")
        if sub == "add":
            self._add(req)
        elif sub == "edit":
            self._edit(req)
        elif sub == "delete":
            self._delete(req)
        elif sub == "clear":
            self._clear()
        db.safe_commit()
        return json.dumps({"queue": self._get_queue()})

    def _add(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "INSERT INTO focus_queue (uuid, modified_at, title, duration, type, status, course) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                uuid_mod.uuid4().hex,
                datetime.now().isoformat(),
                req.get("title"),
                int(req.get("duration")),
                req.get("type"),
                "pending",
                req.get("course"),
            ),
        )

    def _edit(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "UPDATE focus_queue SET title=?, duration=?, type=?, course=?, modified_at=? WHERE id=?",
            (
                req.get("title"),
                int(req.get("duration")),
                req.get("type"),
                req.get("course"),
                datetime.now().isoformat(),
                req.get("id"),
            ),
        )

    def _delete(self, req: dict[str, Any]) -> None:
        target_id = req.get("id")
        queue_uuid = db.c.execute("SELECT uuid FROM focus_queue WHERE id=?", (target_id,)).fetchone()
        if queue_uuid:
            db.c.execute("DELETE FROM focus_queue WHERE id=?", (target_id,))
            db.c.execute(
                "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                ("focus_queue", queue_uuid[0], datetime.now().isoformat()),
            )
        if self.bridge.active_queue_id == target_id:
            self.bridge.active_queue_id = None
            self.bridge.is_running = False
            self.bridge.timer.stop()

    def _clear(self) -> None:
        queue_uuids = db.c.execute("SELECT uuid FROM focus_queue").fetchall()
        db.c.execute("DELETE FROM focus_queue")
        for (uuid_val,) in queue_uuids:
            db.c.execute(
                "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                ("focus_queue", uuid_val, datetime.now().isoformat()),
            )
        self.bridge.active_queue_id = None
        self.bridge.is_running = False
        self.bridge.timer.stop()

    def _get_queue(self) -> list[dict[str, Any]]:
        return [
            {"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]}
            for r in db.c.execute(
                "SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id"
            ).fetchall()
        ]
