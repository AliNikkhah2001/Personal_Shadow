"""Note management handler."""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime
from typing import Any, ClassVar

from core_sys import db
from handlers import ActionHandler


class NoteHandler(ActionHandler):
    """Handles note CRUD operations."""

    actions: ClassVar[dict[str, str]] = {
        "manage_note": "manage_note",
    }

    def manage_note(self, req: dict[str, Any]) -> str:
        sub = req.get("sub")
        if sub == "save":
            self._save(req)
        elif sub == "delete":
            self._delete(req)
        db.safe_commit()
        return json.dumps({"notes": self._get_notes()})

    def _save(self, req: dict[str, Any]) -> None:
        if req.get("id"):
            db.c.execute(
                "UPDATE notes SET title=?, content=?, course=?, folder=?, color=?, modified_at=? WHERE id=?",
                (
                    req.get("title"),
                    req.get("content"),
                    req.get("course"),
                    req.get("folder"),
                    req.get("color"),
                    datetime.now().isoformat(),
                    req.get("id"),
                ),
            )
        else:
            db.c.execute(
                "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid_mod.uuid4().hex,
                    datetime.now().isoformat(),
                    req.get("title"),
                    req.get("content"),
                    datetime.now().isoformat(),
                    req.get("course"),
                    req.get("folder"),
                    req.get("color"),
                ),
            )

    def _delete(self, req: dict[str, Any]) -> None:
        note_uuid = db.c.execute("SELECT uuid FROM notes WHERE id=?", (req.get("id"),)).fetchone()
        if note_uuid:
            db.c.execute("DELETE FROM notes WHERE id=?", (req.get("id"),))
            db.c.execute(
                "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                ("notes", note_uuid[0], datetime.now().isoformat()),
            )

    def _get_notes(self) -> list[dict[str, Any]]:
        return [
            {"id": r[0], "title": r[1], "content": r[2], "course": r[3], "folder": r[4], "color": r[5]}
            for r in db.c.execute(
                "SELECT id, title, content, course, folder, color FROM notes ORDER BY id DESC"
            ).fetchall()
        ]
