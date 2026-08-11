"""Database-backed wallpaper actions."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import uuid
from datetime import datetime
from typing import Any, ClassVar

from core_sys import config, db
from handlers import ActionHandler


class WallpaperHandler(ActionHandler):
    """Persist the active wallpaper as a synchronized SQLite BLOB."""

    actions: ClassVar[dict[str, str]] = {
        "save_wallpaper": "save_wallpaper",
        "get_active_wallpaper": "get_active_wallpaper",
        "clear_wallpaper": "clear_wallpaper",
    }

    def __init__(self, bridge) -> None:
        super().__init__(bridge)
        self._migrate_configured_wallpaper()

    def save_wallpaper(self, req: dict[str, Any]) -> str:
        path = os.path.abspath(os.path.expanduser(req.get("path", "")))
        if not os.path.isfile(path):
            return json.dumps({"error": "Wallpaper file does not exist"})

        with open(path, "rb") as image_file:
            image_data = image_file.read()
        if len(image_data) > 25 * 1024 * 1024:
            return json.dumps({"error": "Wallpaper must be smaller than 25 MB"})

        mime_type = mimetypes.guess_type(path)[0] or "image/jpeg"
        now = datetime.now().isoformat()
        db.c.execute("UPDATE wallpapers SET is_active=0")
        db.c.execute(
            """INSERT INTO wallpapers
               (uuid, modified_at, name, image_data, mime_type, is_active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (uuid.uuid4().hex, now, os.path.basename(path), image_data, mime_type),
        )
        db.safe_commit()
        config.set("bg_image_path", "")
        return json.dumps(self._active_wallpaper())

    def get_active_wallpaper(self, _req: dict[str, Any]) -> str:
        return json.dumps(self._active_wallpaper())

    def clear_wallpaper(self, _req: dict[str, Any]) -> str:
        db.c.execute("UPDATE wallpapers SET is_active=0")
        db.safe_commit()
        config.set("bg_image_path", "")
        return json.dumps({"status": "cleared", "data_url": ""})

    def _migrate_configured_wallpaper(self) -> None:
        db.c.execute("SELECT 1 FROM wallpapers WHERE is_active=1 LIMIT 1")
        if db.c.fetchone():
            return
        configured_path = config.get("bg_image_path", "")
        if configured_path and os.path.isfile(os.path.expanduser(configured_path)):
            self.save_wallpaper({"path": configured_path})

    @staticmethod
    def _active_wallpaper() -> dict[str, Any]:
        db.c.execute(
            """SELECT name, image_data, mime_type
               FROM wallpapers
               WHERE is_active=1
               ORDER BY modified_at DESC LIMIT 1"""
        )
        row = db.c.fetchone()
        if not row:
            return {"status": "empty", "data_url": ""}
        name, image_data, mime_type = row
        encoded = base64.b64encode(image_data).decode("ascii")
        return {
            "status": "ok",
            "name": name,
            "data_url": f"data:{mime_type};base64,{encoded}",
        }
