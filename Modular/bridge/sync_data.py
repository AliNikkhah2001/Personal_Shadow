"""Sync configuration and portable data actions."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import uuid
import zipfile

from PyQt6.QtWidgets import QApplication, QFileDialog

from core_sys import GITHUB_TOKEN, config, db


class SyncDataActionsMixin:
    """Handle mapped folders, sync status, and import/export actions."""

    def _handle_get_device_id(self, req):
        return json.dumps({"device_id": self.sync_manager.device_id})

    def _handle_map_folder(self, req):
        path = req.get("path", "")
        if os.path.exists(path):
            self.sync_manager.map_folder(path)
            return json.dumps({"status": "success", "path": path})
        return json.dumps({"status": "error", "message": "Path does not exist"})

    def _handle_unmap_folder(self, req):
        path = req.get("path", "")
        self.sync_manager.unmap_folder(path)
        return json.dumps({"status": "success", "path": path})

    def _handle_get_mapped_folders(self, req):
        net_folders = self.sync_manager.get_network_folders()
        repo_path = self.sync_manager.repo_path
        discovered_nodes = {folder["device_id"] for folder in net_folders}

        if os.path.exists(repo_path):
            for root_dir, _, files in os.walk(repo_path):
                if ".git" in root_dir:
                    continue
                for filename in files:
                    if filename.endswith(".json"):
                        try:
                            with open(os.path.join(root_dir, filename), encoding="utf-8") as tmp_f:
                                data = json.load(tmp_f)
                                dev_id = data.get("device_id")
                                if dev_id and dev_id not in discovered_nodes:
                                    discovered_nodes.add(dev_id)
                                    net_folders.append(
                                        {
                                            "device_id": dev_id,
                                            "is_local": dev_id == self.sync_manager.device_id,
                                            "file_count": 1,
                                            "last_update": data.get("last_sync", "Unknown").replace("T", " ")[:16],
                                            "path": "",
                                        }
                                    )
                        except Exception:
                            pass

        return json.dumps(
            {
                "folders": config.get("sync_local_paths", []),
                "network_folders": net_folders,
            }
        )

    def _handle_open_network_folder(self, req):
        path = req.get("path", "")
        if os.path.exists(path):
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
            return json.dumps({"status": "opened"})
        return json.dumps({"status": "error"})

    def _handle_get_sync_status(self, req):
        master_id = None
        with contextlib.suppress(Exception):
            if hasattr(self.sync_manager, "_get_master_id"):
                master_id = self.sync_manager._get_master_id()
        return json.dumps(
            {
                "enabled": config.get("sync_enabled", False),
                "device_id": self.sync_manager.device_id,
                "repo_url": config.get("sync_repo_url", ""),
                "interval": config.get("sync_interval", 3600),
                "has_token": bool(GITHUB_TOKEN),
                "master_id": master_id,
            }
        )

    def _handle_set_quiet_mode(self, req):
        enabled = req.get("enabled", False)
        config.set("quiet_mode", enabled)
        self.quiet_mode = enabled
        if enabled:
            self.vision.stop()
            self.vision.cap = None
        return json.dumps({"status": "ok", "quiet_mode": enabled})

    def _handle_export_data(self, req):
        parent = QApplication.activeWindow()
        file_path, _ = QFileDialog.getSaveFileName(parent, "Export Data", "mindpalace_backup.zip", "ZIP (*.zip)")
        if not file_path:
            return json.dumps({"error": "Export cancelled"})
        data = {"settings": config.cfg, "tables": {}}
        tables = [
            "courses",
            "pomodoro_sessions",
            "cascading_goals",
            "habits",
            "habit_logs",
            "flashcards",
            "quizzes",
            "focus_queue",
            "notes",
        ]
        for table in tables:
            db.c.execute(f"SELECT * FROM {table}")
            columns = [desc[0] for desc in db.c.description]
            data["tables"][table] = [dict(zip(columns, row, strict=False)) for row in db.c.fetchall()]
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("data.json", json.dumps(data, indent=2))
        with open(file_path, "wb") as f:
            f.write(zip_buffer.getvalue())
        return json.dumps({"status": "exported", "path": file_path})

    def _handle_import_data(self, req):
        parent = QApplication.activeWindow()
        file_path, _ = QFileDialog.getOpenFileName(parent, "Import Data", "", "ZIP (*.zip)")
        if not file_path:
            return json.dumps({"error": "Import cancelled"})
        with zipfile.ZipFile(file_path, "r") as zipf, zipf.open("data.json") as f:
            data = json.load(f)
        tables_data = data.get("tables", {})
        for table in [
            "courses",
            "habits",
            "cascading_goals",
            "flashcards",
            "quizzes",
            "notes",
            "focus_queue",
            "habit_logs",
            "pomodoro_sessions",
        ]:
            if table not in tables_data:
                continue
            for row in tables_data[table]:
                uid = row.get("uuid")
                if not uid:
                    uid = uuid.uuid4().hex
                    row["uuid"] = uid
                db.c.execute(f"SELECT id, modified_at FROM {table} WHERE uuid = ?", (uid,))
                existing = db.c.fetchone()
                if existing:
                    existing_id, existing_mod = existing
                    incoming_mod = row.get("modified_at", "")
                    if incoming_mod > existing_mod:
                        set_clause = ", ".join([f"{key} = ?" for key in row if key != "id"])
                        values = [row[key] for key in row if key != "id"] + [existing_id]
                        db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                else:
                    row.pop("id", None)
                    cols = ", ".join(row.keys())
                    placeholders = ", ".join(["?"] * len(row))
                    db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
        db.safe_commit()
        return self.request(json.dumps({"action": "init"}))
