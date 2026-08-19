"""Sync operations handler."""

from __future__ import annotations

import contextlib
import json
import os
import threading
from typing import Any, ClassVar

from core_sys import db
from handlers import ActionHandler


class SyncHandler(ActionHandler):
    """Handles device synchronization operations."""

    actions: ClassVar[dict[str, str]] = {
        "sync_now": "sync_now",
        "hard_clone_remote": "hard_clone_remote",
        "force_sync_now": "force_sync_now",
        "get_sync_progress": "get_sync_progress",
    }

    def __init__(self, bridge: Any) -> None:
        super().__init__(bridge)

    def sync_now(self, req: dict[str, Any]) -> str:
        threading.Thread(target=self._sync_thread, daemon=True).start()
        return json.dumps({"status": "started"})

    def hard_clone_remote(self, req: dict[str, Any]) -> str:
        target_device = req.get("target_device")
        threading.Thread(target=self._hard_clone_thread, args=(target_device,), daemon=True).start()
        return json.dumps({"status": "started"})

    def force_sync_now(self, req: dict[str, Any]) -> str:
        threading.Thread(target=self._force_sync_thread, daemon=True).start()
        return json.dumps({"status": "started"})

    def get_sync_progress(self, req: dict[str, Any]) -> str:
        return json.dumps({
            "status": self.bridge.sync_status if hasattr(self.bridge, 'sync_status') else "idle",
            "progress": self.bridge.sync_progress_value if hasattr(self.bridge, 'sync_progress_value') else 0,
            "message": self.bridge.sync_message if hasattr(self.bridge, 'sync_message') else ""
        })

    def _sync_thread(self) -> None:
        try:
            self.bridge.sync_progress.emit("Starting K-Peer Sync...")
            success, msg = self.bridge.sync_manager.setup_repo()
            if not success:
                self.bridge.handle_sync_completed(False, msg)
                return

            origin = self.bridge.sync_manager.repo.remotes.origin
            from sync_manager import DetailedSyncProgress

            self.bridge.sync_progress.emit("Pulling cluster state...")
            origin.pull(rebase=False, progress=DetailedSyncProgress())

            master_id = self.bridge.get_cluster_master()
            is_master = (self.bridge.sync_manager.device_id == master_id) or (master_id is None)

            self.bridge.sync_progress.emit("Merging remote changes...")
            self.bridge.sync_manager.ensure_uuids_and_timestamps()

            # Track sync status on bridge for UI polling
            self.bridge.sync_status = "merging"
            self.bridge.sync_progress_value = 30
            self.bridge.sync_message = "Merging remote changes..."

            sync_dir = os.path.join(self.bridge.sync_manager.repo_path, self.bridge.sync_manager.db_sync_dir)
            if os.path.exists(sync_dir):
                db.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence')")
                valid_tables = [r[0] for r in db.c.fetchall()]
                for filename in os.listdir(sync_dir):
                    if not filename.endswith(".json") or filename == f"{self.bridge.sync_manager.device_id}.json":
                        continue
                    if not is_master and master_id and filename != f"{master_id}.json":
                        continue

                    try:
                        with open(os.path.join(sync_dir, filename), encoding="utf-8") as f:
                            remote_data = json.load(f)
                        r_sync = remote_data.get("last_sync", "")
                        l_sync = self.bridge.config.get("last_sync_timestamp", "")
                        if r_sync and (not l_sync or r_sync > l_sync):
                            for k, v in remote_data.get("settings", {}).items():
                                if k not in ["device_id", "has_token", "git_status"]:
                                    self.bridge.config.set(k, v)
                            self.bridge.config.set("last_sync_timestamp", r_sync)

                        for table, rows in remote_data.get("tables", {}).items():
                            if table not in valid_tables:
                                continue
                            db.c.execute(f"PRAGMA table_info({table})")
                            columns = [info[1] for info in db.c.fetchall()]
                            if "uuid" not in columns or "modified_at" not in columns:
                                continue

                            for row in rows:
                                uid = row.get("uuid")
                                if not uid:
                                    continue
                                in_mod = row.get("modified_at", "")
                                db.c.execute(f"SELECT id, modified_at FROM {table} WHERE uuid = ?", (uid,))
                                existing = db.c.fetchone()
                                if existing:
                                    if not existing[1] or (in_mod and in_mod > existing[1]):
                                        set_clause = ", ".join([f"{k} = ?" for k in row if k not in ["id", "uuid"]])
                                        values = [row[k] for k in row if k not in ["id", "uuid"]] + [existing[0]]
                                        with contextlib.suppress(Exception):
                                            db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                                else:
                                    row.pop("id", None)
                                    cols = ", ".join(row.keys())
                                    placeholders = ", ".join(["?"] * len(row))
                                    with contextlib.suppress(Exception):
                                        db.c.execute(
                                            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values())
                                        )
                    except Exception as e:
                        print(f"Merge error {filename}: {e}")
                    db.safe_commit()

            self.bridge.sync_progress.emit("Syncing mapped folders...")
            self.bridge.sync_status = "syncing_files"
            self.bridge.sync_progress_value = 50
            self.bridge.sync_message = "Syncing mapped folders..."
            with contextlib.suppress(Exception):
                self.bridge.sync_manager.sync_files()

            self.bridge.sync_progress.emit("Exporting local state...")
            self.bridge.sync_status = "exporting"
            self.bridge.sync_progress_value = 70
            self.bridge.sync_message = "Exporting local state..."
            local_data = self.bridge.sync_manager.export_local_data()
            export_path = os.path.join(self.bridge.sync_manager.repo_path, self.bridge.sync_manager.sync_data_file)
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(local_data, f, indent=2)

            self.bridge.sync_progress.emit("Pushing to cluster...")
            self.bridge.sync_status = "pushing"
            self.bridge.sync_progress_value = 90
            self.bridge.sync_message = "Pushing to cluster..."
            self.bridge.sync_manager.repo.git.add(export_path, force=True)
            self.bridge.sync_manager.repo.git.add(all=True)
            if self.bridge.sync_manager.repo.is_dirty() or self.bridge.sync_manager.repo.untracked_files:
                self.bridge.sync_manager.repo.index.commit(f"Sync from {self.bridge.sync_manager.device_id}")
            origin.push(progress=DetailedSyncProgress())
            self.bridge.sync_status = "completed"
            self.bridge.sync_progress_value = 100
            self.bridge.sync_message = "Sync completed"
            self.bridge.handle_sync_completed(True, "K-Peer Sync completed successfully")
        except Exception as e:
            self.bridge.handle_sync_completed(False, str(e))

    def _hard_clone_thread(self, target_device: str | None) -> None:
        try:
            safe_target = target_device if target_device else "Unknown"
            self.bridge.sync_progress.emit(f"Starting Hard Clone for Node {safe_target[:8]}...")
            self.bridge.sync_status = "cloning"
            self.bridge.sync_progress_value = 10
            self.bridge.sync_message = f"Starting Hard Clone for Node {safe_target[:8]}..."

            success, msg = self.bridge.sync_manager.setup_repo()
            if not success:
                self.bridge.handle_sync_completed(False, msg)
                return

            self.bridge.sync_progress.emit("Pulling Network Data from Git...")
            self.bridge.sync_status = "cloning_pull"
            self.bridge.sync_progress_value = 20
            self.bridge.sync_message = "Pulling network data from Git..."
            origin = self.bridge.sync_manager.repo.remotes.origin
            with contextlib.suppress(Exception):
                from sync_manager import DetailedSyncProgress

                origin.pull(rebase=False, progress=DetailedSyncProgress())

            self.bridge.sync_status = "cloning_wipe"
            self.bridge.sync_progress_value = 40
            self.bridge.sync_message = "Wiping local database..."
            sync_dir = os.path.join(self.bridge.sync_manager.repo_path, self.bridge.sync_manager.db_sync_dir)
            target_file = self._resolve_clone_target(sync_dir, target_device)

            if not target_file or not os.path.exists(target_file):
                self.bridge.handle_sync_completed(False, f"Target JSON file not found: {target_file}")
                return

            self.bridge.sync_progress.emit("Wiping local database...")
            tables_to_clear = [
                "courses",
                "pomodoro_sessions",
                "cascading_goals",
                "habits",
                "habit_logs",
                "flashcards",
                "quizzes",
                "focus_queue",
                "notes",
                "health_profile",
                "health_logs",
                "custom_foods",
                "custom_activities",
                "health_plans",
                "activity_logs",
                "ingredients",
                "composite_foods",
                "recipe_ingredients",
            ]
            for table in tables_to_clear:
                with contextlib.suppress(Exception):
                    db.c.execute(f"DELETE FROM {table}")
            db.c.execute("DELETE FROM deleted_uuids")
            db.safe_commit()

            self.bridge.sync_status = "cloning_inject"
            self.bridge.sync_progress_value = 60
            self.bridge.sync_message = "Injecting node data..."
            self.bridge.sync_progress.emit("Injecting node data...")
            with open(target_file, encoding="utf-8") as f:
                remote_data = json.load(f)

            for k, v in remote_data.get("settings", {}).items():
                if k not in ["device_id", "has_token", "git_status"]:
                    self.bridge.config.set(k, v)

            for table, rows in remote_data.get("tables", {}).items():
                if table not in tables_to_clear:
                    continue
                for row in rows:
                    cols = ", ".join(row.keys())
                    placeholders = ", ".join(["?"] * len(row))
                    with contextlib.suppress(Exception):
                        db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
            db.safe_commit()

            self.bridge.sync_status = "cloning_complete"
            self.bridge.sync_progress_value = 100
            self.bridge.sync_message = "Clone completed"
            self.bridge.handle_sync_completed(
                True, f"Successfully cloned from {os.path.basename(target_file)}. Restart App."
            )
        except Exception as e:
            self.bridge.handle_sync_completed(False, str(e))
                True, f"Successfully cloned from {os.path.basename(target_file)}. Restart App."
            )
        except Exception as e:
            self.bridge.handle_sync_completed(False, str(e))

def _force_sync_thread(self) -> None:
        try:
            self.bridge.sync_progress.emit("Starting MASTER OVERWRITE sync...")
            self.bridge.sync_status = "force_sync"
            self.bridge.sync_progress_value = 10
            self.bridge.sync_message = "Starting MASTER OVERWRITE sync..."
            success, msg = self.bridge.sync_manager.setup_repo()
            if not success:
                self.bridge.handle_sync_completed(False, msg)
                return

            self.bridge.sync_status = "force_sync_pull"
            self.bridge.sync_progress_value = 20
            self.bridge.sync_message = "Pulling latest data..."
            self.bridge.sync_progress.emit("Pulling latest data to prevent push conflicts...")
            origin = self.bridge.sync_manager.repo.remotes.origin
            with contextlib.suppress(Exception):
                from sync_manager import DetailedSyncProgress

                origin.pull(rebase=False, progress=DetailedSyncProgress())

            self.bridge.sync_status = "force_sync_promote"
            self.bridge.sync_progress_value = 30
            self.bridge.sync_message = "Promoting device to Cluster Master..."
            self.bridge.sync_progress.emit("Promoting device to Cluster Master...")
            origin = self.bridge.sync_manager.repo.remotes.origin
            with contextlib.suppress(Exception):
                from sync_manager import DetailedSyncProgress

                origin.pull(rebase=False, progress=DetailedSyncProgress())

            cluster_file = os.path.join(self.bridge.sync_manager.repo_path, "cluster_state.json")
            with open(cluster_file, "w") as f:
                json.dump(
                    {
                        "master_id": self.bridge.sync_manager.device_id,
                        "timestamp": __import__("datetime").datetime.now().isoformat(),
                    },
                    f,
                )

            self.bridge.sync_status = "force_sync_clear"
            self.bridge.sync_progress_value = 40
            self.bridge.sync_message = "Clearing other nodes' data..."
            sync_dir = os.path.join(self.bridge.sync_manager.repo_path, self.bridge.sync_manager.db_sync_dir)
            if os.path.exists(sync_dir):
                for fname in os.listdir(sync_dir):
                    if fname.endswith(".json") and fname != f"{self.bridge.sync_manager.device_id}.json":
                        with contextlib.suppress(Exception):
                            os.remove(os.path.join(sync_dir, fname))

            self.bridge.sync_status = "force_sync_clear_db"
            self.bridge.sync_progress_value = 50
            self.bridge.sync_message = "Clearing local database..."
            db.c.execute("DELETE FROM deleted_uuids")
            db.safe_commit()

            self.bridge.sync_status = "force_sync_files"
            self.bridge.sync_progress_value = 60
            self.bridge.sync_message = "Syncing mapped folders..."
            self.bridge.sync_progress.emit("Syncing mapped folders...")
            with contextlib.suppress(Exception):
                self.bridge.sync_manager.sync_files()

            self.bridge.sync_status = "force_sync_export"
            self.bridge.sync_progress_value = 70
            self.bridge.sync_message = "Exporting Master local data..."
            self.bridge.sync_progress.emit("Exporting Master local data...")
            self.bridge.sync_manager.ensure_uuids_and_timestamps()
            local_data = self.bridge.sync_manager.export_local_data()
            export_path = os.path.join(self.bridge.sync_manager.repo_path, self.bridge.sync_manager.sync_data_file)
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(local_data, f, indent=2)

            self.bridge.sync_status = "force_sync_push"
            self.bridge.sync_progress_value = 90
            self.bridge.sync_message = "Force Pushing Master to GitHub..."
            self.bridge.sync_progress.emit("Force Pushing Master to GitHub...")
            self.bridge.sync_manager.repo.git.add(cluster_file, force=True)
            self.bridge.sync_manager.repo.git.add(export_path, force=True)
            self.bridge.sync_manager.repo.git.add(all=True)
            if self.bridge.sync_manager.repo.is_dirty() or self.bridge.sync_manager.repo.untracked_files:
                self.bridge.sync_manager.repo.index.commit(f"MASTER PROMOTE from {self.bridge.sync_manager.device_id}")
            origin.push(progress=DetailedSyncProgress())
            self.bridge.sync_status = "completed"
            self.bridge.sync_progress_value = 100
            self.bridge.sync_message = "Master Overwrite completed"
            self.bridge.handle_sync_completed(True, "Master Overwrite completed successfully")
        except Exception as e:
            self.bridge.handle_sync_completed(False, str(e))

    def _resolve_clone_target(self, sync_dir: str, target_device: str | None) -> str | None:
        master_id = None
        if hasattr(self.bridge.sync_manager, "_get_master_id"):
            master_id = self.bridge.sync_manager._get_master_id()

        if target_device == "MASTER" and master_id:
            target_file = os.path.join(sync_dir, f"{master_id}.json")
        elif target_device and target_device != "MASTER":
            target_file = os.path.join(sync_dir, f"{target_device}.json")
        else:
            target_file = None

        if not target_file or not os.path.exists(target_file):
            if master_id:
                target_file = os.path.join(sync_dir, f"{master_id}.json")
            else:
                json_files = [
                    f
                    for f in os.listdir(sync_dir)
                    if f.endswith(".json") and f != f"{self.bridge.sync_manager.device_id}.json"
                ]
                if json_files:
                    target_file = os.path.join(sync_dir, json_files[0])

        return target_file
