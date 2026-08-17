import base64
import contextlib
import hashlib
import json
import logging
import os
import shutil
import uuid
from datetime import datetime

import git
import machineid
from git import RemoteProgress
from PyQt6.QtCore import QObject, pyqtSignal

from core_sys import config, db


class DetailedSyncProgress(RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=""):
        pct = (cur_count / (max_count or 100.0)) * 100
        msg = f"Git Sync: {message} ({pct:.1f}%)"
        logging.debug(msg)
        print(msg)


class SyncManager(QObject):
    sync_progress = pyqtSignal(str)
    sync_completed = pyqtSignal(bool, str)

    def __init__(self, device_id=None):
        super().__init__()
        self.device_id = device_id or self.get_device_id()
        self.repo = None
        self.repo_path = os.path.join(os.path.expanduser("~"), ".mindpalace_sync_repo")
        self.db_sync_dir = "db_exports"
        self.sync_data_file = os.path.join(self.db_sync_dir, f"{self.device_id}.json")
        self.files_dir = "files"
        self.token = os.getenv("GITHUB_TOKEN", "")
        if not self.token:
            self.token = config.get("sync_github_token", "")
        self.repo_url = config.get("sync_repo_url", "https://github.com/AliNikkhah2001/MindPalaceData.git")

    def get_device_id(self):
        try:
            return machineid.id()
        except Exception:
            try:
                import platform

                data = f"{platform.node()}-{platform.processor()}-{platform.machine()}"
                return hashlib.sha256(data.encode()).hexdigest()[:16]
            except Exception:
                id_file = os.path.join(os.path.expanduser("~"), ".mindpalace_device_id")
                if os.path.exists(id_file):
                    with open(id_file) as f:
                        return f.read().strip()
                else:
                    device_id = str(uuid.uuid4())
                    with open(id_file, "w") as f:
                        f.write(device_id)
                    return device_id

    def _get_all_tables(self):
        db.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence')")
        return [r[0] for r in db.c.fetchall()]

    def _get_master_id(self):
        cluster_file = os.path.join(self.repo_path, "cluster_state.json")
        if os.path.exists(cluster_file):
            try:
                with open(cluster_file) as f:
                    return json.load(f).get("master_id")
            except Exception:
                pass
        return None

    def clean_git_locks(self):
        lock_file = os.path.join(self.repo_path, ".git", "index.lock")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except Exception as e:
                print(f"[SyncManager] Failed to remove lock: {e}")

    def _init_git_lfs(self):
        """Initialize Git LFS for large file tracking."""
        try:
            import subprocess
            # Check if git-lfs is installed
            result = subprocess.run(["git", "lfs", "version"], capture_output=True, text=True)
            if result.returncode != 0:
                print("[SyncManager] Git LFS not found. Large files will not use LFS.")
                return
            # Install git-lfs hooks
            subprocess.run(["git", "lfs", "install", "--skip-smudge"], cwd=self.repo_path, capture_output=True)
            print("[SyncManager] Git LFS initialized.")
        except Exception as e:
            print(f"[SyncManager] Git LFS init error: {e}")

    def setup_repo(self, _retries=0):
        if not self.repo_url:
            return False, "No repository URL configured"
        if _retries >= 3:
            return False, f"Failed to setup repo after {_retries} attempts"
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
        url = self.repo_url
        # Support file://, ssh://, git://, http://, https:// URLs
        if not (url.startswith("https://") or url.startswith("http://") or url.startswith("file://") or url.startswith("ssh://") or url.startswith("git://") or "@" in url):
            url = "https://" + url
        if self.token and url.startswith("https://"):
            url = url.replace("https://", f"https://{self.token}@")

        import subprocess

        if os.path.exists(self.repo_path):
            try:
                self.clean_git_locks()
                self.repo = git.Repo(self.repo_path)
                subprocess.run(["git", "remote", "set-url", "origin", url], cwd=self.repo_path, capture_output=True)
                subprocess.run(["git", "config", "user.name", "Mind Palace Sync"], cwd=self.repo_path)
                subprocess.run(["git", "config", "user.email", "sync@mindpalace.os"], cwd=self.repo_path)
                subprocess.run(["git", "config", "http.postBuffer", "524288000"], cwd=self.repo_path)
                subprocess.run(["git", "config", "http.version", "HTTP/1.1"], cwd=self.repo_path)
                subprocess.run(["git", "config", "pull.rebase", "false"], cwd=self.repo_path)

                # Initialize Git LFS if not already set up
                self._init_git_lfs()

                # REWRITE GITIGNORE TO FIX OLD AGGRESSIVE WILDCARDS
                gitignore_path = os.path.join(self.repo_path, ".gitignore")
                with open(gitignore_path, "w") as f:
                    f.write(".idea/\n.vscode/\n*.swp\n.DS_Store\n")
                self.repo.git.add(".gitignore")

                result = subprocess.run(["git", "fetch", "origin"], cwd=self.repo_path, capture_output=True, text=True)
                return True, "Repository ready"
            except Exception:
                shutil.rmtree(self.repo_path)
                return self.setup_repo(_retries=_retries + 1)
        else:
            try:
                os.makedirs(os.path.dirname(self.repo_path), exist_ok=True)
                result = subprocess.run(["git", "clone", url, self.repo_path], capture_output=True, text=True)
                if result.returncode == 0:
                    self.repo = git.Repo(self.repo_path)
                    subprocess.run(["git", "config", "user.name", "Mind Palace Sync"], cwd=self.repo_path)
                    subprocess.run(["git", "config", "user.email", "sync@mindpalace.os"], cwd=self.repo_path)
                    subprocess.run(["git", "config", "pull.rebase", "false"], cwd=self.repo_path)

                    # Initialize Git LFS if not already set up
                    self._init_git_lfs()

                    gitignore_path = os.path.join(self.repo_path, ".gitignore")
                    with open(gitignore_path, "w") as f:
                        f.write(".idea/\n.vscode/\n*.swp\n.DS_Store\n")
                    subprocess.run(["git", "add", ".gitignore"], cwd=self.repo_path)
                    subprocess.run(["git", "commit", "-m", "Init distributed sync rules"], cwd=self.repo_path)
                    subprocess.run(["git", "push", "--set-upstream", "origin", "HEAD"], cwd=self.repo_path)
                    return True, "Repository cloned successfully"
                else:
                    return False, f"Clone failed: {result.stderr}"
            except Exception as e:
                return False, f"Failed to clone: {e!s}"

    def ensure_uuids_and_timestamps(self):
        db.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence')")
        tables = [r[0] for r in db.c.fetchall()]
        now = datetime.now().isoformat()

        for table in tables:
            db.c.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in db.c.fetchall()]
            if "uuid" not in cols or "modified_at" not in cols:
                continue

            db.c.execute(
                f"SELECT id FROM {table} WHERE uuid IS NULL OR uuid = '' OR modified_at IS NULL OR modified_at = ''"
            )
            rows = db.c.fetchall()
            for (row_id,) in rows:
                new_uuid = uuid.uuid4().hex
                db.c.execute(f"UPDATE {table} SET uuid=?, modified_at=? WHERE id=?", (new_uuid, now, row_id))
        db.safe_commit()

    def force_overwrite_remote(self):
        """DANGER ZONE: Purge remote device branches and force this device to be the Master"""
        self.sync_progress.emit("Starting MASTER OVERWRITE sync...")
        success, msg = self.setup_repo()
        if not success:
            self.sync_completed.emit(False, msg)
            return False, msg

        self.sync_progress.emit("Pulling latest data to prevent push conflicts...")
        try:
            origin = self.repo.remotes.origin
            origin.pull(rebase=False, progress=DetailedSyncProgress())
        except Exception:
            pass

        self.sync_progress.emit("Clearing other nodes' data from cluster...")
        sync_dir = os.path.join(self.repo_path, self.db_sync_dir)
        if os.path.exists(sync_dir):
            for f in os.listdir(sync_dir):
                if f.endswith(".json") and f != f"{self.device_id}.json":
                    with contextlib.suppress(BaseException):
                        os.remove(os.path.join(sync_dir, f))

        # Also clear remote JSONs in repo (already done)

        self.sync_progress.emit("Exporting Master local data...")
        self.ensure_uuids_and_timestamps()
        # Clear local deletion log (master should not have pending deletions)
        db.c.execute("DELETE FROM deleted_uuids")
        db.safe_commit()

        try:
            local_data = self.export_local_data()
            export_path = os.path.join(self.repo_path, self.sync_data_file)
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            with open(export_path, "w") as f:
                json.dump(local_data, f, indent=2)
        except Exception as e:
            self.sync_completed.emit(False, f"Export failed: {e!s}")
            return False, f"Export failed: {e!s}"

        self.sync_progress.emit("Force Pushing Master to GitHub...")
        try:
            # CRITICAL: Force add the export path to bypass any lingering gitignore rules
            if os.path.exists(export_path):
                self.repo.git.add(export_path, force=True)
            self.repo.git.add(all=True)

            if self.repo.is_dirty() or self.repo.untracked_files:
                self.repo.index.commit(f"MASTER OVERWRITE from {self.device_id}")
            origin.push(progress=DetailedSyncProgress())
            logging.info("Git Master Force Push Successful")
        except Exception as e:
            self.sync_completed.emit(False, f"Push failed: {e!s}")
            return False, f"Push failed: {e!s}"

        self.sync_completed.emit(True, "Master Overwrite completed successfully")
        return True, "Master Overwrite completed successfully"

    def sync(self):
        if not config.get("sync_enabled", False):
            return False, "Sync is disabled in settings"
        self.sync_progress.emit("Starting sync...")
        success, msg = self.setup_repo()
        if not success:
            self.sync_completed.emit(False, msg)
            return False, msg

        self.sync_progress.emit("Pulling latest data from GitHub...")
        try:
            origin = self.repo.remotes.origin
            origin.pull(rebase=False, progress=DetailedSyncProgress())
            logging.info("Git Pull Successful")
        except Exception as e:
            logging.error(f"Pull exception: {e}")
            self.sync_completed.emit(False, f"Pull exception: {e!s}")
            return False, f"Pull exception: {e!s}"

        self.sync_progress.emit("Merging remote data...")
        self.ensure_uuids_and_timestamps()
        try:
            self.merge_all_remote_data()
        except Exception as e:
            self.sync_completed.emit(False, f"Merge failed: {e!s}")
            return False, f"Merge failed: {e!s}"

        self.sync_progress.emit("Exporting local data...")
        try:
            local_data = self.export_local_data()
            export_path = os.path.join(self.repo_path, self.sync_data_file)
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            with open(export_path, "w") as f:
                json.dump(local_data, f, indent=2)
        except Exception as e:
            self.sync_completed.emit(False, f"Export failed: {e!s}")
            return False, f"Export failed: {e!s}"

        self.sync_progress.emit("Syncing files...")
        with contextlib.suppress(BaseException):
            self.sync_files()

        self.sync_progress.emit("Pushing to GitHub...")
        try:
            # CRITICAL: Force add the export path to bypass any lingering gitignore rules
            if os.path.exists(export_path):
                self.repo.git.add(export_path, force=True)
            self.repo.git.add(all=True)

            if self.repo.is_dirty() or self.repo.untracked_files:
                self.repo.index.commit(f"Sync from {self.device_id}")
            origin.push(progress=DetailedSyncProgress())
            logging.info("Git Push Successful")
        except Exception as e:
            logging.error(f"Push failed: {e}")
            self.sync_completed.emit(False, f"Push failed: {e!s}")
            return False, f"Push failed: {e!s}"

        self.sync_completed.emit(True, "Sync completed successfully")
        return True, "Sync completed successfully"

    def merge_all_remote_data(self):
        import sqlite3

        sync_dir = os.path.join(self.repo_path, self.db_sync_dir)
        if not os.path.exists(sync_dir):
            return

        master_id = self._get_master_id()
        valid_tables = self._get_all_tables()

        # Read all remote JSONs
        remote_data_by_device = {}
        for filename in os.listdir(sync_dir):
            if not filename.endswith(".json") or filename == f"{self.device_id}.json":
                continue
            try:
                with open(os.path.join(sync_dir, filename)) as f:
                    remote_data_by_device[filename.replace(".json", "")] = json.load(f)
            except Exception as e:
                print(f"Failed to read {filename}: {e}")

        # Collect all deleted UUIDs across all tables to prevent re-import
        db.c.execute("SELECT table_name, uuid FROM deleted_uuids")
        deleted_set = {(t, u) for t, u in db.c.fetchall()}

        # Process each table
        for table in valid_tables:
            # Apply deletions from all remote devices
            for _dev_id, remote_data in remote_data_by_device.items():
                for del_item in remote_data.get("deletions", {}).get(table, []):
                    uid = del_item["uuid"]
                    del_time = del_item["deleted_at"]
                    db.c.execute(f"SELECT modified_at FROM {table} WHERE uuid = ?", (uid,))
                    row = db.c.fetchone()
                    if row and (not row[0] or del_time > row[0]):
                        db.c.execute(f"DELETE FROM {table} WHERE uuid = ?", (uid,))
                        db.c.execute("DELETE FROM deleted_uuids WHERE table_name=? AND uuid=?", (table, uid))
                        deleted_set.add((table, uid))

            # Merge rows (master wins, else last-write-wins)
            db.c.execute(f"PRAGMA table_info({table})")
            cols = [info[1] for info in db.c.fetchall()]
            if "uuid" not in cols or "modified_at" not in cols:
                continue

            for dev_id, remote_data in remote_data_by_device.items():
                rows = remote_data.get("tables", {}).get(table, [])
                for row in rows:
                    row = {key: self._decode_json_value(value) for key, value in row.items()}
                    uid = row.get("uuid")
                    if not uid:
                        continue
                    if (table, uid) in deleted_set:
                        continue
                    db.c.execute(f"SELECT id, modified_at FROM {table} WHERE uuid = ?", (uid,))
                    existing = db.c.fetchone()
                    if not existing:
                        row.pop("id", None)
                        cols = ", ".join(row.keys())
                        placeholders = ", ".join(["?"] * len(row))
                        with contextlib.suppress(sqlite3.IntegrityError):
                            db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
                    else:
                        existing_id, existing_mod = existing
                        incoming_mod = row.get("modified_at", "")
                        remote_is_master = dev_id == master_id
                        if remote_is_master:
                            set_clause = ", ".join([f"{k}=?" for k in row if k not in ["id", "uuid"]])
                            values = [row[k] for k in row if k not in ["id", "uuid"]] + [existing_id]
                            with contextlib.suppress(sqlite3.IntegrityError):
                                db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id=?", values)
                        else:
                            if incoming_mod and (not existing_mod or incoming_mod > existing_mod):
                                set_clause = ", ".join([f"{k}=?" for k in row if k not in ["id", "uuid"]])
                                values = [row[k] for k in row if k not in ["id", "uuid"]] + [existing_id]
                                with contextlib.suppress(sqlite3.IntegrityError):
                                    db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id=?", values)
        db.safe_commit()

    def export_local_data(self):
        settings = config.cfg.copy()
        settings.pop("sync_github_token", None)

        now = datetime.now().isoformat()
        config.set("last_sync_timestamp", now)

        data = {"device_id": self.device_id, "last_sync": now, "settings": settings, "tables": {}, "deletions": {}}

        tables = self._get_all_tables()

        for table in tables:
            try:
                db.c.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in db.c.description]
                data["tables"][table] = [
                    {column: self._encode_json_value(value) for column, value in zip(columns, row, strict=True)}
                    for row in db.c.fetchall()
                ]
            except Exception as exc:
                logging.warning("Could not export table %s: %s", table, exc)

        # Add deletions
        for table in tables:
            db.c.execute("SELECT uuid, deleted_at FROM deleted_uuids WHERE table_name=?", (table,))
            data["deletions"][table] = [{"uuid": r[0], "deleted_at": r[1]} for r in db.c.fetchall()]

        return data

    @staticmethod
    def _encode_json_value(value):
        if isinstance(value, bytes):
            return {"__blob_base64__": base64.b64encode(value).decode("ascii")}
        return value

    @staticmethod
    def _decode_json_value(value):
        if isinstance(value, dict) and set(value) == {"__blob_base64__"}:
            return base64.b64decode(value["__blob_base64__"])
        return value

    def sync_files(self):
        local_paths = config.get("sync_local_paths", [])
        if not local_paths:
            return

        shared_files_dir = os.path.join(self.repo_path, self.files_dir)
        manifest_path = os.path.join(shared_files_dir, f"_manifest_{self.device_id}.json")

        local_manifest = {}
        lfs_files = []  # Track files that need LFS
        LFS_THRESHOLD = 10 * 1024 * 1024  # 10MB threshold for LFS

        for local_path in local_paths:
            if not os.path.exists(local_path):
                continue
            base_folder = os.path.basename(os.path.normpath(local_path))
            for root, _dirs, files in os.walk(local_path):
                rel_path = os.path.relpath(root, local_path)
                for f in files:
                    src = os.path.join(root, f)
                    try:
                        stat = os.stat(src)
                        # Track LFS candidates (files > 10MB)
                        file_key = os.path.join(base_folder, rel_path, f) if rel_path != "." else os.path.join(base_folder, f)
                        if stat.st_size > LFS_THRESHOLD:
                            lfs_files.append(file_key)
                        # Skip extremely large files (>100MB) to prevent issues
                        if stat.st_size > 100 * 1024 * 1024:
                            continue
                        if rel_path == ".":
                            key = os.path.join(base_folder, f)
                        else:
                            key = os.path.join(base_folder, rel_path, f)
                        local_manifest[key] = {
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                            "src": src,
                        }
                    except Exception:
                        pass

        prev_manifest = {}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path) as f:
                    prev_manifest = json.load(f)
            except Exception:
                pass

        new_files = 0
        changed_files = 0
        deleted_files = 0

        for key, info in local_manifest.items():
            dst = os.path.join(shared_files_dir, key)
            prev = prev_manifest.get(key)
            if prev and prev.get("size") == info["size"] and prev.get("mtime") == info["mtime"]:
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                shutil.copy2(info["src"], dst)
                if prev:
                    changed_files += 1
                else:
                    new_files += 1
            except Exception:
                pass

        for key in prev_manifest:
            if key not in local_manifest:
                dst = os.path.join(shared_files_dir, key)
                if os.path.exists(dst):
                    try:
                        os.remove(dst)
                        deleted_files += 1
                    except Exception:
                        pass

        for key, info in local_manifest.items():
            remote_file = os.path.join(shared_files_dir, key)
            if os.path.exists(remote_file):
                try:
                    remote_stat = os.stat(remote_file)
                    local_stat = os.stat(info["src"])
                    if remote_stat.st_mtime > local_stat.st_mtime:
                        os.makedirs(os.path.dirname(info["src"]), exist_ok=True)
                        shutil.copy2(remote_file, info["src"])
                except Exception:
                    pass

        # Update .gitattributes for Git LFS
        if lfs_files:
            gitattributes_path = os.path.join(self.repo_path, ".gitattributes")
            lfs_patterns = []
            for f in lfs_files:
                # Escape special characters for gitattributes
                pattern = f.replace("[", "\\[").replace("]", "\\]").replace("*", "\\*")
                lfs_patterns.append(f"{pattern} filter=lfs diff=lfs merge=lfs -text")
            try:
                with open(gitattributes_path, "w") as f:
                    f.write("# Git LFS tracking\n")
                    f.write("\n".join(lfs_patterns) + "\n")
                self.repo.git.add(".gitattributes")
            except Exception:
                pass

        with open(manifest_path, "w") as f:
            json.dump(
                {k: {"size": v["size"], "mtime": v["mtime"]} for k, v in local_manifest.items()},
                f,
            )

        self.sync_progress.emit(
            f"Files: {new_files} new, {changed_files} changed, {deleted_files} deleted" + (
                f" + {len(lfs_files)} LFS" if lfs_files else ""
            )
        )

    def get_network_folders(self):
        network_dir = os.path.join(self.repo_path, self.files_dir)
        folders = []
        if os.path.exists(network_dir):
            for entry in os.listdir(network_dir):
                entry_path = os.path.join(network_dir, entry)
                if entry.startswith("_manifest_"):
                    continue
                if os.path.isdir(entry_path):
                    file_count = 0
                    latest_mod = 0
                    for root, _, files in os.walk(entry_path):
                        for f in files:
                            if ".git" in root:
                                continue
                            file_count += 1
                            mod_time = os.path.getmtime(os.path.join(root, f))
                            if mod_time > latest_mod:
                                latest_mod = mod_time

                    last_update = (
                        datetime.fromtimestamp(latest_mod).strftime("%Y-%m-%d %H:%M") if latest_mod > 0 else "Never"
                    )
                    folders.append(
                        {
                            "device_id": entry,
                            "is_local": entry == self.device_id,
                            "file_count": file_count,
                            "last_update": last_update,
                            "path": entry_path,
                        }
                    )

            manifest_files = [f for f in os.listdir(network_dir) if f.startswith("_manifest_")]
            for mf in manifest_files:
                dev_id = mf.replace("_manifest_", "").replace(".json", "")
                manifest_path = os.path.join(network_dir, mf)
                try:
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                    existing = next((x for x in folders if x["device_id"] == dev_id), None)
                    if existing:
                        existing["file_count"] = len(manifest)
                except Exception:
                    pass

        return folders

    def map_folder(self, local_path):
        paths = config.get("sync_local_paths", [])
        if local_path not in paths:
            paths.append(local_path)
            config.set("sync_local_paths", paths)

    def unmap_folder(self, local_path):
        paths = config.get("sync_local_paths", [])
        if local_path in paths:
            paths.remove(local_path)
            config.set("sync_local_paths", paths)
