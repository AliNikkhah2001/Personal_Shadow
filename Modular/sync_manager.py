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
        self.sync_data_file = "sync_data.json"
        self.files_dir = "files"
        self.token = os.getenv('GITHUB_TOKEN', '')
        if not self.token: self.token = config.get("sync_github_token", "")
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
    
    def setup_repo(self):
        if not self.repo_url: return False, "No repository URL configured"
        os.environ['GIT_TERMINAL_PROMPT'] = '0'
        url = self.repo_url
        if not url.startswith('https://') and not url.startswith('http://'): url = 'https://' + url
        if self.token: url = url.replace("https://", f"https://{self.token}@")
            
        import subprocess
        if os.path.exists(self.repo_path):
            try:
                self.repo = git.Repo(self.repo_path)
                subprocess.run(['git', 'remote', 'set-url', 'origin', url], cwd=self.repo_path, capture_output=True)
                subprocess.run(['git', 'config', 'user.name', 'Mind Palace Sync'], cwd=self.repo_path)
                subprocess.run(['git', 'config', 'user.email', 'sync@mindpalace.os'], cwd=self.repo_path)
                subprocess.run(['git', 'config', 'http.postBuffer', '524288000'], cwd=self.repo_path)
                subprocess.run(['git', 'config', 'http.version', 'HTTP/1.1'], cwd=self.repo_path)
                
                result = subprocess.run(['git', 'fetch', '--dry-run'], cwd=self.repo_path, capture_output=True, text=True)
                if result.returncode == 0: return True, "Repository ready"
                else:
                    result = subprocess.run(['git', 'pull'], cwd=self.repo_path, capture_output=True, text=True)
                    if result.returncode == 0: return True, "Repository pulled successfully"
                    else: raise Exception(result.stderr)
            except Exception as e:
                print(f"Error with repo: {e}")
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
                    subprocess.run(['git', 'config', 'http.postBuffer', '524288000'], cwd=self.repo_path)
                    subprocess.run(['git', 'config', 'http.version', 'HTTP/1.1'], cwd=self.repo_path)
                    
                    gitignore_path = os.path.join(self.repo_path, '.gitignore')
                    with open(gitignore_path, 'w') as f:
                        f.write('*\n!sync_data.json\n!files/\n!files/**\n.idea/\n.vscode/\n*.swp\n*.swo\n.DS_Store\nThumbs.db\n*.tmp\n*.temp\n*.log\n')
                    subprocess.run(['git', 'add', '.gitignore'], cwd=self.repo_path)
                    subprocess.run(['git', 'commit', '-m', 'Add .gitignore for data-only sync'], cwd=self.repo_path)
                    subprocess.run(['git', 'push', '--set-upstream', 'origin', 'HEAD'], cwd=self.repo_path)
                    return True, "Repository cloned successfully"
                else: 
                    return False, f"Clone failed: {result.stderr}"
            except Exception as e: 
                return False, f"Failed to clone: {str(e)}"
                
    def sync(self):
        if not config.get("sync_enabled", False): return False, "Sync is disabled in settings"
        self.sync_progress.emit("Starting sync...")
        success, msg = self.setup_repo()
        if not success:
            self.sync_completed.emit(False, msg); return False, msg
            
        self.sync_progress.emit("Pulling latest data from GitHub...")
        import subprocess
        try:
            subprocess.run(['git', 'rebase', '--abort'], cwd=self.repo_path, capture_output=True)
            subprocess.run(['git', 'merge', '--abort'], cwd=self.repo_path, capture_output=True)
            result = subprocess.run(['git', 'pull', '--rebase'], cwd=self.repo_path, capture_output=True, text=True)
            if result.returncode != 0:
                subprocess.run(['git', 'rebase', '--abort'], cwd=self.repo_path, capture_output=True)
                subprocess.run(['git', 'fetch', 'origin'], cwd=self.repo_path, capture_output=True)
                subprocess.run(['git', 'reset', '--hard', 'FETCH_HEAD'], cwd=self.repo_path, capture_output=True)
        except Exception as e:
            self.sync_completed.emit(False, f"Pull exception: {str(e)}"); return False, f"Pull exception: {str(e)}"
        
        self.sync_progress.emit("Merging remote data...")
        remote_data_path = os.path.join(self.repo_path, self.sync_data_file)
        if os.path.exists(remote_data_path):
            try:
                with open(remote_data_path, 'r') as f: remote_data = json.load(f)
                self.merge_remote_data(remote_data)
            except Exception as e:
                self.sync_completed.emit(False, f"Merge failed: {str(e)}"); return False, f"Merge failed: {str(e)}"
        
        self.sync_progress.emit("Exporting local data...")
        try:
            local_data = self.export_local_data()
            with open(os.path.join(self.repo_path, self.sync_data_file), 'w') as f: json.dump(local_data, f, indent=2)
        except Exception as e:
            self.sync_completed.emit(False, f"Export failed: {str(e)}"); return False, f"Export failed: {str(e)}"
        
        self.sync_progress.emit("Syncing files...")
        try: self.sync_files()
        except: pass
        
        self.sync_progress.emit("Pushing to GitHub...")
        try:
            status_res = subprocess.run(['git', 'status', '--porcelain'], cwd=self.repo_path, capture_output=True, text=True)
            if status_res.stdout.strip():
                subprocess.run(['git', 'add', '-A'], cwd=self.repo_path)
                subprocess.run(['git', 'commit', '-m', f"Sync from {self.device_id}"], cwd=self.repo_path)
                push_res = subprocess.run(['git', 'push', 'origin', 'HEAD'], cwd=self.repo_path, capture_output=True, text=True)
                if push_res.returncode != 0:
                    subprocess.run(['git', 'pull', '--rebase'], cwd=self.repo_path)
                    subprocess.run(['git', 'push', 'origin', 'HEAD'], cwd=self.repo_path)
        except Exception as e:
            self.sync_completed.emit(False, f"Push failed: {str(e)}"); return False, f"Push failed: {str(e)}"
        
        self.sync_completed.emit(True, "Sync completed successfully")
        return True, "Sync completed successfully"

    def merge_remote_data(self, remote_data):
        import sqlite3
        tables = remote_data.get("tables", {})
        order = ["courses", "habits", "cascading_goals", "flashcards", "quizzes", "notes", "focus_queue", "habit_logs", "pomodoro_sessions", "health_profile", "health_logs"]
        for table in order:
            if table not in tables: continue
            for row in tables[table]:
                uid = row.get("uuid")
                if not uid: uid = uuid.uuid4().hex; row["uuid"] = uid
                db.c.execute(f"SELECT id, modified_at FROM {table} WHERE uuid = ?", (uid,))
                existing = db.c.fetchone()
                if existing:
                    existing_id, existing_mod = existing
                    incoming_mod = row.get("modified_at", "")
                    if not existing_mod or (incoming_mod and incoming_mod > existing_mod):
                        set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid"]])
                        values = [row[k] for k in row.keys() if k not in ["id", "uuid"]] + [existing_id]
                        try: db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                        except sqlite3.IntegrityError as e: pass
                else:
                    row.pop("id", None)
                    cols = ", ".join(row.keys()); placeholders = ", ".join(["?"] * len(row))
                    try: db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
                    except sqlite3.IntegrityError as e: pass
        db.conn.commit()
    
    def export_local_data(self):
        settings = config.cfg.copy(); settings.pop("sync_github_token", None)
        data = {"device_id": self.device_id, "last_sync": datetime.now().isoformat(), "settings": settings, "tables": {}}
        tables = ["courses", "pomodoro_sessions", "cascading_goals", "habits", "habit_logs", "flashcards", "quizzes", "focus_queue", "notes", "health_profile", "health_logs"]
        for table in tables:
            db.c.execute(f"SELECT * FROM {table}"); columns = [desc[0] for desc in db.c.description]
            data["tables"][table] = [dict(zip(columns, row)) for row in db.c.fetchall()]
        return data
    
    def sync_files(self):
        local_paths = config.get("sync_local_paths", [])
        if not local_paths: return
        device_files_dir = os.path.join(self.repo_path, self.files_dir, self.device_id)
        os.makedirs(device_files_dir, exist_ok=True)
        for local_path in local_paths:
            if not os.path.exists(local_path): continue
            for item in os.listdir(local_path):
                src = os.path.join(local_path, item); dst = os.path.join(device_files_dir, item)
                if os.path.isfile(src): shutil.copy2(src, dst)
                elif os.path.isdir(src): shutil.copytree(src, dst, dirs_exist_ok=True)
    
    def map_folder(self, local_path):
        paths = config.get("sync_local_paths", [])
        if local_path not in paths: paths.append(local_path); config.set("sync_local_paths", paths)
    
    def unmap_folder(self, local_path):
        paths = config.get("sync_local_paths", [])
        if local_path in paths: paths.remove(local_path); config.set("sync_local_paths", paths)