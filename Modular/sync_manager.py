import os
import json
import uuid
import shutil
import hashlib
from datetime import datetime
import git
import machineid
from PyQt6.QtCore import QObject, pyqtSignal

from core_sys import config, db

class SyncManager(QObject):
    sync_progress = pyqtSignal(str)
    sync_completed = pyqtSignal(bool, str)
    
    def __init__(self, device_id=None):
        super().__init__()
        self.device_id = device_id or self.get_device_id()
        self.repo = None
        self.repo_path = os.path.join(os.path.expanduser("~"), ".mindpalace_sync_repo")
        self.db_sync_dir = "db_exports" # NEW: Directory to hold individual device JSONs
        self.files_dir = "files"
        self.token = os.getenv('GITHUB_TOKEN', '')
        if not self.token: 
            self.token = config.get("sync_github_token", "")
        self.repo_url = config.get("sync_repo_url", "")

    def get_device_id(self):
        try: return machineid.id()
        except:
            try:
                import platform
                data = f"{platform.node()}-{platform.processor()}-{platform.machine()}"
                return hashlib.sha256(data.encode()).hexdigest()[:16]
            except:
                id_file = os.path.join(os.path.expanduser("~"), ".mindpalace_device_id")
                if os.path.exists(id_file):
                    with open(id_file, 'r') as f: return f.read().strip()
                else:
                    device_id = str(uuid.uuid4())
                    with open(id_file, 'w') as f: f.write(device_id)
                    return device_id
    
    def clean_git_locks(self):
        """Fixes fatal: Unable to create '/.../.git/index.lock': File exists."""
        lock_file = os.path.join(self.repo_path, '.git', 'index.lock')
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except Exception as e:
                print(f"[SyncManager] Failed to remove lock: {e}")

    def setup_repo(self):
        if not self.repo_url: return False, "No repository URL configured"
        os.environ['GIT_TERMINAL_PROMPT'] = '0'
        url = self.repo_url
        if not url.startswith('https://') and not url.startswith('http://'): url = 'https://' + url
        if self.token: url = url.replace("https://", f"https://{self.token}@")
            
        import subprocess
        if os.path.exists(self.repo_path):
            try:
                self.clean_git_locks()
                self.repo = git.Repo(self.repo_path)
                subprocess.run(['git', 'remote', 'set-url', 'origin', url], cwd=self.repo_path, capture_output=True)
                subprocess.run(['git', 'config', 'user.name', 'Mind Palace Sync'], cwd=self.repo_path)
                subprocess.run(['git', 'config', 'user.email', 'sync@mindpalace.os'], cwd=self.repo_path)
                subprocess.run(['git', 'config', 'http.postBuffer', '524288000'], cwd=self.repo_path)
                subprocess.run(['git', 'config', 'http.version', 'HTTP/1.1'], cwd=self.repo_path)
                subprocess.run(['git', 'config', 'pull.rebase', 'false'], cwd=self.repo_path) # Force merge strategy
                
                result = subprocess.run(['git', 'fetch', 'origin'], cwd=self.repo_path, capture_output=True, text=True)
                return True, "Repository ready"
            except Exception as e:
                shutil.rmtree(self.repo_path)
                return self.setup_repo()
        else:
            try:
                os.makedirs(os.path.dirname(self.repo_path), exist_ok=True)
                result = subprocess.run(['git', 'clone', url, self.repo_path], capture_output=True, text=True)
                if result.returncode == 0:
                    self.repo = git.Repo(self.repo_path)
                    subprocess.run(['git', 'config', 'user.name', 'Mind Palace Sync'], cwd=self.repo_path)
                    subprocess.run(['git', 'config', 'user.email', 'sync@mindpalace.os'], cwd=self.repo_path)
                    subprocess.run(['git', 'config', 'pull.rebase', 'false'], cwd=self.repo_path)
                    
                    gitignore_path = os.path.join(self.repo_path, '.gitignore')
                    with open(gitignore_path, 'w') as f:
                        f.write('*\n!db_exports/\n!db_exports/**\n!files/\n!files/**\n.idea/\n.vscode/\n*.swp\n.DS_Store\n')
                    subprocess.run(['git', 'add', '.gitignore'], cwd=self.repo_path)
                    subprocess.run(['git', 'commit', '-m', 'Init distributed sync rules'], cwd=self.repo_path)
                    subprocess.run(['git', 'push', '--set-upstream', 'origin', 'HEAD'], cwd=self.repo_path)
                    return True, "Repository cloned successfully"
                else: 
                    return False, f"Clone failed: {result.stderr}"
            except Exception as e: 
                return False, f"Failed to clone: {str(e)}"

    def ensure_uuids_and_timestamps(self):
        """Ensures every row in the DB has a UUID and timestamp to allow LWW Merging."""
        db.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence')")
        tables = [r[0] for r in db.c.fetchall()]
        now = datetime.now().isoformat()
        
        for table in tables:
            db.c.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in db.c.fetchall()]
            if 'uuid' not in cols or 'modified_at' not in cols:
                continue
                
            db.c.execute(f"SELECT id FROM {table} WHERE uuid IS NULL OR uuid = '' OR modified_at IS NULL OR modified_at = ''")
            rows = db.c.fetchall()
            for (row_id,) in rows:
                new_uuid = uuid.uuid4().hex
                db.c.execute(f"UPDATE {table} SET uuid=?, modified_at=? WHERE id=?", (new_uuid, now, row_id))
        db.conn.commit()

    def sync(self):
        if not config.get("sync_enabled", False): return False, "Sync is disabled in settings"
        self.sync_progress.emit("Starting distributed sync...")
        success, msg = self.setup_repo()
        if not success:
            self.sync_completed.emit(False, msg)
            return False, msg
            
        self.clean_git_locks()
        import subprocess
        
        # 1. PRE-FLIGHT: Prep local DB
        self.ensure_uuids_and_timestamps()
        
        # 2. PULL: Fetch all other devices' JSON files (No conflicts since paths are isolated)
        self.sync_progress.emit("Pulling cross-platform data...")
        try:
            subprocess.run(['git', 'rebase', '--abort'], cwd=self.repo_path, capture_output=True)
            subprocess.run(['git', 'merge', '--abort'], cwd=self.repo_path, capture_output=True)
            pull_res = subprocess.run(['git', 'pull', 'origin', 'HEAD', '--no-rebase', '--strategy-option=theirs'], cwd=self.repo_path, capture_output=True, text=True)
        except Exception as e:
            print("Pull warning:", e)
        
        # 3. MERGE: Apply remote data to local SQLite DB
        self.sync_progress.emit("Merging distributed databases...")
        self.merge_all_remote_data()
        
        # 4. EXPORT: Write the newly synced Local DB to this device's specific JSON
        self.sync_progress.emit("Exporting local state...")
        try:
            local_data = self.export_local_data()
            export_dir = os.path.join(self.repo_path, self.db_sync_dir)
            os.makedirs(export_dir, exist_ok=True)
            file_path = os.path.join(export_dir, f"{self.device_id}.json")
            
            with open(file_path, 'w') as f: 
                json.dump(local_data, f, indent=2)
        except Exception as e:
            self.sync_completed.emit(False, f"Export failed: {str(e)}")
            return False, f"Export failed: {str(e)}"
        
        # 5. SYNC FILES (PDFs/Images)
        self.sync_progress.emit("Syncing physical files...")
        try: self.sync_files()
        except: pass
        
        # 6. PUSH: Send this device's JSON back up to GitHub
        self.sync_progress.emit("Pushing to GitHub...")
        try:
            self.clean_git_locks()
            status_res = subprocess.run(['git', 'status', '--porcelain'], cwd=self.repo_path, capture_output=True, text=True)
            if status_res.stdout.strip():
                subprocess.run(['git', 'add', '-A'], cwd=self.repo_path)
                subprocess.run(['git', 'commit', '-m', f"Sync node update from {self.device_id}"], cwd=self.repo_path)
                push_res = subprocess.run(['git', 'push', 'origin', 'HEAD'], cwd=self.repo_path, capture_output=True, text=True)
                
                # Failsafe if another device pushed exactly right now
                if push_res.returncode != 0:
                    subprocess.run(['git', 'pull', 'origin', 'HEAD', '--no-rebase', '--strategy-option=theirs'], cwd=self.repo_path)
                    subprocess.run(['git', 'push', 'origin', 'HEAD'], cwd=self.repo_path)
                    
        except Exception as e:
            self.sync_completed.emit(False, f"Push failed: {str(e)}")
            return False, f"Push failed: {str(e)}"
        
        self.sync_completed.emit(True, "Distributed Sync completed successfully")
        return True, "Distributed Sync completed successfully"

    def merge_all_remote_data(self):
        """Reads all other devices' JSON exports and applies Last-Write-Wins logic."""
        import sqlite3
        sync_dir = os.path.join(self.repo_path, self.db_sync_dir)
        if not os.path.exists(sync_dir): return
        
        db.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence')")
        valid_tables = [r[0] for r in db.c.fetchall()]
        
        for filename in os.listdir(sync_dir):
            # Skip non-JSON or our OWN export file
            if not filename.endswith('.json') or filename == f"{self.device_id}.json":
                continue
                
            file_path = os.path.join(sync_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    remote_data = json.load(f)
                
                # Merge Settings (Last-Write-Wins based on a timestamp)
                remote_sync_time = remote_data.get("last_sync", "")
                local_sync_time = config.get("last_sync_timestamp", "")
                if remote_sync_time and (not local_sync_time or remote_sync_time > local_sync_time):
                    # Remote settings are newer, apply them
                    remote_settings = remote_data.get("settings", {})
                    for k, v in remote_settings.items():
                        config.set(k, v)
                    config.set("last_sync_timestamp", remote_sync_time)

                # Merge Tables
                tables = remote_data.get("tables", {})
                for table, rows in tables.items():
                    if table not in valid_tables: continue
                    
                    db.c.execute(f"PRAGMA table_info({table})")
                    columns = [info[1] for info in db.c.fetchall()]
                    if "uuid" not in columns or "modified_at" not in columns: continue
                        
                    for row in rows:
                        uid = row.get("uuid")
                        if not uid: continue
                        
                        incoming_mod = row.get("modified_at", "")
                        
                        db.c.execute(f"SELECT id, modified_at FROM {table} WHERE uuid = ?", (uid,))
                        existing = db.c.fetchone()
                        
                        if existing:
                            existing_id, existing_mod = existing
                            # Update if remote data is strictly newer
                            if not existing_mod or (incoming_mod and incoming_mod > existing_mod):
                                set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid"]])
                                values = [row[k] for k in row.keys() if k not in ["id", "uuid"]] + [existing_id]
                                try: 
                                    db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                                except sqlite3.IntegrityError: pass
                        else:
                            # Insert entirely new row
                            row.pop("id", None) # Remove remote ID to prevent PK conflicts
                            cols = ", ".join(row.keys())
                            placeholders = ", ".join(["?"] * len(row))
                            try: 
                                db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
                            except sqlite3.IntegrityError: pass
            except Exception as e:
                print(f"[SyncManager] Failed to merge node {filename}: {e}")
                
        db.conn.commit()
    
    def export_local_data(self):
        """Dumps entire SQLite state into this device's JSON payload."""
        settings = config.cfg.copy()
        settings.pop("sync_github_token", None) # Never export secrets
        
        now = datetime.now().isoformat()
        config.set("last_sync_timestamp", now)
        
        data = {
            "device_id": self.device_id, 
            "last_sync": now, 
            "settings": settings, 
            "tables": {}
        }
        
        db.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence')")
        tables = [r[0] for r in db.c.fetchall()]
        
        for table in tables:
            try:
                db.c.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in db.c.description]
                data["tables"][table] = [dict(zip(columns, row)) for row in db.c.fetchall()]
            except: pass
        return data
    
    def sync_files(self):
        local_paths = config.get("sync_local_paths", [])
        if not local_paths: return
        device_files_dir = os.path.join(self.repo_path, self.files_dir, self.device_id)
        os.makedirs(device_files_dir, exist_ok=True)
        
        for local_path in local_paths:
            if not os.path.exists(local_path): continue
            base_folder = os.path.basename(os.path.normpath(local_path))
            
            for root, dirs, files in os.walk(local_path):
                rel_path = os.path.relpath(root, local_path)
                target_dir = os.path.join(device_files_dir, base_folder, rel_path)
                if rel_path == '.': target_dir = os.path.join(device_files_dir, base_folder)
                os.makedirs(target_dir, exist_ok=True)
                
                for f in files:
                    src = os.path.join(root, f)
                    dst = os.path.join(target_dir, f)
                    try:
                        file_size_mb = os.path.getsize(src) / (1024 * 1024)
                        if file_size_mb > 95:
                            continue # Exceeds GitHub safe limits
                        shutil.copy2(src, dst)
                    except: pass

    def get_network_folders(self):
        network_dir = os.path.join(self.repo_path, self.files_dir)
        folders = []
        if os.path.exists(network_dir):
            for dev_id in os.listdir(network_dir):
                dev_path = os.path.join(network_dir, dev_id)
                if os.path.isdir(dev_path):
                    file_count = 0
                    latest_mod = 0
                    for root, _, files in os.walk(dev_path):
                        for f in files:
                            if '.git' in root: continue
                            file_count += 1
                            mod_time = os.path.getmtime(os.path.join(root, f))
                            if mod_time > latest_mod: latest_mod = mod_time
                            
                    last_update = datetime.fromtimestamp(latest_mod).strftime('%Y-%m-%d %H:%M') if latest_mod > 0 else "Never"
                    folders.append({
                        "device_id": dev_id,
                        "is_local": dev_id == self.device_id,
                        "file_count": file_count,
                        "last_update": last_update,
                        "path": dev_path
                    })
        return folders
