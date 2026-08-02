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

# Force Python to look in the current directory for custom modules like health_parser
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QTimer, Qt, QTime, QByteArray, QBuffer, QIODevice, QRectF
from PyQt6.QtGui import QImage, QPainter, QColor, QBrush, QPen, QFont
from PyQt6.QtWidgets import QWidget, QApplication, QFileDialog

from core_sys import config, db, get_color, GITHUB_TOKEN
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
        self.oldPos = None

    def update_state(self, time_str, progress_pct, worked_mins, total_mins, active_course, distraction_mode):
        self.txt = time_str
        self.sp = progress_pct / 100.0
        self.sm = worked_mins
        self.pm = total_mins
        self.dp = min(self.sm / max(self.pm, 1), 1.0)
        self.ring_color = get_color(active_course)
        
        if distraction_mode == "App": self.bg_override_color = QColor(255, 140, 0, 220)
        elif distraction_mode == "Camera": self.bg_override_color = QColor(255, 50, 50, 220)
        else: self.bg_override_color = None
        self.update()

    def mousePressEvent(self, e): 
        if e.button() == Qt.MouseButton.LeftButton: self.oldPos = e.globalPosition().toPoint()
    def mouseMoveEvent(self, e): 
        if self.oldPos is not None: 
            d = e.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + d.x(), self.y() + d.y()); self.oldPos = e.globalPosition().toPoint()
    def mouseReleaseEvent(self, e): 
        self.oldPos = None

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); radius = 90; p.translate(100, 100)
        bg_col = self.bg_override_color if self.bg_override_color else QColor(15, 15, 17, 220)
        draw_clock_face(p, radius, bg_col)
        p.setPen(QPen(QColor(255,255,255,30), 8))
        p.drawArc(-70, -70, 140, 140, 0, 360*16)
        p.setPen(QPen(self.ring_color, 8, cap=Qt.PenCapStyle.RoundCap))
        p.drawArc(-70, -70, 140, 140, 90*16, int(-self.sp * 360 * 16))
        p.setPen(QColor("white"))
        p.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        p.drawText(QRectF(-90, 20, 180, 40), Qt.AlignmentFlag.AlignCenter, self.txt)
        draw_clock_ticks_and_indices(p, radius)
        draw_clock_complications(p, radius)
        
        t = QTime.currentTime(); h_style = config.get("clock_hands", "Classic"); comp = config.get("clock_complication", "None")
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("white")))
        p.save(); p.rotate(30.0 * (t.hour() + t.minute()/60.0)); draw_horological_hand(p, h_style, 45, 3, True); p.restore()
        p.save(); p.rotate(6.0 * (t.minute() + t.second()/60.0)); draw_horological_hand(p, h_style, 65, 2, False); p.restore()
        
        sec_col = self.ring_color
        if comp == "Small Seconds":
            p.save(); p.translate(0, int(radius - 40)); p.setBrush(QBrush(sec_col)); p.setPen(QPen(sec_col, 1)); p.rotate(6.0 * t.second()); p.drawLine(0, 0, 0, -12); p.restore()
        else:
            p.setBrush(QBrush(sec_col)); p.setPen(QPen(sec_col, 2)); p.save(); p.rotate(6.0 * t.second())
            if h_style in ["Serpentine", "Arrow", "Sword"]: draw_horological_hand(p, h_style, 75, 1, False)
            else: p.setPen(Qt.PenStyle.NoPen); p.drawRect(-1, 0, 2, -75)
            p.restore()
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("white"))); p.drawEllipse(-3, -3, 6, 6)

class SystemBridge(QObject):
    state_update = pyqtSignal(str)
    video_feed = pyqtSignal(str)
    clock_feed = pyqtSignal(str)
    sync_completed = pyqtSignal(bool, str)
    scan_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ovl = OverlayWidget()
        self.vision = VisionTracker()
        self.timer = QTimer(); self.timer.timeout.connect(self.tick)
        self.clock_timer = QTimer(); self.clock_timer.timeout.connect(self.emit_clock); self.clock_timer.start(1000)
        
        self.is_running = False
        self.time_left = 0
        self.total_time = 0
        self.current_course = "General"
        self.distractions = 0
        self.distraction_markers = [] 
        self.active_queue_id = None
        
        self.quiet_mode = config.get("quiet_mode", False)
        self.sync_manager = SyncManager()
        self.sync_timer = QTimer(); self.sync_timer.timeout.connect(self.auto_sync)
        if config.get("sync_enabled", False): self.sync_timer.start(config.get("sync_interval", 3600) * 1000)
        
        self.backup_timer = QTimer()
        self.backup_timer.timeout.connect(self.backup_data)
        self.backup_timer.start(3600 * 1000)

        # Setup Invisible Drop Folder Watchdog
        self.scan_dir = os.path.expanduser("~/MindPalace_Scans")
        self.archive_dir = os.path.join(self.scan_dir, "Archive")
        os.makedirs(self.archive_dir, exist_ok=True)
        
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.check_auto_scans)
        self.scan_timer.start(10000)
        
        # PDF Library State
        self.lib_path = os.path.expanduser("~/MindPalace_Library")
        os.makedirs(self.lib_path, exist_ok=True)
        # Ensure it's in sync paths
        paths = config.get("sync_local_paths", [])
        if self.lib_path not in paths:
            paths.append(self.lib_path)
            config.set("sync_local_paths", paths)
            
        self.active_pdf = None
        self.active_pdf_name = ""

    def check_auto_scans(self):
        def worker():
            for f in os.listdir(self.scan_dir):
                if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                    img_path = os.path.join(self.scan_dir, f)
                    try:
                        from health_parser import BodyScanParser
                        parser = BodyScanParser(rois_file="rois.json")
                        data = parser.parse_image(img_path)
                    except Exception as e:
                        print("Parse error", e)
                        continue
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    arch_path = os.path.join(self.archive_dir, f"scan_{timestamp}_{f}")
                    os.rename(img_path, arch_path)
                    
                    if data:
                        data["file_path"] = arch_path
                        self.scan_ready.emit(json.dumps(data))
                        
        threading.Thread(target=worker, daemon=True).start()

    def handle_sync_result(self, success, msg):
        if not success: QApplication.beep()

    def play_sound(self, sound_type="app"):
        if config.get("mute_sounds", False) or config.get("quiet_mode", False): return
        sound_name = config.get(f"sound_{sound_type}_dist", "Basso" if sound_type=="cam" else "Ping")
        if sys.platform == "darwin":
            path = f"/System/Library/Sounds/{sound_name}.aiff"
            if os.path.exists(path): subprocess.Popen(["afplay", path])
            else: QApplication.beep()
        elif sys.platform == "win32":
            try: import winsound; winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except: QApplication.beep()
        else: QApplication.beep()

    def speak(self, text):
        if config.get("mute_speech", False) or config.get("quiet_mode", False): return
        if sys.platform == "darwin": subprocess.Popen(["say", text])
        elif sys.platform == "win32":
            try:
                import pyttsx3
                engine = pyttsx3.init(); engine.say(text); engine.runAndWait()
            except ImportError: pass
        else: subprocess.Popen(["espeak", text], stderr=subprocess.DEVNULL)

    def set_max_volume(self):
        if sys.platform == "darwin":
            try: subprocess.Popen(["osascript", "-e", "set volume output volume 100"])
            except: pass

    def get_running_processes(self):
        processes = []
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cpu_percent', 'memory_percent', 'create_time']):
                try: processes.append({'pid': proc.info['pid'], 'name': proc.info['name'], 'cpu': proc.info['cpu_percent'] or 0, 'memory': proc.info['memory_percent'] or 0})
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

    def auto_sync(self):
        if config.get("sync_enabled", False): self.sync_manager.sync()

    def backup_data(self):
        backup_dir = os.path.join(os.path.expanduser("~"), "MindPalaceBackups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"auto_backup_{timestamp}.zip")
        settings = config.cfg.copy(); settings.pop("sync_github_token", None)
        data = {"settings": settings, "tables": {}}
        tables = ["courses", "pomodoro_sessions", "cascading_goals", "habits", "habit_logs", "flashcards", "quizzes", "focus_queue", "notes", "health_profile", "health_logs", "custom_foods", "custom_activities", "health_plans"]
        for table in tables:
            db.c.execute(f"SELECT * FROM {table}"); columns = [desc[0] for desc in db.c.description]
            data["tables"][table] = [dict(zip(columns, row)) for row in db.c.fetchall()]
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("data.json", json.dumps(data, indent=2))
        with open(backup_path, 'wb') as f: f.write(zip_buffer.getvalue())

    def get_goals_tree(self):
        db.c.execute("SELECT id, parent_id, title, target_hours, deadline FROM cascading_goals")
        return [{"id": r[0], "parent_id": r[1], "title": r[2], "target_hours": r[3], "deadline": r[4]} for r in db.c.fetchall()]

    def get_flat_goals(self):
        db.c.execute("SELECT id, parent_id, title FROM cascading_goals")
        tree = {r[0]: {"parent": r[1], "title": r[2]} for r in db.c.fetchall()}
        paths = []
        for gid, data in tree.items():
            path = [data["title"]]; curr = data["parent"]
            while curr in tree: path.insert(0, tree[curr]["title"]); curr = tree[curr]["parent"]
            paths.append(" > ".join(path))
        return sorted(paths)
        
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
                
            db.c.execute("SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work'")
            global_study_hours = (db.c.fetchone()[0] or 0) / 60.0
            db.c.execute("SELECT sum(target_hours) FROM cascading_goals")
            global_target_hours = db.c.fetchone()[0] or 0.0
            if global_target_hours == 0:
                db.c.execute("SELECT sum(target_hours) FROM courses")
                global_target_hours = db.c.fetchone()[0] or 50.0 

            db.c.execute("SELECT data_json FROM health_profile ORDER BY id DESC LIMIT 1")
            h_prof = db.c.fetchone()
            db.c.execute("SELECT log_type, date, data_json FROM health_logs")
            h_logs = [{"type": r[0], "date": r[1], "data": json.loads(r[2])} for r in db.c.fetchall()]

            return json.dumps({
                "flat_goals": self.get_flat_goals(),
                "goals": self.get_goals_tree(),
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
                "custom_foods": [{"id": r[0], "name": r[1], "kcal": r[2], "protein": r[3], "fat": r[4], "carbs": r[5], "category": r[6]} for r in db.c.execute("SELECT id, name, kcal, protein, fat, carbs, category FROM custom_foods").fetchall()],
                "custom_activities": [{"id": r[0], "name": r[1], "met": r[2], "category": r[3]} for r in db.c.execute("SELECT id, name, met, category FROM custom_activities").fetchall()],
                "health_plans": [{"id": r[0], "type": r[1], "title": r[2], "details": r[3]} for r in db.c.execute("SELECT id, type, title, details FROM health_plans").fetchall()],
                "metrics_data": {
                    "tdy_study": tdy_study / 60.0, "ydy_study": ydy_study / 60.0, 
                    "tdy_dist": tdy_dist, "ydy_dist": ydy_dist, 
                    "hourly_vol": vols, 
                    "global_study_hours": global_study_hours,
                    "global_target_hours": global_target_hours
                }
            })

        elif action == "save_settings":
            for k, v in req.get("data", {}).items(): config.set(k, v)
            return json.dumps({"status": "saved"})

        elif action == "save_file":
            parent = QApplication.activeWindow()
            ext = req.get("ext", "txt")
            content = req.get("content", "")
            title = req.get("title", "Export")
            file_path, _ = QFileDialog.getSaveFileName(parent, "Save File", f"{title}.{ext}", f"Files (*.{ext})")
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return json.dumps({"status": "saved", "path": file_path})
                except Exception as e:
                    return json.dumps({"status": "error", "message": str(e)})
            return json.dumps({"status": "cancelled"})

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

        elif action == "open_folder_dialog":
            parent = QApplication.activeWindow()
            folder_path = QFileDialog.getExistingDirectory(parent, "Select Folder to Sync", "", QFileDialog.Option.ShowDirsOnly)
            return json.dumps({"path": folder_path if folder_path else ""})

        elif action == "sync_now":
            def sync_thread():
                try:
                    success, msg = self.sync_manager.sync()
                    self.sync_completed.emit(success, msg if msg else "Sync completed" if success else "Sync failed - unknown error")
                except Exception as e:
                    self.sync_completed.emit(False, f"Error: {str(e)}")
            try: self.sync_completed.disconnect()
            except: pass
            self.sync_completed.connect(self.handle_sync_result)
            thread = threading.Thread(target=sync_thread); thread.daemon = True; thread.start()
            return json.dumps({"status": "started"})
            
        elif action == "get_device_id":
            return json.dumps({"device_id": self.sync_manager.device_id})

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
            return json.dumps({
                "folders": config.get("sync_local_paths", []),
                "network_folders": self.sync_manager.get_network_folders()
            })
            
        elif action == "open_network_folder":
            path = req.get("path", "")
            if os.path.exists(path):
                if sys.platform == 'darwin': subprocess.Popen(['open', path])
                elif sys.platform == 'win32': os.startfile(path)
                else: subprocess.Popen(['xdg-open', path])
                return json.dumps({"status": "opened"})
            return json.dumps({"status": "error"})

        elif action == "get_sync_status":
            return json.dumps({"enabled": config.get("sync_enabled", False), "device_id": self.sync_manager.device_id, "repo_url": config.get("sync_repo_url", ""), "interval": config.get("sync_interval", 3600), "has_token": bool(GITHUB_TOKEN)})

        elif action == "set_quiet_mode":
            enabled = req.get("enabled", False)
            config.set("quiet_mode", enabled)
            self.quiet_mode = enabled
            if enabled:
                self.vision.stop()
                self.vision.cap = None
            return json.dumps({"status": "ok", "quiet_mode": enabled})

        elif action == "reset_data":
            tables_to_clear = [
                "courses", "pomodoro_sessions", "cascading_goals", "habits", 
                "habit_logs", "flashcards", "quizzes", "focus_queue", "notes", 
                "health_profile", "health_logs", "custom_foods", "custom_activities", 
                "health_plans", "course_targets", "starred_questions", "exams", "todos"
            ]
            for table in tables_to_clear:
                try:
                    db.c.execute(f"DELETE FROM {table}")
                except Exception:
                    pass
            db.conn.commit()
            return json.dumps({"status": "cleared"})

        elif action == "open_file_dialog":
            parent = QApplication.activeWindow()
            file_path, _ = QFileDialog.getOpenFileName(parent, "Select a file", "", "All Files (*.*);;JSON (*.json);;Images (*.png *.jpg)")
            return json.dumps({"path": file_path if file_path else ""})

        elif action == "get_processes":
            return json.dumps({"processes": [{'name': p['name'], 'pid': p['pid'], 'cpu': p['cpu'], 'memory': p['memory']} for p in self.get_running_processes()[:50]]})

        elif action == "get_app_monitoring_status":
            return json.dumps({'enabled': config.get("app_monitoring_enabled", False), 'allowed_apps': config.get("allowed_apps", []), 'blocked_apps': config.get("blocked_apps", []), 'auto_block': config.get("auto_block", False)})

        elif action == "set_allowed_apps":
            apps = req.get("apps", [])
            config.set("allowed_apps", apps)
            return json.dumps({"status": "ok", "allowed_apps": apps})

        elif action == "set_blocked_apps":
            apps = req.get("apps", [])
            config.set("blocked_apps", apps)
            return json.dumps({"status": "ok", "blocked_apps": apps})

        elif action == "set_app_monitoring":
            enabled = req.get("enabled", False)
            config.set("app_monitoring_enabled", enabled)
            return json.dumps({"status": "ok", "enabled": enabled})

        elif action == "set_auto_block":
            enabled = req.get("enabled", False)
            config.set("auto_block", enabled)
            return json.dumps({"status": "ok", "auto_block": enabled})

        elif action == "check_current_distractions":
            return json.dumps({"distractions": self.check_processes_for_distraction()})

        elif action == "import_body_scan":
            parent = QApplication.activeWindow()
            file_path, _ = QFileDialog.getOpenFileName(parent, "Select Body Scan Image", "", "Images (*.png *.jpg *.jpeg)")
            if not file_path:
                return json.dumps({"status": "cancelled"})
                
            try:
                from health_parser import BodyScanParser
                parser = BodyScanParser(rois_file="rois.json")
                data = parser.parse_image(file_path)
                
                if not data:
                    return json.dumps({"status": "error", "message": "Failed to parse image."})
                
                data["file_path"] = file_path
                return json.dumps({"status": "success", "parsed_data": data})
            except Exception as e:
                return json.dumps({"status": "error", "message": str(e)})

        elif action == "save_body_scan":
            data = req.get("data", {})
            today_str = datetime.now().date().isoformat()
            
            db.c.execute("SELECT id, data_json FROM health_profile ORDER BY id DESC LIMIT 1")
            prof_row = db.c.fetchone()
            prof_data = json.loads(prof_row[1]) if prof_row else {}
            
            if data.get("weight"): prof_data["weight"] = data["weight"]
            if data.get("bmr"): prof_data["bmr"] = data["bmr"]
            
            if prof_row:
                db.c.execute("UPDATE health_profile SET data_json=?, modified_at=? WHERE id=?", 
                             (json.dumps(prof_data), datetime.now().isoformat(), prof_row[0]))
            else:
                db.c.execute("INSERT INTO health_profile (uuid, modified_at, data_json) VALUES (?, ?, ?)", 
                             (uuid.uuid4().hex, datetime.now().isoformat(), json.dumps(prof_data)))
            
            db.c.execute("INSERT INTO health_logs (uuid, modified_at, log_type, date, data_json) VALUES (?, ?, ?, ?, ?)", 
                         (uuid.uuid4().hex, datetime.now().isoformat(), 'body_scan', today_str, json.dumps(data)))
            db.conn.commit()
            
            h_prof = db.c.execute("SELECT data_json FROM health_profile ORDER BY id DESC LIMIT 1").fetchone()
            h_logs = [{"type": r[0], "date": r[1], "data": json.loads(r[2])} for r in db.c.execute("SELECT log_type, date, data_json FROM health_logs").fetchall()]
            
            return json.dumps({"status": "success", "health_profile": json.loads(h_prof[0]) if h_prof else {}, "health_logs": h_logs})

        elif action == "start_timer":
            queue_id = req.get("queue_id")
            
            if queue_id == "auto":
                db.c.execute("SELECT id, duration, course, type FROM focus_queue WHERE status IN ('pending', 'active') ORDER BY id ASC LIMIT 1")
                q_item = db.c.fetchone()
                if q_item:
                    self.active_queue_id = q_item[0]
                    self.total_time = int(q_item[1]) * 60
                    self.current_course = q_item[2] or "General"
                    db.c.execute("UPDATE focus_queue SET status='active' WHERE id=?", (self.active_queue_id,))
                    db.conn.commit()
                else:
                    return json.dumps({"error": "Queue empty"})
            else:
                self.active_queue_id = queue_id
                if self.active_queue_id:
                    db.c.execute("UPDATE focus_queue SET status='active' WHERE id=?", (self.active_queue_id,))
                    db.conn.commit()
                self.current_course = req.get("course", "General")
                self.total_time = int(req.get("duration", 25)) * 60

            self.time_left = self.total_time
            self.distractions = 0
            self.distraction_markers = []
            self.is_running = True
            
            self.ovl.show()
            self.vision.start()
            self.timer.start(1000)
            
            self.push_state("None")
            return json.dumps({"status": "started"})

        elif action == "stop_timer":
            self.is_running = False
            self.timer.stop()
            self.ovl.hide()
            self.vision.stop()
            
            if self.active_queue_id:
                db.c.execute("UPDATE focus_queue SET status='pending' WHERE id=?", (self.active_queue_id,))
                self.active_queue_id = None
                
            db.c.execute("""
                INSERT INTO pomodoro_sessions (uuid, modified_at, course, duration, actual_duration, timestamp, type, distractions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (uuid.uuid4().hex, datetime.now().isoformat(), self.current_course, self.total_time // 60, (self.total_time - self.time_left) // 60, datetime.now().isoformat(), 'Work', self.distractions))
            db.conn.commit()
            
            self.push_state()
            return json.dumps({"status": "stopped"})

        elif action == "manage_queue":
            sub = req.get("sub")
            if sub == "add":
                db.c.execute("INSERT INTO focus_queue (uuid, modified_at, title, duration, type, status, course) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                            (uuid.uuid4().hex, datetime.now().isoformat(), req.get("title"), int(req.get("duration")), req.get("type"), 'pending', req.get("course")))
            elif sub == "edit":
                db.c.execute("UPDATE focus_queue SET title=?, duration=?, type=?, course=?, modified_at=? WHERE id=?",
                             (req.get("title"), int(req.get("duration")), req.get("type"), req.get("course"), datetime.now().isoformat(), req.get("id")))
            elif sub == "delete":
                target_id = req.get("id")
                db.c.execute("DELETE FROM focus_queue WHERE id=?", (target_id,))
                if self.active_queue_id == target_id:
                    self.active_queue_id = None
                    self.is_running = False
                    self.timer.stop()
            elif sub == "clear":
                db.c.execute("DELETE FROM focus_queue")
                self.active_queue_id = None
                self.is_running = False
                self.timer.stop()
            db.conn.commit()
            
            db.c.execute("SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id")
            queue_data = [{"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]} for r in db.c.fetchall()]
            return json.dumps({"queue": queue_data})

        elif action == "manage_health":
            sub = req.get("sub")
            if sub == "save_profile": db.c.execute("INSERT INTO health_profile (uuid, modified_at, data_json) VALUES (?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), json.dumps(req.get("data"))))
            elif sub == "log_entry": db.c.execute("INSERT INTO health_logs (uuid, modified_at, log_type, date, data_json) VALUES (?, ?, ?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), req.get("log_type"), req.get("date"), json.dumps(req.get("data"))))
            elif sub == "delete_log": db.c.execute("DELETE FROM health_logs WHERE date=? AND log_type=?", (req.get("date"), req.get("log_type")))
            elif sub == "save_food": db.c.execute("INSERT OR REPLACE INTO custom_foods (uuid, modified_at, name, kcal, protein, fat, carbs, category) VALUES (COALESCE((SELECT uuid FROM custom_foods WHERE name=?), ?), ?, ?, ?, ?, ?, ?, ?)", (req.get("name"), uuid.uuid4().hex, datetime.now().isoformat(), req.get("name"), req.get("kcal"), req.get("protein"), req.get("fat"), req.get("carbs"), req.get("category")))
            elif sub == "save_activity": db.c.execute("INSERT OR REPLACE INTO custom_activities (uuid, modified_at, name, met, category) VALUES (COALESCE((SELECT uuid FROM custom_activities WHERE name=?), ?), ?, ?, ?, ?)", (req.get("name"), uuid.uuid4().hex, datetime.now().isoformat(), req.get("name"), req.get("met"), req.get("category")))
            elif sub == "save_plan": db.c.execute("INSERT OR REPLACE INTO health_plans (uuid, modified_at, type, title, details) VALUES (COALESCE((SELECT uuid FROM health_plans WHERE title=?), ?), ?, ?, ?, ?)", (req.get("title"), uuid.uuid4().hex, datetime.now().isoformat(), req.get("type"), req.get("title"), req.get("details")))
            elif sub == "delete_plan": db.c.execute("DELETE FROM health_plans WHERE id=?", (req.get("id"),))
            db.conn.commit()
            return json.dumps({"health_logs": [{"type": r[0], "date": r[1], "data": json.loads(r[2])} for r in db.c.execute("SELECT log_type, date, data_json FROM health_logs").fetchall()], "custom_foods": [{"id": r[0], "name": r[1], "kcal": r[2], "protein": r[3], "fat": r[4], "carbs": r[5], "category": r[6]} for r in db.c.execute("SELECT id, name, kcal, protein, fat, carbs, category FROM custom_foods").fetchall()], "custom_activities": [{"id": r[0], "name": r[1], "met": r[2], "category": r[3]} for r in db.c.execute("SELECT id, name, met, category FROM custom_activities").fetchall()], "health_plans": [{"id": r[0], "type": r[1], "title": r[2], "details": r[3]} for r in db.c.execute("SELECT id, type, title, details FROM health_plans").fetchall()]})

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
                if req.get("id"): 
                    db.c.execute("UPDATE notes SET title=?, content=?, course=?, folder=?, color=?, modified_at=? WHERE id=?", 
                                 (req.get("title"), req.get("content"), req.get("course"), req.get("folder"), req.get("color"), datetime.now().isoformat(), req.get("id")))
                else: 
                    db.c.execute("INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                 (uuid.uuid4().hex, datetime.now().isoformat(), req.get("title"), req.get("content"), datetime.now().isoformat(), req.get("course"), req.get("folder"), req.get("color")))
            elif sub == "delete": 
                db.c.execute("DELETE FROM notes WHERE id=?", (req.get("id"),))
                
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
            if sub == "add": db.c.execute("INSERT INTO cascading_goals (uuid, modified_at, parent_id, title, category, target_hours, deadline) VALUES (?, ?, ?, ?, ?, ?, ?)", (uuid.uuid4().hex, datetime.now().isoformat(), req.get("parent_id"), req.get("title"), req.get("category"), float(req.get("target_hours") or 0), req.get("deadline").replace('T', ' ') if req.get("deadline") else None))
            elif sub == "delete": db.c.execute("DELETE FROM cascading_goals WHERE id=?", (req.get("id"),))
            db.conn.commit()
            return json.dumps({"goals": self.get_goals_tree(), "flat_goals": self.get_flat_goals()})

        elif action == "export_data":
            parent = QApplication.activeWindow()
            file_path, _ = QFileDialog.getSaveFileName(parent, "Export Data", "mindpalace_backup.zip", "ZIP (*.zip)")
            if not file_path: return json.dumps({"error": "Export cancelled"})
            data = {"settings": config.cfg, "tables": {}}
            tables = ["courses", "pomodoro_sessions", "cascading_goals", "habits", "habit_logs", "flashcards", "quizzes", "focus_queue", "notes"]
            for table in tables:
                db.c.execute(f"SELECT * FROM {table}"); columns = [desc[0] for desc in db.c.description]
                data["tables"][table] = [dict(zip(columns, row)) for row in db.c.fetchall()]
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf: zipf.writestr("data.json", json.dumps(data, indent=2))
            with open(file_path, 'wb') as f: f.write(zip_buffer.getvalue())
            return json.dumps({"status": "exported", "path": file_path})

        elif action == "import_data":
            parent = QApplication.activeWindow()
            file_path, _ = QFileDialog.getOpenFileName(parent, "Import Data", "", "ZIP (*.zip)")
            if not file_path: return json.dumps({"error": "Import cancelled"})
            with zipfile.ZipFile(file_path, 'r') as zipf:
                with zipf.open("data.json") as f: data = json.load(f)
            tables_data = data.get("tables", {})
            for table in ["courses", "habits", "cascading_goals", "flashcards", "quizzes", "notes", "focus_queue", "habit_logs", "pomodoro_sessions"]:
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

        elif action == "lib_list":
            files = [f for f in os.listdir(self.lib_path) if f.lower().endswith('.pdf')]
            return json.dumps({"files": files})
            
        elif action == "lib_open":
            if not pymupdf: return json.dumps({"error": "PyMuPDF not installed. Run: pip install pymupdf"})
            fname = req.get("filename")
            path = os.path.join(self.lib_path, fname)
            try:
                if self.active_pdf: self.active_pdf.close()
                self.active_pdf = pymupdf.open(path)
                self.active_pdf_name = fname
                return json.dumps({"status": "ok", "total_pages": len(self.active_pdf)})
            except Exception as e:
                return json.dumps({"error": str(e)})
                
        elif action == "lib_page":
            if not self.active_pdf: return json.dumps({"error": "No PDF open"})
            page_num = req.get("page", 0)
            zoom = req.get("zoom", 1.5)
            if page_num < 0 or page_num >= len(self.active_pdf): return json.dumps({"error": "Invalid page"})
            
            page = self.active_pdf[page_num]
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img_b64 = base64.b64encode(pix.tobytes("png")).decode('utf-8')
            
            annots = []
            annot = page.first_annot
            while annot:
                info = annot.info
                annots.append({
                    "subject": info.get("subject", "Annot"),
                    "title": info.get("title", "User"),
                    "content": info.get("content", "")
                })
                annot = annot.next
                
            return json.dumps({"b64": img_b64, "width": pix.width, "height": pix.height, "annots": annots})
            
        elif action == "lib_annot":
            if not self.active_pdf: return json.dumps({"error": "No PDF open"})
            page_num = req.get("page", 0)
            rect_data = req.get("rect") # [x0, y0, x1, y1]
            tool = req.get("tool", "Highlight")
            text = req.get("text", "")
            
            page = self.active_pdf[page_num]
            r = pymupdf.Rect(*rect_data)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            device = config.get("device_id", "UnknownDevice")
            
            try:
                if tool == "Highlight":
                    annot = page.add_highlight_annot(r)
                    annot.set_colors(stroke=(1, 1, 0))
                    annot.set_info(info={"title": device, "subject": "Highlight", "content": f"Captured at {timestamp}"})
                    annot.update()
                elif tool == "Underline":
                    annot = page.add_underline_annot(r)
                    annot.set_colors(stroke=(0, 0.5, 1))
                    annot.set_info(info={"title": device, "subject": "Underline", "content": f"Captured at {timestamp}"})
                    annot.update()
                elif tool == "Note":
                    annot = page.add_text_annot(r.tl, text)
                    annot.set_info(info={"title": device, "subject": "Note", "content": f"{timestamp}\n{text}"})
                    annot.update()
                    
                self.active_pdf.save(self.active_pdf.name, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
                return json.dumps({"status": "ok"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        return json.dumps({"error": "Unknown action"})

    def emit_clock(self):
        try:
            img = QImage(300, 300, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            radius = 120
            p.translate(150, 150)
            
            s = config.get("clock_style", "Analog Classic")
            h_style = config.get("clock_hands", "Classic")
            comp = config.get("clock_complication", "None")
            
            if "Minimal" in s:
                bg_col = QColor(0,0,0,80)
                hand_col = QColor("white")
            elif "Neon" in s:
                bg_col = QColor(10,132,255,50)
                hand_col = QColor("white")
            else:
                bg_col = QColor(15, 15, 17, 220)
                hand_col = QColor("white")
                
            draw_clock_face(p, radius, bg_col)
            draw_clock_ticks_and_indices(p, radius)
            draw_clock_complications(p, radius)
                
            t = QTime.currentTime()
            
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(hand_col))
            
            p.save(); p.rotate(30.0 * (t.hour() + t.minute()/60.0)); draw_horological_hand(p, h_style, 60, 4, True); p.restore()
            p.save(); p.rotate(6.0 * (t.minute() + t.second()/60.0)); draw_horological_hand(p, h_style, 90, 3, False); p.restore()
            
            sec_col = QColor("#0a84ff")
            if comp == "Small Seconds":
                p.save(); p.translate(0, int(radius - 40)); p.setBrush(QBrush(sec_col)); p.setPen(QPen(sec_col, 1)); p.rotate(6.0 * t.second()); p.drawLine(0, 0, 0, -15); p.restore()
            else:
                p.setBrush(QBrush(sec_col)); p.setPen(QPen(sec_col, 2)); p.save(); p.rotate(6.0 * t.second())
                if h_style in ["Serpentine", "Sword", "Arrow"]: draw_horological_hand(p, h_style, 100, 1, False)
                else: p.setPen(Qt.PenStyle.NoPen); p.drawRect(-1, 0, 2, -100)
                p.restore()
            
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("white"))); p.drawEllipse(-4, -4, 8, 8)
            p.end()
            
            buf = QByteArray()
            buffer = QBuffer(buf)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(buffer, "PNG")
            
            # Robust bytes extraction to prevent PyQt6 silent crashes
            raw_bytes = bytes(buf) if hasattr(buf, '__bytes__') else bytes(buf.data())
            b64 = base64.b64encode(raw_bytes).decode('utf-8')
            self.clock_feed.emit(f"data:image/png;base64,{b64}")
        except Exception as e:
            print(f"Horology render failed: {e}")

    def push_state(self, dist_mode="None"):
        mins, secs = divmod(self.time_left, 60)
        time_str = f"{mins:02d}:{secs:02d}"
        pct = 100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0
        
        self.ovl.update_state(time_str, pct, (self.total_time-self.time_left)//60, self.total_time//60, self.current_course, dist_mode)
        
        db.c.execute("SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id")
        queue_data = [{"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]} for r in db.c.fetchall()]
        
        state = {
            "is_running": self.is_running,
            "time_str": time_str,
            "progress": pct,
            "distractions": self.distractions,
            "distraction_markers": self.distraction_markers,
            "course": self.current_course,
            "active_queue_id": self.active_queue_id,
            "queue": queue_data
        }
        self.state_update.emit(json.dumps(state))

    def tick(self):
        if not self.is_running: return
        
        att = True
        dist_mode = "None"
        
        if not config.get("quiet_mode", False):
            att, b64_frame = self.vision.process_frame()
            if b64_frame:
                self.video_feed.emit(b64_frame)
            
            if not att:
                self.distractions += 1
                dist_mode = "Camera"
                self.distraction_markers.append(100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0)
                if self.distractions % 5 == 0:
                    self.set_max_volume()
                    self.play_sound("cam")
        
        if config.get("app_monitoring_enabled", False):
            app_distractions = self.check_processes_for_distraction()
            if app_distractions:
                if dist_mode == "None":
                    dist_mode = "App"
                    self.distractions += 1
                    self.distraction_markers.append(100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0)
                if config.get("auto_block", False):
                    self.kill_processes(app_distractions)

        if self.time_left > 0:
            self.time_left -= 1
        else:
            if not config.get("quiet_mode", False):
                self.speak(config.get("speech_comp", "Session Complete."))
                
            db.c.execute("""
                INSERT INTO pomodoro_sessions (uuid, modified_at, course, duration, actual_duration, timestamp, type, distractions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (uuid.uuid4().hex, datetime.now().isoformat(), self.current_course, self.total_time // 60, self.total_time // 60, datetime.now().isoformat(), 'Work', self.distractions))
            
            if self.active_queue_id:
                db.c.execute("UPDATE focus_queue SET status='completed' WHERE id=?", (self.active_queue_id,))
                db.conn.commit()
                
                db.c.execute("SELECT id, duration, course, type FROM focus_queue WHERE status='pending' ORDER BY id ASC LIMIT 1")
                next_item = db.c.fetchone()
                
                if next_item:
                    self.active_queue_id = next_item[0]
                    self.total_time = int(next_item[1]) * 60
                    self.current_course = next_item[2] or "General"
                    self.time_left = self.total_time
                    self.distractions = 0
                    self.distraction_markers = []
                    
                    db.c.execute("UPDATE focus_queue SET status='active' WHERE id=?", (self.active_queue_id,))
                    db.conn.commit()
                else:
                    self.active_queue_id = None
                    self.is_running = False
                    self.timer.stop()
                    self.ovl.hide()
                    self.vision.stop()
            else:
                self.is_running = False
                self.timer.stop()
                self.ovl.hide()
                self.vision.stop()
                
            db.conn.commit()
        
        self.push_state(dist_mode)