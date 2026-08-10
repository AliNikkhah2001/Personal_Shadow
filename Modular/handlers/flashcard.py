"""Flashcard and quiz management handler."""

from __future__ import annotations

import json
import uuid as uuid_mod
from datetime import datetime
from typing import Any, ClassVar

from core_sys import db
from handlers import ActionHandler


class FlashcardHandler(ActionHandler):
    """Handles flashcard and quiz CRUD operations."""

    actions: ClassVar[dict[str, str]] = {
        "manage_flashcard": "manage_flashcard",
        "manage_quiz": "manage_quiz",
    }

    def manage_flashcard(self, req: dict[str, Any]) -> str:
        sub = req.get("sub")
        if sub == "add":
            self._add_card(req)
        elif sub == "delete":
            self._delete_card(req)
        db.safe_commit()
        return json.dumps({"flashcards": self._get_flashcards()})

    def manage_quiz(self, req: dict[str, Any]) -> str:
        sub = req.get("sub")
        if sub == "add":
            self._add_quiz(req)
        elif sub == "delete":
            self._delete_quiz(req)
        db.safe_commit()
        return json.dumps({"quizzes": self._get_quizzes()})

    def _add_card(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "INSERT INTO flashcards (uuid, modified_at, front, back, deck, course, folder, color) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid_mod.uuid4().hex,
                datetime.now().isoformat(),
                req.get("front"),
                req.get("back"),
                req.get("deck"),
                req.get("course"),
                req.get("folder"),
                req.get("color"),
            ),
        )

    def _delete_card(self, req: dict[str, Any]) -> None:
        card_uuid = db.c.execute("SELECT uuid FROM flashcards WHERE id=?", (req.get("id"),)).fetchone()
        if card_uuid:
            db.c.execute("DELETE FROM flashcards WHERE id=?", (req.get("id"),))
            db.c.execute(
                "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                ("flashcards", card_uuid[0], datetime.now().isoformat()),
            )

    def _add_quiz(self, req: dict[str, Any]) -> None:
        db.c.execute(
            "INSERT INTO quizzes (uuid, modified_at, title, questions_json, course, folder, color) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                uuid_mod.uuid4().hex,
                datetime.now().isoformat(),
                req.get("title"),
                req.get("json"),
                req.get("course"),
                req.get("folder"),
                req.get("color"),
            ),
        )

    def _delete_quiz(self, req: dict[str, Any]) -> None:
        quiz_uuid = db.c.execute("SELECT uuid FROM quizzes WHERE id=?", (req.get("id"),)).fetchone()
        if quiz_uuid:
            db.c.execute("DELETE FROM quizzes WHERE id=?", (req.get("id"),))
            db.c.execute(
                "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                ("quizzes", quiz_uuid[0], datetime.now().isoformat()),
            )

    def _get_flashcards(self) -> list[dict[str, Any]]:
        return [
            {"id": r[0], "front": r[1], "back": r[2], "deck": r[3], "course": r[4], "folder": r[5], "color": r[6]}
            for r in db.c.execute("SELECT id, front, back, deck, course, folder, color FROM flashcards").fetchall()
        ]

    def _get_quizzes(self) -> list[dict[str, Any]]:
        return [
            {"id": r[0], "title": r[1], "json": r[2], "course": r[3], "folder": r[4], "color": r[5]}
            for r in db.c.execute("SELECT id, title, questions_json, course, folder, color FROM quizzes").fetchall()
        ]
