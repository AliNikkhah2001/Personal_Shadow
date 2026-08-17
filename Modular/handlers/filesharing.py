"""Filesharing advanced actions handler."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta
from typing import Any

from core_sys import config, db
from handlers import ActionHandler


class FileSharingHandler(ActionHandler):
    """Handles advanced filesharing operations."""

    actions: dict[str, str] = {
        "get_folder_hierarchy": "get_folder_hierarchy",
        "get_folder_changelog": "get_folder_changelog",
        "bind_folder_goal": "bind_folder_goal",
        "get_goal_folder_bindings": "get_goal_folder_bindings",
        "apply_retention_policy": "apply_retention_policy",
    }

    def __init__(self, bridge: Any) -> None:
        super().__init__(bridge)

    def get_folder_hierarchy(self, req: dict[str, Any]) -> str:
        path = req.get("path", "")
        if not path or not os.path.exists(path):
            return json.dumps({"error": "Folder not found", "tree": None})

        tree = self._build_tree(path, path)
        return json.dumps({"tree": tree})

    def _build_tree(self, root: str, current: str) -> dict:
        name = os.path.basename(current) or current
        is_dir = os.path.isdir(current)

        node = {
            "name": name,
            "path": current,
            "type": "directory" if is_dir else "file",
            "devices": self._get_file_devices(current),
        }

        if is_dir:
            children = []
            try:
                for entry in sorted(os.listdir(current)):
                    if entry.startswith(".") or entry == "__pycache__":
                        continue
                    child_path = os.path.join(current, entry)
                    children.append(self._build_tree(root, child_path))
            except PermissionError:
                pass
            node["children"] = children
        else:
            try:
                stat = os.stat(current)
                node["size"] = stat.st_size
                node["mtime"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            except OSError:
                pass

        return node

    def _get_file_devices(self, path: str) -> list[str]:
        devices = []
        repo_path = self.bridge.sync_manager.repo_path
        files_dir = os.path.join(repo_path, "files")
        if not os.path.exists(files_dir):
            return devices

        for manifest_file in os.listdir(files_dir):
            if not manifest_file.startswith("_manifest_"):
                continue
            dev_id = manifest_file.replace("_manifest_", "").replace(".json", "")
            manifest_path = os.path.join(files_dir, manifest_file)
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                rel = os.path.relpath(path, os.path.dirname(path))
                for key in manifest:
                    if rel in key or os.path.basename(path) in key:
                        devices.append(dev_id)
                        break
            except Exception:
                pass
        return devices

    def get_folder_changelog(self, req: dict[str, Any]) -> str:
        path = req.get("path", "")
        days = req.get("days", 30)
        max_changes = req.get("max_changes", 100)

        repo_path = self.bridge.sync_manager.repo_path
        if not os.path.exists(repo_path):
            return json.dumps({"changelog": []})

        try:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            result = subprocess.run(
                ["git", "log", f"--since={since}", f"--max-count={max_changes}",
                 "--pretty=format:%H|%ai|%an|%s", "--", os.path.basename(path)],
                cwd=repo_path, capture_output=True, text=True, timeout=30,
            )

            changelog = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    changelog.append({
                        "commit": parts[0],
                        "timestamp": parts[1],
                        "device_id": parts[2],
                        "action": "modified" if "modify" in parts[3].lower() else "added" if "add" in parts[3].lower() else "updated",
                        "file_path": parts[3],
                    })
            return json.dumps({"changelog": changelog})
        except Exception as e:
            return json.dumps({"error": str(e), "changelog": []})

    def bind_folder_goal(self, req: dict[str, Any]) -> str:
        folder = req.get("folder", "")
        goal_uuid = req.get("goal_uuid", "")

        bindings = config.get("folder_goal_bindings", {})
        if goal_uuid:
            bindings[folder] = goal_uuid
        else:
            bindings.pop(folder, None)
        config.set("folder_goal_bindings", bindings)
        return json.dumps({"status": "success"})

    def get_goal_folder_bindings(self, req: dict[str, Any]) -> str:
        bindings = config.get("folder_goal_bindings", {})
        return json.dumps({"bindings": bindings})

    def apply_retention_policy(self, req: dict[str, Any]) -> str:
        days = req.get("days", 30)
        max_changes = req.get("max_changes", 100)

        repo_path = self.bridge.sync_manager.repo_path
        if not os.path.exists(repo_path):
            return json.dumps({"message": "No repo found", "removed": 0})

        removed = 0
        try:
            export_dir = os.path.join(repo_path, self.bridge.sync_manager.db_sync_dir)
            if os.path.exists(export_dir):
                cutoff = datetime.now() - timedelta(days=days)
                for fname in os.listdir(export_dir):
                    fpath = os.path.join(export_dir, fname)
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                        if mtime < cutoff:
                            os.remove(fpath)
                            removed += 1
                    except Exception:
                        pass

            files_dir = os.path.join(repo_path, "files")
            if os.path.exists(files_dir):
                cutoff = datetime.now() - timedelta(days=days)
                for manifest_file in os.listdir(files_dir):
                    if not manifest_file.startswith("_manifest_"):
                        continue
                    fpath = os.path.join(files_dir, manifest_file)
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                        if mtime < cutoff:
                            os.remove(fpath)
                            removed += 1
                    except Exception:
                        pass

            subprocess.run(
                ["git", "gc", "--prune=now"], cwd=repo_path,
                capture_output=True, timeout=60,
            )

            return json.dumps({
                "message": f"Retention applied: {removed} old records removed (>{days} days)",
                "removed": removed,
            })
        except Exception as e:
            return json.dumps({"message": f"Error: {e}", "removed": 0})
