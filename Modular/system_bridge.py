import sys
import os
import json
import base64
import subprocess
import uuid
import io
import zipfile
import threading
import traceback
from datetime import datetime, timedelta

from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QTimer, Qt, QTime, QByteArray, QBuffer, QIODevice, QRectF
from PyQt6.QtGui import QImage, QPainter, QColor, QBrush, QPen, QFont
from PyQt6.QtWidgets import QWidget, QApplication, QFileDialog

from core_sys import config, db, get_color, play_system_sound, speak_text, set_max_volume, GITHUB_TOKEN
from vision_tracker import VisionTracker
from sync_manager import SyncManager
from horology import draw_clock_face, draw_clock_ticks_and_indices, draw_clock_complications, draw_horological_hand

class OverlayWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(200, 200)
        self.sp = 0; self.dp = 0; self.txt = "00:00"; self.sm = 0; self.pm = 1
        self.ring_color = QColor("#0a84ff"); self.bg_override_color = None
        sc = QApplication.primaryScreen().geometry()
        self.move(sc.width() // 2 - 100, 20)

    def update_state(self, time_str, progress_pct, worked_mins, total_mins, active_course, distraction_mode):
        self.txt = time_str; self.sp = progress_pct / 100.0; self.sm = worked_mins; self.pm = total_mins; self.dp = min(self.sm / max(self.pm, 1), 1.0)
        self.ring_color = get_color(active_course)
        if distraction_mode == "App": self.bg_override_color = QColor(255, 140, 0, 220)
        elif distraction_mode == "Camera": self.bg_override_color = QColor(255, 50, 50, 220)
        else: self.bg_override_color = None
        self.update()
        
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); radius = 90; p.translate(100, 100)
        bg_col = self.bg_override_color if self.bg_override_color else QColor(15, 15, 17, 220)
        draw_clock_face(p, radius, bg_col); p.setPen(QPen(QColor(255,255,255,30), 8)); p.drawArc(-70, -70, 140, 140, 0, 360*16); p.setPen(QPen(self.ring_color, 8, cap=Qt.PenCapStyle.RoundCap)); p.drawArc(-70, -70, 140, 140, 90*16, int(-self.sp * 360 * 16)); p.setPen(QColor("white")); p.setFont(QFont("Arial", 16, QFont.Weight.Bold)); p.drawText(QRectF(-90, 20, 180, 40), Qt.AlignmentFlag.AlignCenter, self.txt)
        draw_clock_ticks_and_indices(p, radius); draw_clock_complications(p, radius)
        t = QTime.currentTime(); h_style = config.get("clock_hands", "Classic")
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("white")))
        p.save(); p.rotate(30.0 * (t.hour() + t.minute()/60.0)); draw_horological_hand(p, h_style, 45, 3, True); p.restore()
        p.save(); p.rotate(6.0 * (t.minute() + t.second()/60.0)); draw_horological_hand(p, h_style, 65, 2, False); p.restore()
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("white"))); p.drawEllipse(-3, -3, 6, 6)

class SystemBridge(QObject):
    state_update = pyqtSignal(str)
    video_feed = pyqtSignal(str)
    clock_feed = pyqtSignal(str)
    sync_completed = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.ovl = OverlayWidget()
        self.vision = VisionTracker()
        self.timer = QTimer(); self.timer.timeout.connect(self.tick)
        self.clock_timer = QTimer(); self.clock_timer.timeout.connect(self.emit_clock); self.clock_timer.start(1000)
        self.is_running = False; self.time_left = 0; self.total_time = 0; self.current_course = "General"; self.distractions = 0; self.distraction_markers = [] 
        
        self.quiet_mode = config.get("quiet_mode", False)
        self.sync_manager = SyncManager()
        self.sync_timer = QTimer(); self.sync_timer.timeout.connect(self.auto_sync)
        if config.get("sync_enabled", False): self.sync_timer.start(config.get("sync_interval", 3600) * 1000)
        
        self.backup_timer = QTimer()
        self.backup_timer.timeout.connect(self.backup_data)
        self.backup_timer.start(3600 * 1000)

    def get_running_processes(self):
        processes = []
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cpu_percent', 'memory_percent']):
                try:
                    info = proc.info
                    processes.append({'pid': info['pid'], 'name': info['name'], 'cpu': info['cpu_percent'] or 0, 'memory': info['memory_percent'] or 0})
                except: pass
            processes.sort(key=lambda x: x['cpu'], reverse=True)
            return processes
        except ImportError:
            if sys.platform == "win32":
                try:
                    res = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True)
                    for line in res.stdout.strip().split('\n'):
                        parts = line.strip('"').split('","')
                        if len(parts) >= 2: processes.append({'pid': parts[1], 'name': parts[0], 'cpu': 0, 'memory': 0})
                except: pass
            else:
                try:
                    res = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                    for line in res.stdout.strip().split('\n')[1:]:
                        parts = line.split()
                        if len(parts) >= 11: processes.append({'pid': parts[1], 'name': parts[10] if len(parts) > 10 else parts[0], 'cpu': 0, 'memory': 0})
                except: pass
        return processes

    def check_processes_for_distraction(self):
        if not config.get("app_monitoring_enabled", False): return []
        allowed = config.get("allowed_apps", [])
        blocked = config.get("blocked_apps", [])
        if not blocked and not allowed: return []
        
        running = self.get_running_processes()
        distractions = []
        
        for proc in running:
            proc_name = proc['name'].lower()
            if blocked:
                for b in blocked:
                    if b.lower() in proc_name: distractions.append(proc); break
            elif allowed:
                is_allowed = False
                for a in allowed:
                    if a.lower() in proc_name: is_allowed = True; break
                if not is_allowed: distractions.append(proc)
        return distractions

    def kill_processes(self, processes):
        try:
            import psutil
            for proc in processes[:3]:
                try: psutil.Process(proc['pid']).terminate()
                except: pass
        except: pass

    def handle_sync_result(self, success, msg):
        if not success: QApplication.beep()

    def auto_sync(self):
        if config.get("sync_enabled", False): self.sync_manager.sync()

    def backup_data(self):
        backup_dir = os.path.join(os.path.expanduser("~"), "MindPalaceBackups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"auto_backup_{timestamp}.zip")
        settings = config.cfg.copy(); settings.pop("sync_github_token", None)
        data = {"settings": settings, "tables": {}}
        tables = ["courses", "pomodoro_sessions", "cascading_goals", "habits", "habit_logs", "flashcards", "quizzes", "focus_queue", "notes", "health_profile", "health_logs"]
        for table in tables:
            db.c.execute(f"SELECT * FROM {table}"); columns = [desc[0] for desc in db.c.description]
            data["tables"][table] = [dict(zip(columns, row)) for row in db.c.fetchall()]
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("data.json", json.dumps(data, indent=2))
        with open(backup_path, 'wb') as f: f.write(zip_buffer.getvalue())

    @pyqtSlot(str, result=str)
    def request(self, payload):
        req = json.loads(payload)
        action = req.get("action")

        if action == "init":
            today_str = datetime.now().date().isoformat()
            ydy_str = (datetime.now().date() - timedelta(days=1)).isoformat()
            db.c.execute("SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?", (today_str,))
            tdy_study = db.c.fetchone()[0] or 0
            db.c.execute("SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?", (ydy_str,))
            ydy_study = db.c.fetchone()[0] or 0
            db.c.execute("SELECT sum(distractions) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?", (today_str,))
            tdy_dist = db.c.fetchone()[0] or 0
            db.c.execute("SELECT sum(distractions) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?", (ydy_str,))
            ydy_dist = db.c.fetchone()[0] or 0
            
            vols = []
            for h in range(8, 20):
                db.c.execute("SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=? AND cast(strftime('%H', timestamp) as integer)=?", (today_str, h))
                vols.append((db.c.fetchone()[0] or 0) / 60.0)
                
            db.c.execute("SELECT data_json FROM health_profile ORDER BY id DESC LIMIT 1")
            h_prof = db.c.fetchone()
            
            db.c.execute("SELECT log_type, date, data_json FROM health_logs")
            h_logs = [{"type": r[0], "date": r[1], "data": json.loads(r[2])} for r in db.c.fetchall()]

            return json.dumps({
                "flat_goals": [r[0] for r in db.c.execute("SELECT title FROM cascading_goals").fetchall()],
                "goals": [{"id": r[0], "title": r[1], "target_hours": r[2], "deadline": r[3], "parent_id": r[4]} for r in db.c.execute("SELECT id, title, target_hours, deadline, parent_id FROM cascading_goals").fetchall()],
                "heatmap": self.get_heatmap_data(),
                "settings": config.cfg,
                "habits": [{"id": r[0], "name": r[1], "type": r[2]} for r in db.c.execute("SELECT id, name, type FROM habits").fetchall()],
                "habit_logs": [{"habit_id": r[0], "date": r[1], "status": r[2]} for r in db.c.execute("SELECT habit_id, date, status FROM habit_logs").fetchall()],
                "flashcards": [{"id": r[0], "front": r[1], "back": r[2], "deck": r[3], "course": r[4], "folder": r[5], "color": r[6]} for r in db.c.execute("SELECT id, front, back, deck, course, folder, color FROM flashcards").fetchall()],
                "quizzes": [{"id": r[0], "title": r[1], "json": r[2], "course": r[3], "folder": r[4], "color": r[5]} for r in db.c.execute("SELECT id, title, questions_json, course, folder, color FROM quizzes").fetchall()],
                "queue": [{"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]} for r in db.c.execute("SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id").fetchall()],
                "notes": [{"id": r[0], "title": r[1], "content": r[2], "course": r[3], "folder": r[4], "color": r[5]} for r in db.c.execute("SELECT id, title, content, course, folder, color FROM notes ORDER BY id DESC").fetchall()],
                "health_profile": json.loads(h_prof[0]) if h_prof else {},
                "health_logs": h_logs,
                "metrics_data": {"tdy_study": tdy_study / 60.0, "ydy_study": ydy_study / 60.0, "tdy_dist": tdy_dist, "ydy_dist": ydy_dist, "hourly_vol": vols, "total_study_hours": tdy_study / 60.0}
            })

        elif action == "save_settings":
            for k, v in req.get("data", {}).items(): config.set(k, v)
            return json.dumps({"status": "saved"})

        elif action == "open_file_dialog":
            parent = QApplication.activeWindow()
            file_path, _ = QFileDialog.getOpenFileName(parent, "Select a file", "", "All Files (*.*);;Images (*.png *.jpg *.jpeg);;Fonts (*.ttf *.otf)")
            return json.dumps({"path": file_path if file_path else ""})
            
        elif action == "open_folder_dialog":
            parent = QApplication.activeWindow()
            folder_path = QFileDialog.getExistingDirectory(parent, "Select Folder to Sync", "", QFileDialog.Option.ShowDirsOnly)
            return json.dumps({"path": folder_path if folder_path else ""})

        elif action == "get_processes":
            return json.dumps({"processes": [{'name': p['name'], 'pid': p['pid'], 'cpu': p['cpu'], 'memory': p['memory']} for p in self.get_running_processes()[:50]]})
            
        elif action == "set_app_monitoring":
            config.set("app_monitoring_enabled", req.get("enabled", False))
            return json.dumps({"status": "ok"})
            
        elif action == "set_allowed_apps":
            config.set("allowed_apps", req.get("apps", []))
            return json.dumps({"status": "ok"})
            
        elif action == "set_blocked_apps":
            config.set("blocked_apps", req.get("apps", []))
            return json.dumps({"status": "ok"})
            
        elif action == "set_auto_block":
            config.set("auto_block", req.get("enabled", False))
            return json.dumps({"status": "ok"})
            
        elif action == "check_current_distractions":
            return json.dumps({"distractions": self.check_processes_for_distraction()})
            
        elif action == "set_quiet_mode":
            enabled = req.get("enabled", False)
            config.set("quiet_mode", enabled)
            self.quiet_mode = enabled
            if enabled:
                self.vision.stop()
                self.vision.cap = None
            return json.dumps({"status": "ok"})

        elif action == "get_git_status":
            try:
                repo_path = os.path.join(os.path.expanduser("~"), ".mindpalace_sync_repo")
                if os.path.exists(repo_path):
                    import git
                    repo = git.Repo(repo_path)
                    try:
                        remote = repo.remotes.origin
                        remote.fetch(dry_run=True)
                        status = "connected"
                    except: status = "error"
                    last_commit = repo.head.commit.committed_datetime.isoformat() if repo.head.is_valid() else None
                    return json.dumps({"status": status, "last_sync": last_commit, "branch": repo.active_branch.name if repo.head.is_valid() else "none"})
                else: return json.dumps({"status": "not_initialized", "last_sync": None})
            except Exception as e: return json.dumps({"status": "error", "error": str(e)})

        elif action == "sync_now":
            def sync_thread():
                try:
                    success, msg = self.sync_manager.sync()
                    self.sync_completed.emit(success, msg if msg else "Sync completed" if success else "Sync failed")
                except Exception as e:
                    self.sync_completed.emit(False, f"Error: {str(e)}")
            try: self.sync_completed.disconnect()
            except: pass
            self.sync_completed.connect(self.handle_sync_result)
            thread = threading.Thread(target=sync_thread); thread.daemon = True; thread.start()
            return json.dumps({"status": "started"})
            
        elif action == "get_sync_status":
            return json.dumps({
                "enabled": config.get("sync_enabled", False),
                "device_id": self.sync_manager.device_id,
                "repo_url": config.get("sync_repo_url", ""),
                "interval": config.get("sync_interval", 3600),
                "has_token": bool(GITHUB_TOKEN)
            })

        elif action == "map_folder":
            path = req.get("path", "")
            if os.path.exists(path):
                self.sync_manager.map_folder(path)
                return json.dumps({"status": "success", "path": path})
            return json.dumps({"status": "error", "message": "Path does not exist"})

        elif action == "unmap_folder":
            path = req.get("path", "")
            self.sync_manager.unmap_folder(path)
            return json.dumps({"status": "success", "path": path})

        elif action == "get_mapped_folders":
            return json.dumps({"folders": config.get("sync_local_paths", [])})

        elif action == "export_data":
            parent = QApplication.activeWindow()
            file_path, _ = QFileDialog.getSaveFileName(parent, "Export Data", "mindpalace_backup.zip", "ZIP (*.zip)")
            if not file_path: return json.dumps({"error": "Export cancelled"})
            data = {"settings": config.cfg, "tables": {}}
            tables = ["courses", "pomodoro_sessions", "cascading_goals", "habits", "habit_logs", "flashcards", "quizzes", "focus_queue", "notes", "health_profile", "health_logs"]
            for table in tables:
                db.c.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in db.c.description]
                data["tables"][table] = [dict(zip(columns, row)) for row in db.c.fetchall()]
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.writestr("data.json", json.dumps(data, indent=2))
            with open(file_path, 'wb') as f: f.write(zip_buffer.getvalue())
            return json.dumps({"status": "exported", "path": file_path})

        elif action == "import_data":
            parent = QApplication.activeWindow()
            file_path, _ = QFileDialog.getOpenFileName(parent, "Import Data", "", "ZIP (*.zip)")
            if not file_path: return json.dumps({"error": "Import cancelled"})
            with zipfile.ZipFile(file_path, 'r') as zipf:
                with zipf.open("data.json") as f: data = json.load(f)
            tables_data = data.get("tables", {})
            order = ["courses", "habits", "cascading_goals", "flashcards", "quizzes", "notes", "focus_queue", "habit_logs", "pomodoro_sessions", "health_profile", "health_logs"]
            for table in order:
                if table not in tables_data: continue
                for row in tables_data[table]:
                    uid = row.get("uuid")
                    if not uid: uid = uuid.uuid4().hex; row["uuid"] = uid
                    db.c.execute(f"SELECT id, modified_at FROM {table} WHERE uuid = ?", (uid,))
                    existing = db.c.fetchone()
                    if existing:
                        existing_id, existing_mod = existing
                        incoming_mod = row.get("modified_at", "")
                        if incoming_mod > existing_mod:
                            set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k != "id"])
                            values = [row[k] for k in row.keys() if k != "id"] + [existing_id]
                            db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                    else:
                        row.pop("id", None)
                        cols = ", ".join(row.keys()); placeholders = ", ".join(["?"] * len(row))
                        db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
            db.conn.commit()
            return self.request(json.dumps({"action": "init"}))

        elif action == "reset_data":
            db.c.execute("DELETE FROM pomodoro_sessions")
            db.c.execute("DELETE FROM habit_logs")
            db.c.execute("DELETE FROM focus_queue")
            db.conn.commit()
            return json.dumps({"status": "cleared"})

        elif action == "start_timer":
            self.current_course = req.get("course", "General")
            self.total_time = int(req.get("duration", 25)) * 60
            self.time_left = self.total_time
            self.distractions = 0
            self.distraction_markers = []
            self.is_running = True
            self.ovl.show()
            self.vision.start()
            self.timer.start(1000)
            return json.dumps({"status": "started"})

        elif action == "stop_timer":
            self.is_running = False
            self.timer.stop(); self.ovl.hide(); self.vision.stop()
            db.c.execute("INSERT INTO pomodoro_sessions (uuid, modified_at, course, duration, actual_duration, timestamp, type, distractions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                        (uuid.uuid4().hex, datetime.now().isoformat(), self.current_course, self.total_time // 60, (self.total_time - self.time_left) // 60, datetime.now().isoformat(), 'Work', self.distractions))
            db.conn.commit()
            return json.dumps({"status": "stopped"})

        elif action == "manage_health":
            sub = req.get("sub")
            if sub == "save_profile":
                db.c.execute("INSERT INTO health_profile (uuid, modified_at, data_json) VALUES (?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), json.dumps(req.get("data"))))
            elif sub == "log_entry":
                db.c.execute("INSERT INTO health_logs (uuid, modified_at, log_type, date, data_json) VALUES (?, ?, ?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), req.get("log_type"), req.get("date"), json.dumps(req.get("data"))))
            elif sub == "delete_log":
                date = req.get("date")
                ltype = req.get("log_type")
                idx = req.get("index") # Using index or ID to delete specific ones if multiple exist on same day
                db.c.execute("DELETE FROM health_logs WHERE date=? AND log_type=?", (date, ltype))
            db.conn.commit()
            
            # Return updated logs
            db.c.execute("SELECT log_type, date, data_json FROM health_logs")
            h_logs = [{"type": r[0], "date": r[1], "data": json.loads(r[2])} for r in db.c.fetchall()]
            return json.dumps({"health_logs": h_logs})

        elif action == "manage_queue":
            sub = req.get("sub")
            if sub == "add": db.c.execute("INSERT INTO focus_queue (uuid, modified_at, title, duration, type, status, course) VALUES (?, ?, ?, ?, ?, 'pending', ?)", (uuid.uuid4().hex, datetime.now().isoformat(), req.get("title"), int(req.get("duration")), req.get("type"), req.get("course")))
            elif sub == "edit": db.c.execute("UPDATE focus_queue SET title=?, duration=?, type=?, course=?, modified_at=? WHERE id=?", (req.get("title"), int(req.get("duration")), req.get("type"), req.get("course"), datetime.now().isoformat(), req.get("id")))
            elif sub == "delete": db.c.execute("DELETE FROM focus_queue WHERE id=?", (req.get("id"),))
            elif sub == "clear": db.c.execute("DELETE FROM focus_queue")
            db.conn.commit()
            return json.dumps({"queue": [{"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]} for r in db.c.execute("SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id").fetchall()]})

        elif action == "manage_habit":
            sub = req.get("sub")
            if sub == "add": db.c.execute("INSERT INTO habits (uuid, modified_at, name, type, created_at) VALUES (?, ?, ?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), req.get("name"), req.get("type", "Positive"), datetime.now().isoformat()))
            elif sub == "edit": db.c.execute("UPDATE habits SET name=?, type=?, modified_at=? WHERE id=?", (req.get("name"), req.get("type"), datetime.now().isoformat(), req.get("id")))
            elif sub == "delete": db.c.execute("DELETE FROM habits WHERE id=?"); db.c.execute("DELETE FROM habit_logs WHERE habit_id=?", (req.get("id"),))
            elif sub == "toggle_log":
                hid, dt, st = req.get("habit_id"), req.get("date"), req.get("status", 1)
                existing = db.c.execute("SELECT id FROM habit_logs WHERE habit_id=? AND date=?", (hid, dt)).fetchone()
                if existing: db.c.execute("UPDATE habit_logs SET status=?, modified_at=? WHERE id=?", (st, datetime.now().isoformat(), existing[0]))
                else: db.c.execute("INSERT INTO habit_logs (uuid, modified_at, habit_id, date, status) VALUES (?, ?, ?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), hid, dt, st))
            db.conn.commit()
            return json.dumps({"habits": [{"id": r[0], "name": r[1], "type": r[2]} for r in db.c.execute("SELECT id, name, type FROM habits").fetchall()], "habit_logs": [{"habit_id": r[0], "date": r[1], "status": r[2]} for r in db.c.execute("SELECT habit_id, date, status FROM habit_logs").fetchall()]})

        elif action == "manage_note":
            sub = req.get("sub")
            if sub == "save":
                if req.get("id"): db.c.execute("UPDATE notes SET title=?, content=?, course=?, folder=?, color=?, modified_at=? WHERE id=?", (req.get("title"), req.get("content"), req.get("course"), req.get("folder"), req.get("color"), datetime.now().isoformat(), req.get("id")))
                else: db.c.execute("INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), req.get("title"), req.get("content"), datetime.now().isoformat(), req.get("course"), req.get("folder"), req.get("color")))
            elif sub == "delete": db.c.execute("DELETE FROM notes WHERE id=?", (req.get("id"),))
            db.conn.commit()
            return json.dumps({"notes": [{"id": r[0], "title": r[1], "content": r[2], "course": r[3], "folder": r[4], "color": r[5]} for r in db.c.execute("SELECT id, title, content, course, folder, color FROM notes ORDER BY id DESC").fetchall()]})

        elif action == "manage_flashcard":
            sub = req.get("sub")
            if sub == "add": db.c.execute("INSERT INTO flashcards (uuid, modified_at, front, back, deck, course, folder, color) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), req.get("front"), req.get("back"), req.get("deck"), req.get("course"), req.get("folder"), req.get("color")))
            elif sub == "delete": db.c.execute("DELETE FROM flashcards WHERE id=?", (req.get("id"),))
            db.conn.commit()
            return json.dumps({"flashcards": [{"id": r[0], "front": r[1], "back": r[2], "deck": r[3], "course": r[4], "folder": r[5], "color": r[6]} for r in db.c.execute("SELECT id, front, back, deck, course, folder, color FROM flashcards").fetchall()]})

        elif action == "manage_quiz":
            sub = req.get("sub")
            if sub == "add": db.c.execute("INSERT INTO quizzes (uuid, modified_at, title, questions_json, course, folder, color) VALUES (?, ?, ?, ?, ?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), req.get("title"), req.get("json"), req.get("course"), req.get("folder"), req.get("color")))
            elif sub == "delete": db.c.execute("DELETE FROM quizzes WHERE id=?", (req.get("id"),))
            db.conn.commit()
            return json.dumps({"quizzes": [{"id": r[0], "title": r[1], "json": r[2], "course": r[3], "folder": r[4], "color": r[5]} for r in db.c.execute("SELECT id, title, questions_json, course, folder, color FROM quizzes").fetchall()]})

        elif action == "manage_goal":
            sub = req.get("sub")
            if sub == "add":
                deadline = req.get("deadline")
                if deadline and 'T' in deadline: deadline = deadline.replace('T', ' ')
                db.c.execute("INSERT INTO cascading_goals (uuid, modified_at, parent_id, title, category, target_hours, deadline) VALUES (?, ?, ?, ?, ?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), req.get("parent_id"), req.get("title"), req.get("category"), float(req.get("target_hours") or 0), deadline))
            elif sub == "delete": db.c.execute("DELETE FROM cascading_goals WHERE id=?", (req.get("id"),))
            db.conn.commit()
            return json.dumps({"goals": [{"id": r[0], "title": r[1], "target_hours": r[2], "deadline": r[3], "parent_id": r[4]} for r in db.c.execute("SELECT id, title, target_hours, deadline, parent_id FROM cascading_goals").fetchall()], "flat_goals": [r[0] for r in db.c.execute("SELECT title FROM cascading_goals").fetchall()]})

        return json.dumps({"error": "Unknown action"})

    def emit_clock(self):
        img = QImage(300, 300, QImage.Format.Format_ARGB32_Premultiplied); img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.translate(150, 150)
        draw_clock_face(p, 120, QColor(15, 15, 17, 220)); draw_clock_ticks_and_indices(p, 120); draw_clock_complications(p, 120)
        t = QTime.currentTime(); h_style = config.get("clock_hands", "Classic")
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("white")))
        p.save(); p.rotate(30.0 * (t.hour() + t.minute()/60.0)); draw_horological_hand(p, h_style, 60, 4, True); p.restore()
        p.save(); p.rotate(6.0 * (t.minute() + t.second()/60.0)); draw_horological_hand(p, h_style, 90, 3, False); p.restore()
        p.end()
        buf = QByteArray(); buffer = QBuffer(buf); buffer.open(QIODevice.OpenModeFlag.WriteOnly); img.save(buffer, "PNG")
        self.clock_feed.emit(f"data:image/png;base64,{base64.b64encode(buf.data()).decode('utf-8')}")

    def tick(self):
        if not self.is_running: return
        att = True; dist_mode = "None"
        if not config.get("quiet_mode", False):
            att, b64_frame = self.vision.process_frame()
            if b64_frame: self.video_feed.emit(b64_frame)
            if not att:
                self.distractions += 1; dist_mode = "Camera"
                self.distraction_markers.append(100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0)
                if self.distractions % 5 == 0: play_system_sound(config.get("sound_cam_dist", "Basso")); set_max_volume()
                
        if config.get("app_monitoring_enabled", False):
            app_distractions = self.check_processes_for_distraction()
            if app_distractions:
                if dist_mode == "None": dist_mode = "App"; self.distractions += 1; self.distraction_markers.append(100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0)
                if config.get("auto_block", False): self.kill_processes(app_distractions)

        if self.time_left > 0: self.time_left -= 1
        else:
            self.is_running = False; self.timer.stop(); self.ovl.hide(); self.vision.stop()
            if not config.get("quiet_mode", False): speak_text(config.get("speech_comp", "Session Complete."))
            
        mins, secs = divmod(self.time_left, 60); time_str = f"{mins:02d}:{secs:02d}"
        pct = 100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0
        self.ovl.update_state(time_str, pct, (self.total_time-self.time_left)//60, self.total_time//60, self.current_course, dist_mode)
        self.state_update.emit(json.dumps({"is_running": self.is_running, "time_str": time_str, "progress": pct, "distractions": self.distractions, "distraction_markers": self.distraction_markers, "course": self.current_course}))

    def get_heatmap_data(self):
        weeks = 28; matrix = [[0]*7 for _ in range(weeks)]; td = datetime.now().date()
        db.c.execute("SELECT date(timestamp), sum(duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY date(timestamp)")
        history = {r[0]: r[1]/60.0 for r in db.c.fetchall()}
        for w in range(weeks):
            for d in range(7):
                target_date = (td - timedelta(days=(weeks-w-1)*7 + (6-d))).isoformat()
                hrs = history.get(target_date, 0); intensity = 0
                if hrs > 0: intensity = 1
                if hrs > 2: intensity = 2
                if hrs > 4: intensity = 3
                if hrs > 6: intensity = 4
                matrix[w][d] = intensity
        return matrix