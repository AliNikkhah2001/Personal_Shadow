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
        "get_merged_folder_hierarchy": "get_merged_folder_hierarchy",
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

    def get_merged_folder_hierarchy(self, req: dict[str, Any]) -> str:
        """Build a merged folder hierarchy from local + all remote devices."""
        path = req.get("path", "")
        if not path or not os.path.exists(path):
            return json.dumps({"error": "Folder not found", "tree": None})

        # Build local tree
        local_tree = self._build_tree(path, path)

        # Get remote trees from all other devices
        repo_path = self.bridge.sync_manager.repo_path
        files_dir = os.path.join(repo_path, "files")
        remote_trees = {}

        if os.path.exists(files_dir):
            for entry in os.listdir(files_dir):
                entry_path = os.path.join(files_dir, entry)
                if entry.startswith("_manifest_") or entry == self.bridge.sync_manager.device_id:
                    continue
                if os.path.isdir(entry_path):
                    # Build tree for this remote device
                    rel_path = os.path.relpath(path, os.path.dirname(path))
                    remote_base = os.path.join(entry_path, rel_path)
                    if os.path.exists(remote_base):
                        remote_trees[entry] = self._build_tree(remote_base, remote_base)

        # Merge local and remote trees
        merged_tree = self._merge_trees(local_tree, remote_trees)
        return json.dumps({"tree": merged_tree})

    def _merge_trees(self, local_tree: dict, remote_trees: dict) -> dict:
        """Merge local tree with remote trees, combining devices list."""
        # Start with a copy of local tree
        merged = local_tree.copy()

        # Merge children recursively
        if "children" in local_tree and local_tree["children"]:
            # Start with a copy of ALL local children
            merged_children = [c.copy() for c in local_tree["children"]]
            # Index merged children by name for quick lookup
            merged_children_by_name = {c["name"]: c for c in merged_children}
            # Index local children by name
            local_children = {c["name"]: c for c in local_tree["children"]}

            # Merge remote children
            for dev_id, remote_tree in remote_trees.items():
                if "children" in remote_tree and remote_tree["children"]:
                    for child in remote_tree["children"]:
                        self._merge_child(merged_children, merged_children_by_name, local_children, child, dev_id)

            merged["children"] = merged_children

        # Merge devices list
        if "devices" in merged:
            all_devices = set(merged["devices"])
            for dev_id, remote_tree in remote_trees.items():
                if "devices" in remote_tree:
                    all_devices.update(remote_tree["devices"])
            merged["devices"] = list(all_devices)

        return merged

    def _merge_child(self, merged_children: list, merged_children_by_name: dict, local_children: dict, remote_child: dict, dev_id: str):
        """Merge a single remote child into the merged children list."""
        name = remote_child["name"]
        if name in merged_children_by_name:
            # Merge with existing merged child
            merged = merged_children_by_name[name]
            if "devices" in merged:
                merged["devices"] = list(set(merged["devices"] + [dev_id]))
            else:
                merged["devices"] = [dev_id]

            # Recursively merge children
            if "children" in remote_child and remote_child["children"]:
                if "children" not in merged:
                    merged["children"] = []
                merged_grandchildren = merged["children"] or []
                merged_grandchildren_by_name = {c["name"]: c for c in merged_grandchildren}
                # We need the local grandchildren for comparison
                local_grandchildren = {}
                # Find the corresponding local child
                for c in local_children.values():
                    if c["name"] == name and "children" in c:
                        local_grandchildren = {gc["name"]: gc for gc in c["children"]}
                        break
                for grandchild in remote_child["children"]:
                    self._merge_child(merged_grandchildren, merged_grandchildren_by_name, local_grandchildren, grandchild, dev_id)
                merged["children"] = merged_grandchildren

            # Update the lookup
            merged_children_by_name[name] = merged
        else:
            # Add new child from remote
            new_child = remote_child.copy()
            new_child["devices"] = new_child.get("devices", []) + [dev_id]
            merged_children.append(new_child)
            merged_children_by_name[name] = new_child

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
