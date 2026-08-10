"""System Bridge - Central backend for Mind Palace OS.

Handles communication between React frontend and PyQt6 backend via QWebChannel.
Refactored to use a handler-based architecture for maintainability.
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import logging
import os
import sqlite3
import subprocess
import sys
import threading
import uuid
import zipfile
from datetime import datetime, timedelta

# --- AUTOMATIC GLOBAL AUDIT LOGGING ---
logging.basicConfig(
    filename="mindpalace_audit.log",
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s [%(threadName)s] %(levelname)s - %(message)s",
)


def global_audit_tracer(frame, event, arg):
    """Global function call tracer for audit logging."""
    if event == "call":
        filename = frame.f_code.co_filename
        if "main.py" in filename or "system_bridge.py" in filename:
            func_name = frame.f_code.co_name
            if not func_name.startswith("<") and func_name not in ["tick", "process_frame", "push_state"]:
                logging.debug(f"CALL: {func_name} (Line {frame.f_lineno} in {os.path.basename(filename)})")
    return global_audit_tracer


sys.setprofile(global_audit_tracer)

# --------------------------------------

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

import cv2
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QRectF, Qt, QTime, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core_logger import audit_log, logger
from core_sys import GITHUB_TOKEN, config, db, get_color
from handlers.flashcard import FlashcardHandler
from handlers.goal import GoalHandler
from handlers.habit import HabitHandler
from handlers.health import HealthHandler
from handlers.note import NoteHandler
from handlers.nutrition import NutritionHandler
from handlers.queue import QueueHandler
from handlers.sync import SyncHandler
from horology import draw_clock_complications, draw_clock_face, draw_clock_ticks_and_indices, draw_horological_hand
from sync_manager import SyncManager
from ui import OverlayWidget, AdvancedPDFWindow, TimelapseDialog
from vision_tracker import VisionTracker


class SystemBridge(QObject):
    """Central backend bridge handling all frontend requests.

    Uses a handler-based architecture to dispatch actions to domain-specific
    handler classes, improving maintainability and separation of concerns.
    """

    state_update = pyqtSignal(str)
    video_feed = pyqtSignal(str)
    clock_feed = pyqtSignal(str)
    sync_completed = pyqtSignal(bool, str)
    scan_ready = pyqtSignal(str)
    sync_progress = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ovl = OverlayWidget()
        self.vision = VisionTracker()
        self.vision.attention_status.connect(self.handle_attention)

        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.emit_clock)
        self.clock_timer.start(1000)

        # Timer state
        self.is_running = False
        self.time_left = 0
        self.total_time = 0
        self.current_course = "General"
        self.distractions = 0
        self.distraction_markers = []
        self.active_queue_id = None
        self.current_att = True
        self.distraction_log = []
        self.was_distracted = False
        self.distraction_start = 0
        self.last_completed_session_id = None
        self.distraction_type_current = "Manual"
        self.last_session_data = None

        self._init_database()
        self._init_sync()
        self._init_timers()
        self._init_handlers()

    def _init_database(self):
        """Initialize database schema and migrations."""
        with contextlib.suppress(Exception):
            db.c.execute("ALTER TABLE pomodoro_sessions ADD COLUMN note TEXT")
            db.safe_commit()

        try:
            db.c.executescript("""
                CREATE TABLE IF NOT EXISTS ingredients (
                    id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT,
                    name TEXT UNIQUE, kcal REAL, protein REAL, fat REAL, carbs REAL,
                    image_path TEXT, is_iranian BOOLEAN DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS composite_foods (
                    id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT,
                    name TEXT UNIQUE, image_path TEXT
                );
                CREATE TABLE IF NOT EXISTS recipe_ingredients (
                    id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT,
                    composite_food_id INTEGER, ingredient_id INTEGER, amount_grams REAL
                );
            """)
            db.safe_commit()
        except Exception as e:
            print("Nutrition DB Migration Error:", e)

    def _init_sync(self):
        """Initialize sync manager and connections."""
        self.quiet_mode = config.get("quiet_mode", False)
        self.sync_manager = SyncManager()
        self.sync_manager.sync_progress.connect(self.handle_sync_progress)
        self.sync_manager.sync_completed.connect(self.handle_sync_completed)

    def _init_timers(self):
        """Initialize background timers."""
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.auto_sync)
        if config.get("sync_enabled", False):
            self.sync_timer.start(config.get("sync_interval", 3600) * 1000)

        self.backup_timer = QTimer()
        self.backup_timer.timeout.connect(self.backup_data)
        self.backup_timer.start(3600 * 1000)

        self.scan_dir = os.path.expanduser("~/MindPalace_Scans")
        self.archive_dir = os.path.join(self.scan_dir, "Archive")
        os.makedirs(self.archive_dir, exist_ok=True)

        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.check_auto_scans)
        self.scan_timer.start(10000)

        self.lib_path = os.path.expanduser("~/MindPalace_Library")
        os.makedirs(self.lib_path, exist_ok=True)
        paths = config.get("sync_local_paths", [])
        if self.lib_path not in paths:
            paths.append(self.lib_path)
            config.set("sync_local_paths", paths)

        self.active_pdf = None
        self.active_pdf_name = ""
        self.pdf_editors = []

    def _init_handlers(self):
        """Initialize domain-specific action handlers."""
        self.handlers = [
            NutritionHandler(self),
            HealthHandler(self),
            HabitHandler(self),
            FlashcardHandler(self),
            GoalHandler(self),
            NoteHandler(self),
            QueueHandler(self),
            SyncHandler(self),
        ]

    # --- Handler Dispatch ---
    def _dispatch(self, action, req):
        """Dispatch an action to the appropriate handler."""
        for handler in self.handlers:
            result = handler.handle(action, req)
            if result is not None:
                return result
        return None

    # --- Logging & Events ---
    def log_activity(self, module, desc):
        try:
            now = datetime.now().isoformat()
            db.c.execute(
                "INSERT INTO activity_logs (timestamp, module, description, uuid, modified_at) VALUES (?, ?, ?, ?, ?)",
                (now, module, desc, uuid.uuid4().hex, now),
            )
            db.safe_commit()
        except Exception:
            logger.exception("Failed to log activity")

    def handle_sync_progress(self, msg):
        print(f"[SyncManager] {msg}")
        self.sync_progress.emit(msg)

    def handle_sync_completed(self, success, msg):
        status = "SUCCESS" if success else "FAILED"
        print(f"[SyncManager] {status}: {msg}")
        config.set("git_status", "connected" if success else "error")
        config.set("git_last_sync", datetime.now().isoformat())
        self.sync_completed.emit(success, msg)
        if success:
            self.log_activity("Sync", f"Successfully synced with Git cluster. {msg}")
        else:
            self.log_activity("Sync Error", f"Sync failed: {msg}")

    def handle_attention(self, att):
        self.current_att = att

    def emit_video_frame(self, b64):
        if getattr(self, "feed_active", False):
            self.video_feed.emit(b64)

    def check_auto_scans(self):
        def worker():
            for f in os.listdir(self.scan_dir):
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
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
                        self.log_activity("Scanner", f"Auto-parsed body scan: {f}")
                        self.scan_ready.emit(json.dumps(data))

        threading.Thread(target=worker, daemon=True).start()

    def handle_sync_result(self, success, msg):
        if not success:
            QApplication.beep()

    # --- Sound & Speech ---
    def play_sound(self, sound_type="app"):
        if config.get("mute_sounds", False) or config.get("quiet_mode", False):
            return
        sound_name = config.get(f"sound_{sound_type}_dist", "Basso" if sound_type == "cam" else "Ping")
        if sys.platform == "darwin":
            path = f"/System/Library/Sounds/{sound_name}.aiff"
            if os.path.exists(path):
                subprocess.Popen(["afplay", path])
            else:
                QApplication.beep()
        elif sys.platform == "win32":
            try:
                import winsound

                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                QApplication.beep()
        else:
            QApplication.beep()

    def speak(self, text):
        if config.get("mute_speech", False) or config.get("quiet_mode", False):
            return
        if not hasattr(self, "last_speak_time") or (datetime.now() - self.last_speak_time).total_seconds() > 10:
            self.last_speak_time = datetime.now()
            if sys.platform == "darwin":
                subprocess.Popen(["say", text])
            elif sys.platform == "win32":
                try:
                    import pyttsx3

                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                except ImportError:
                    pass
            else:
                subprocess.Popen(["espeak", text], stderr=subprocess.DEVNULL)

    def set_max_volume(self):
        if sys.platform == "darwin":
            if not hasattr(self, "last_vol_time") or (datetime.now() - self.last_vol_time).total_seconds() > 10:
                self.last_vol_time = datetime.now()
                with contextlib.suppress(Exception):
                    subprocess.Popen(["osascript", "-e", "set volume output volume 100"])

    # --- Process Monitoring ---
    def get_running_processes(self):
        processes = []
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "name", "exe", "cpu_percent", "memory_percent", "create_time"]):
                with contextlib.suppress(Exception):
                    processes.append(
                        {
                            "pid": proc.info["pid"],
                            "name": proc.info["name"],
                            "cpu": proc.info["cpu_percent"] or 0,
                            "memory": proc.info["memory_percent"] or 0,
                        }
                    )
            processes.sort(key=lambda x: x["cpu"], reverse=True)
            return processes
        except ImportError:
            if sys.platform == "win32":
                try:
                    res = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True)
                    for line in res.stdout.strip().split("\n"):
                        parts = line.strip('"').split('","')
                        if len(parts) >= 2:
                            processes.append({"pid": parts[1], "name": parts[0], "cpu": 0, "memory": 0})
                except Exception:
                    pass
        return processes

    def check_processes_for_distraction(self):
        if not config.get("app_monitoring_enabled", False):
            return []
        allowed = config.get("allowed_apps", [])
        blocked = config.get("blocked_apps", [])
        if not blocked and not allowed:
            return []
        running = self.get_running_processes()
        distractions = []
        for proc in running:
            proc_name = proc["name"].lower()
            if blocked:
                for b in blocked:
                    if b.lower() in proc_name:
                        distractions.append(proc)
                        break
            elif allowed:
                is_allowed = False
                for a in allowed:
                    if a.lower() in proc_name:
                        is_allowed = True
                        break
                if not is_allowed:
                    distractions.append(proc)
        return distractions

    def kill_processes(self, processes):
        try:
            import psutil

            for proc in processes[:3]:
                with contextlib.suppress(Exception):
                    psutil.Process(proc["pid"]).terminate()
        except Exception:
            pass

    # --- Sync & Backup ---
    def auto_sync(self):
        if config.get("sync_enabled", False):
            threading.Thread(target=self.sync_manager.sync, daemon=True).start()

    def backup_data(self):
        backup_dir = os.path.join(os.path.expanduser("~"), "MindPalaceBackups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"auto_backup_{timestamp}.zip")
        settings = config.cfg.copy()
        settings.pop("sync_github_token", None)
        data = {"settings": settings, "tables": {}}
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
            "health_profile",
            "health_logs",
            "custom_foods",
            "custom_activities",
            "health_plans",
        ]
        for table in tables:
            try:
                db.c.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in db.c.description]
                data["tables"][table] = [dict(zip(columns, row, strict=False)) for row in db.c.fetchall()]
            except Exception:
                pass
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("data.json", json.dumps(data, indent=2))
        with open(backup_path, "wb") as f:
            f.write(zip_buffer.getvalue())

    # --- Goals ---
    def get_goals_tree(self):
        try:
            db.c.execute("SELECT id, parent_id, title, target_hours, deadline FROM cascading_goals")
            return [
                {"id": r[0], "parent_id": r[1], "title": r[2], "target_hours": r[3], "deadline": r[4]}
                for r in db.c.fetchall()
            ]
        except Exception:
            return []

    def get_flat_goals(self):
        try:
            db.c.execute("SELECT id, parent_id, title FROM cascading_goals")
            tree = {r[0]: {"parent": r[1], "title": r[2]} for r in db.c.fetchall()}
            paths = []
            for _gid, data in tree.items():
                path = [data["title"]]
                curr = data["parent"]
                while curr in tree:
                    path.insert(0, tree[curr]["title"])
                    curr = tree[curr]["parent"]
                paths.append(" > ".join(path))
            return sorted(paths)
        except Exception:
            return []

    def get_heatmap_data(self):
        weeks = 28
        matrix = [[0] * 7 for _ in range(weeks)]
        td = datetime.now().date()
        try:
            db.c.execute(
                "SELECT date(timestamp), sum(duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY date(timestamp)"
            )
            history = {r[0]: r[1] / 60.0 for r in db.c.fetchall()}
            for w in range(weeks):
                for d in range(7):
                    target_date = (td - timedelta(days=(weeks - w - 1) * 7 + (6 - d))).isoformat()
                    hrs = history.get(target_date, 0)
                    intensity = 0
                    if hrs > 0:
                        intensity = 1
                    if hrs > 2:
                        intensity = 2
                    if hrs > 4:
                        intensity = 3
                    if hrs > 6:
                        intensity = 4
                    matrix[w][d] = intensity
            return matrix
        except Exception:
            return matrix

    def get_cluster_master(self):
        cluster_file = os.path.join(self.sync_manager.repo_path, "cluster_state.json")
        if os.path.exists(cluster_file):
            try:
                with open(cluster_file) as f:
                    return json.load(f).get("master_id")
            except Exception:
                pass
        return None

    # --- Clock Rendering ---
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
                bg_col = QColor(0, 0, 0, 80)
                hand_col = QColor("white")
            elif "Neon" in s:
                bg_col = QColor(10, 132, 255, 50)
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

            p.save()
            p.rotate(30.0 * (t.hour() + t.minute() / 60.0))
            draw_horological_hand(p, h_style, 60, 4, True)
            p.restore()
            p.save()
            p.rotate(6.0 * (t.minute() + t.second() / 60.0))
            draw_horological_hand(p, h_style, 90, 3, False)
            p.restore()

            sec_col = QColor("#0a84ff")
            if comp == "Small Seconds":
                p.save()
                p.translate(0, int(radius - 40))
                p.setBrush(QBrush(sec_col))
                p.setPen(QPen(sec_col, 1))
                p.rotate(6.0 * t.second())
                p.drawLine(0, 0, 0, -15)
                p.restore()
            else:
                p.setBrush(QBrush(sec_col))
                p.setPen(QPen(sec_col, 2))
                p.save()
                p.rotate(6.0 * t.second())
                if h_style in ["Serpentine", "Sword", "Arrow"]:
                    draw_horological_hand(p, h_style, 100, 1, False)
                else:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawRect(-1, 0, 2, -100)
                p.restore()

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("white")))
            p.drawEllipse(-4, -4, 8, 8)
            p.end()

            buf = QByteArray()
            buffer = QBuffer(buf)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(buffer, "PNG")

            raw_bytes = bytes(buf) if hasattr(buf, "__bytes__") else bytes(buf.data())
            b64 = base64.b64encode(raw_bytes).decode("utf-8")
            self.clock_feed.emit(f"data:image/png;base64,{b64}")
        except Exception as e:
            print(f"Horology render failed: {e}")

    # --- State Management ---
    def push_state(self, dist_mode="None"):
        mins, secs = divmod(self.time_left, 60)
        time_str = f"{mins:02d}:{secs:02d}"
        pct = 100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0

        self.ovl.update_state(
            time_str,
            pct,
            (self.total_time - self.time_left) // 60,
            self.total_time // 60,
            self.current_course,
            dist_mode,
        )

        try:
            db.c.execute("SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id")
            queue_data = [
                {"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]}
                for r in db.c.fetchall()
            ]
        except Exception:
            queue_data = []

        state = {
            "is_running": self.is_running,
            "time_str": time_str,
            "progress": pct,
            "distractions": self.distractions,
            "distraction_markers": self.distraction_markers,
            "distraction_log": self.distraction_log,
            "course": self.current_course,
            "active_queue_id": self.active_queue_id,
            "queue": queue_data,
            "time_left": self.time_left,
            "total_time": self.total_time,
            "last_completed_session_id": self.last_completed_session_id,
            "last_session_data": getattr(self, "last_session_data", None),
        }
        self.state_update.emit(json.dumps(state))

    def tick(self):
        if not self.is_running:
            return

        dist_mode = "None"

        if not config.get("quiet_mode", False) and not getattr(self, "current_att", True):
            self.distractions += 1
            dist_mode = "Camera"
            self.distraction_markers.append(
                100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0
            )
            if self.distractions % 5 == 0:
                self.set_max_volume()
                self.play_sound("cam")

        if config.get("app_monitoring_enabled", False):
            app_distractions = self.check_processes_for_distraction()
            if app_distractions:
                if dist_mode == "None":
                    dist_mode = "App"
                    self.distractions += 1
                    self.distraction_markers.append(
                        100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0
                    )
                if config.get("auto_block", False):
                    self.kill_processes(app_distractions)

        if dist_mode != "None":
            if not self.was_distracted:
                self.distraction_start = self.total_time - self.time_left
                self.was_distracted = True
                self.distraction_type_current = dist_mode
        else:
            if self.was_distracted:
                dur = (self.total_time - self.time_left) - self.distraction_start
                self.distraction_log.append(
                    [
                        self.distraction_start / 60.0,
                        dur / 60.0,
                        self.distraction_type_current,
                    ]
                )
                self.was_distracted = False

        if self.time_left > 0:
            self.time_left -= 1
        else:
            self._complete_session()

    def _complete_session(self):
        """Handle session completion logic."""
        if not config.get("quiet_mode", False):
            self.speak(config.get("speech_comp", "Session Complete."))

        if self.was_distracted:
            dur = (self.total_time - self.time_left) - self.distraction_start
            self.distraction_log.append(
                [
                    self.distraction_start / 60.0,
                    dur / 60.0,
                    self.distraction_type_current,
                ]
            )
            self.was_distracted = False

        final_tl_path = getattr(self.vision, "v_path", "")

        try:
            db.c.execute(
                """INSERT INTO pomodoro_sessions
                   (course, duration, actual_duration, timestamp, type, distractions, distraction_data, timelapse_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.current_course,
                    self.total_time // 60,
                    self.total_time // 60,
                    datetime.now().isoformat(),
                    "Work",
                    self.distractions,
                    json.dumps(self.distraction_log),
                    final_tl_path,
                ),
            )
        except sqlite3.OperationalError:
            db.c.execute(
                """INSERT INTO pomodoro_sessions
                   (course, duration, actual_duration, timestamp, type, distractions)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    self.current_course,
                    self.total_time // 60,
                    self.total_time // 60,
                    datetime.now().isoformat(),
                    "Work",
                    self.distractions,
                ),
            )

        self.last_completed_session_id = db.c.lastrowid
        self.last_session_data = {
            "course": self.current_course,
            "duration": self.total_time // 60,
            "distractions": self.distractions,
            "timelapse_path": final_tl_path,
        }

        if self.active_queue_id:
            db.c.execute("UPDATE focus_queue SET status='completed' WHERE id=?", (self.active_queue_id,))
            db.safe_commit()

            db.c.execute(
                "SELECT id, duration, course, type FROM focus_queue WHERE status='pending' ORDER BY id ASC LIMIT 1"
            )
            next_item = db.c.fetchone()

            if next_item:
                self.active_queue_id = next_item[0]
                self.total_time = int(next_item[1]) * 60
                self.current_course = next_item[2] or "General"
                self.time_left = self.total_time
                self.distractions = 0
                self.distraction_markers = []
                self.distraction_log = []
                self.was_distracted = False
                self.distraction_type_current = "Manual"
                db.c.execute("UPDATE focus_queue SET status='active' WHERE id=?", (self.active_queue_id,))
                db.safe_commit()

                if not config.get("quiet_mode", False):
                    course_safe = self.current_course.replace(" ", "_").replace("/", "")
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    self.vision.start_rec(f"timelapses/Work_{course_safe}_{ts}.avi")
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

        db.safe_commit()

    # --- Main Request Dispatcher ---
    @pyqtSlot(str, result=str)
    @audit_log
    def request(self, payload):
        req = json.loads(payload)
        action = req.get("action")

        # Try handler dispatch first
        result = self._dispatch(action, req)
        if result is not None:
            return result

        # Handle core actions that require bridge state
        handler = self._core_action_handlers.get(action)
        if handler:
            return handler(req)

        return json.dumps({"error": "Unknown action"})

    @property
    def _core_action_handlers(self):
        """Map of core actions that require bridge state to handler methods."""
        return {
            "init": self._handle_init,
            "get_today_data": self._handle_get_today_data,
            "force_reset_all_data": self._handle_force_reset_all_data,
            "get_history_data": self._handle_get_history_data,
            "play_timelapse": self._handle_play_timelapse,
            "save_session_note": self._handle_save_session_note,
            "save_settings": self._handle_save_settings,
            "save_file": self._handle_save_file,
            "get_device_id": self._handle_get_device_id,
            "set_vision_ui": self._handle_set_vision_ui,
            "toggle_feed": self._handle_toggle_feed,
            "map_folder": self._handle_map_folder,
            "unmap_folder": self._handle_unmap_folder,
            "get_mapped_folders": self._handle_get_mapped_folders,
            "open_network_folder": self._handle_open_network_folder,
            "get_sync_status": self._handle_get_sync_status,
            "set_quiet_mode": self._handle_set_quiet_mode,
            "reset_data": self._handle_reset_data,
            "open_file_dialog": self._handle_open_file_dialog,
            "open_folder_dialog": self._handle_open_folder_dialog,
            "lib_list": self._handle_lib_list,
            "lib_open": self._handle_lib_open,
            "lib_page": self._handle_lib_page,
            "lib_annot": self._handle_lib_annot,
            "lib_open_native": self._handle_lib_open_native,
            "get_processes": self._handle_get_processes,
            "get_app_monitoring_status": self._handle_get_app_monitoring_status,
            "set_allowed_apps": self._handle_set_allowed_apps,
            "set_blocked_apps": self._handle_set_blocked_apps,
            "set_app_monitoring": self._handle_set_app_monitoring,
            "set_auto_block": self._handle_set_auto_block,
            "check_current_distractions": self._handle_check_distractions,
            "import_body_scan": self._handle_import_body_scan,
            "start_timer": self._handle_start_timer,
            "stop_timer": self._handle_stop_timer,
            "pause_timer": self._handle_pause_timer,
            "resume_timer": self._handle_resume_timer,
            "export_data": self._handle_export_data,
            "import_data": self._handle_import_data,
        }

    def _handle_init(self, req):
        today_str = datetime.now().date().isoformat()
        ydy_str = (datetime.now().date() - timedelta(days=1)).isoformat()

        try:
            db.c.execute(
                "SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?",
                (today_str,),
            )
            tdy_study = db.c.fetchone()[0] or 0
            db.c.execute(
                "SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?",
                (ydy_str,),
            )
            ydy_study = db.c.fetchone()[0] or 0
            db.c.execute(
                "SELECT sum(distractions) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?",
                (today_str,),
            )
            tdy_dist = db.c.fetchone()[0] or 0
            db.c.execute(
                "SELECT sum(distractions) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?",
                (ydy_str,),
            )
            ydy_dist = db.c.fetchone()[0] or 0

            vols = []
            for h in range(8, 20):
                db.c.execute(
                    "SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=? AND cast(strftime('%H', timestamp) as integer)=?",
                    (today_str, h),
                )
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

            db.c.execute("SELECT id, log_type, date, data_json FROM health_logs")
            h_logs = [{"id": r[0], "type": r[1], "date": r[2], "data": json.loads(r[3])} for r in db.c.fetchall()]

            try:
                db.c.execute(
                    "SELECT timestamp, module, description FROM activity_logs ORDER BY timestamp DESC LIMIT 50"
                )
                act_logs = [{"timestamp": r[0], "module": r[1], "description": r[2]} for r in db.c.fetchall()]
            except Exception:
                act_logs = []

            ccolors = {}
            for c in db.c.execute("SELECT name FROM courses").fetchall():
                ccolors[c[0]] = get_color(c[0]).name()

            flat_goals = self.get_flat_goals()
            for fg in flat_goals:
                root_name = fg.split(" > ")[0]
                root_color = get_color(root_name).name()
                ccolors[fg] = root_color
                raw_title = fg.split(" > ")[-1]
                if raw_title not in ccolors:
                    ccolors[raw_title] = root_color

            ccolors["General"] = get_color("General").name()
            ccolors["Break"] = get_color("Break").name()

            return json.dumps(
                {
                    "course_colors": ccolors,
                    "flat_goals": flat_goals,
                    "goals": self.get_goals_tree(),
                    "heatmap": self.get_heatmap_data(),
                    "settings": config.cfg,
                    "activity_logs": act_logs,
                    "habits": [
                        {"id": r[0], "name": r[1], "type": r[2]}
                        for r in db.c.execute("SELECT id, name, type FROM habits").fetchall()
                    ],
                    "habit_logs": [
                        {"habit_id": r[0], "date": r[1], "status": r[2]}
                        for r in db.c.execute("SELECT habit_id, date, status FROM habit_logs").fetchall()
                    ],
                    "flashcards": [
                        {
                            "id": r[0],
                            "front": r[1],
                            "back": r[2],
                            "deck": r[3],
                            "course": r[4],
                            "folder": r[5],
                            "color": r[6],
                        }
                        for r in db.c.execute(
                            "SELECT id, front, back, deck, course, folder, color FROM flashcards"
                        ).fetchall()
                    ],
                    "quizzes": [
                        {"id": r[0], "title": r[1], "json": r[2], "course": r[3], "folder": r[4], "color": r[5]}
                        for r in db.c.execute(
                            "SELECT id, title, questions_json, course, folder, color FROM quizzes"
                        ).fetchall()
                    ],
                    "queue": [
                        {"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]}
                        for r in db.c.execute(
                            "SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id"
                        ).fetchall()
                    ],
                    "notes": [
                        {"id": r[0], "title": r[1], "content": r[2], "course": r[3], "folder": r[4], "color": r[5]}
                        for r in db.c.execute(
                            "SELECT id, title, content, course, folder, color FROM notes ORDER BY id DESC"
                        ).fetchall()
                    ],
                    "health_profile": json.loads(h_prof[0]) if h_prof else {},
                    "health_logs": h_logs,
                    "custom_foods": [
                        {
                            "id": r[0],
                            "name": r[1],
                            "kcal": r[2],
                            "protein": r[3],
                            "fat": r[4],
                            "carbs": r[5],
                            "category": r[6],
                        }
                        for r in db.c.execute(
                            "SELECT id, name, kcal, protein, fat, carbs, category FROM custom_foods"
                        ).fetchall()
                    ],
                    "custom_activities": [
                        {"id": r[0], "name": r[1], "met": r[2], "category": r[3]}
                        for r in db.c.execute("SELECT id, name, met, category FROM custom_activities").fetchall()
                    ],
                    "health_plans": [
                        {"id": r[0], "type": r[1], "title": r[2], "details": r[3]}
                        for r in db.c.execute("SELECT id, type, title, details FROM health_plans").fetchall()
                    ],
                    "metrics_data": {
                        "tdy_study": tdy_study / 60.0,
                        "ydy_study": ydy_study / 60.0,
                        "tdy_dist": tdy_dist,
                        "ydy_dist": ydy_dist,
                        "hourly_vol": vols,
                        "global_study_hours": global_study_hours,
                        "global_target_hours": global_target_hours,
                    },
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_get_today_data(self, req):
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            db.c.execute(
                "SELECT id, course, duration, actual_duration, timestamp, type, distractions, timelapse_path, distraction_data, note "
                "FROM pomodoro_sessions WHERE timestamp LIKE ? ORDER BY timestamp ASC",
                (today_str + "%",),
            )
            today_sessions = [
                {
                    "id": r[0],
                    "course": r[1],
                    "duration": r[2],
                    "actual_duration": r[3],
                    "timestamp": r[4],
                    "type": r[5],
                    "distractions": r[6],
                    "timelapse_path": r[7],
                    "distraction_data": json.loads(r[8] if r[8] else "[]"),
                    "note": r[9] or "",
                }
                for r in db.c.fetchall()
            ]

            db.c.execute(
                "SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND timestamp LIKE ?",
                (today_str + "%",),
            )
            studied = {r[0]: (r[1] or 0) / 60.0 for r in db.c.fetchall()}

            return json.dumps({"today_sessions": today_sessions, "studied_hours": studied})
        except Exception:
            return json.dumps({"today_sessions": [], "studied_hours": {}})

    def _handle_force_reset_all_data(self, req):
        try:
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
                "deleted_uuids",
            ]
            for table in tables_to_clear:
                with contextlib.suppress(Exception):
                    db.c.execute(f"DELETE FROM {table}")
            db.safe_commit()

            # Preserve sync settings
            repo_url = config.get("sync_repo_url", "")
            token = config.get("sync_github_token", "")
            sync_enabled = config.get("sync_enabled", False)
            sync_interval = config.get("sync_interval", 3600)

            new_config = config.defaults.copy()
            new_config.update(
                {
                    "sync_repo_url": repo_url,
                    "sync_github_token": token,
                    "sync_enabled": sync_enabled,
                    "sync_interval": sync_interval,
                    "git_status": "unknown",
                    "git_last_sync": None,
                    "sync_msg": "",
                    "sync_progress_pct": 0,
                }
            )

            config.cfg = new_config
            with open(config.fn, "w") as f:
                json.dump(config.cfg, f)

            # Delete local Git sync repository
            import shutil
            import time

            repo_path = os.path.expanduser("~/.mindpalace_sync_repo")
            if os.path.exists(repo_path):
                for attempt in range(5):
                    try:
                        if sys.platform == "win32":
                            subprocess.run(
                                ["attrib", "-r", "-s", "/s", "/d", repo_path],
                                capture_output=True,
                                shell=True,
                            )
                        shutil.rmtree(repo_path)
                        break
                    except Exception as e:
                        print(f"Delete attempt {attempt + 1} failed: {e}")
                        time.sleep(1)
                        if attempt == 4:
                            renamed_path = repo_path + "_old_" + str(int(time.time()))
                            try:
                                os.rename(repo_path, renamed_path)
                                print(f"Renamed repo to {renamed_path}")
                            except Exception:
                                print("Could not delete or rename repo - manual cleanup required")

            self.log_activity("System", "Force reset all data performed")
            return json.dumps({"status": "success", "message": "All local data wiped."})
        except Exception as e:
            self.log_activity("System Error", f"Force reset failed: {e!s}")
            return json.dumps({"status": "error", "message": str(e)})

    def _handle_get_history_data(self, req):
        try:
            db.c.execute(
                "SELECT id, course, duration, actual_duration, timestamp, type, distractions, timelapse_path, distraction_data, note "
                "FROM pomodoro_sessions ORDER BY timestamp DESC"
            )
            history = [
                {
                    "id": r[0],
                    "course": r[1],
                    "duration": r[2],
                    "actual_duration": r[3],
                    "timestamp": r[4],
                    "type": r[5],
                    "distractions": r[6],
                    "timelapse_path": r[7],
                    "distraction_data": json.loads(r[8] if r[8] else "[]"),
                    "note": r[9] or "",
                }
                for r in db.c.fetchall()
            ]
            return json.dumps({"history_sessions": history})
        except Exception:
            return json.dumps({"history_sessions": []})

    def _handle_play_timelapse(self, req):
        try:
            path = req.get("path")
            if os.path.exists(path):
                if not hasattr(self, "tl_dlg"):
                    self.tl_dlg = None
                self.tl_dlg = TimelapseDialog(
                    path,
                    req.get("duration", 0),
                    req.get("distractions", 0),
                    req.get("data", {}),
                )
                self.tl_dlg.show()
                self.tl_dlg.raise_()
                self.tl_dlg.activateWindow()
        except Exception:
            import traceback

            print("Timelapse Playback Error:", traceback.format_exc())
        return json.dumps({"status": "ok"})

    def _handle_save_session_note(self, req):
        s_id = req.get("session_id")
        note = req.get("note")
        if s_id:
            db.c.execute("UPDATE pomodoro_sessions SET note = ? WHERE id = ?", (note, s_id))
            db.safe_commit()
        return json.dumps({"status": "ok"})

    def _handle_save_settings(self, req):
        for k, v in req.get("data", {}).items():
            config.set(k, v)
        self.log_activity("Settings", "Updated application settings via UI.")
        return json.dumps({"status": "saved"})

    def _handle_save_file(self, req):
        parent = QApplication.activeWindow()
        ext = req.get("ext", "txt")
        content = req.get("content", "")
        title = req.get("title", "Export")
        file_path, _ = QFileDialog.getSaveFileName(parent, "Save File", f"{title}.{ext}", f"Files (*.{ext})")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return json.dumps({"status": "saved", "path": file_path})
            except Exception as e:
                return json.dumps({"status": "error", "message": str(e)})
        return json.dumps({"status": "cancelled"})

    def _handle_get_device_id(self, req):
        return json.dumps({"device_id": self.sync_manager.device_id})

    def _handle_set_vision_ui(self, req):
        self.vision.ui_active = req.get("active", False)
        return json.dumps({"status": "ok"})

    def _handle_toggle_feed(self, req):
        self.feed_active = req.get("enabled", False)
        return json.dumps({"status": "ok"})

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
        discovered_nodes = {f["device_id"] for f in net_folders}

        if os.path.exists(repo_path):
            for root_dir, _, files in os.walk(repo_path):
                if ".git" in root_dir:
                    continue
                for f in files:
                    if f.endswith(".json"):
                        try:
                            with open(os.path.join(root_dir, f), encoding="utf-8") as tmp_f:
                                d = json.load(tmp_f)
                                dev_id = d.get("device_id")
                                if dev_id and dev_id not in discovered_nodes:
                                    discovered_nodes.add(dev_id)
                                    net_folders.append(
                                        {
                                            "device_id": dev_id,
                                            "is_local": dev_id == self.sync_manager.device_id,
                                            "file_count": 1,
                                            "last_update": d.get("last_sync", "Unknown").replace("T", " ")[:16],
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

    def _handle_reset_data(self, req):
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
            "course_targets",
            "starred_questions",
            "exams",
            "todos",
        ]
        for table in tables_to_clear:
            with contextlib.suppress(Exception):
                db.c.execute(f"DELETE FROM {table}")
        db.safe_commit()
        return json.dumps({"status": "cleared"})

    def _handle_open_file_dialog(self, req):
        parent = QApplication.activeWindow()
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "Select a file",
            "",
            "All Files (*.*);;JSON (*.json);;Images (*.png *.jpg)",
        )
        return json.dumps({"path": file_path if file_path else ""})

    def _handle_open_folder_dialog(self, req):
        parent = QApplication.activeWindow()
        folder_path = QFileDialog.getExistingDirectory(parent, "Select a folder", "")
        return json.dumps({"path": folder_path if folder_path else ""})

    def _handle_lib_list(self, req):
        lib_files = []
        if os.path.exists(self.lib_path):
            for f in os.listdir(self.lib_path):
                if f.lower().endswith(".pdf"):
                    full_path = os.path.join(self.lib_path, f)
                    lib_files.append(
                        {
                            "name": f,
                            "path": full_path,
                            "size": os.path.getsize(full_path),
                        }
                    )
        return json.dumps({"files": lib_files})

    def _handle_lib_open(self, req):
        filename = req.get("filename")
        path = os.path.join(self.lib_path, filename)
        if os.path.exists(path):
            if self.active_pdf:
                self.active_pdf.close()
            self.active_pdf = pymupdf.open(path)
            self.active_pdf_name = filename
            return json.dumps({"status": "ok", "total_pages": len(self.active_pdf)})
        return json.dumps({"error": f"File not found at {path}"})

    def _handle_lib_page(self, req):
        page_num = req.get("page", 0)
        zoom = req.get("zoom", 1.5)
        if self.active_pdf and 0 <= page_num < len(self.active_pdf):
            page = self.active_pdf[page_num]
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            img_data = pix.tobytes("png")
            b64 = base64.b64encode(img_data).decode("utf-8")

            annots = []
            annot = page.first_annot
            while annot:
                info = annot.info
                annots.append(
                    {
                        "subject": info.get("subject", "Unknown"),
                        "title": info.get("title", ""),
                        "content": info.get("content", ""),
                    }
                )
                annot = annot.next

            return json.dumps(
                {
                    "b64": b64,
                    "width": pix.width,
                    "height": pix.height,
                    "annots": annots,
                }
            )
        return json.dumps({"error": "Invalid page"})

    def _handle_lib_annot(self, req):
        page_num = req.get("page")
        rect_coords = req.get("rect")
        tool = req.get("tool")
        text = req.get("text", "")

        if self.active_pdf and 0 <= page_num < len(self.active_pdf):
            page = self.active_pdf[page_num]
            x0, y0, x1, y1 = rect_coords
            pdf_rect = pymupdf.Rect(x0, y0, x1, y1)

            dirty = False
            if tool in ["Highlight", "Underline"]:
                words = page.get_text("words")
                quads = [
                    pymupdf.Rect(w[:4])
                    for w in words
                    if pymupdf.Rect(w[:4]).intersects(pdf_rect)
                ]
                if quads:
                    annot = (
                        page.add_highlight_annot(quads)
                        if tool == "Highlight"
                        else page.add_underline_annot(quads)
                    )
                    annot.set_colors(
                        stroke=(1, 1, 0) if tool == "Highlight" else (0, 0, 1)
                    )
                    annot.set_info(
                        info={
                            "title": "Web UI",
                            "subject": tool,
                            "content": "Marked via Web UI",
                        }
                    )
                    annot.update()
                    dirty = True
            elif tool == "Note":
                annot = page.add_text_annot(pdf_rect.tl, text)
                annot.set_info(info={"title": "Web UI", "subject": "Note", "content": text})
                annot.update()
                dirty = True

            if dirty:
                with contextlib.suppress(Exception):
                    self.active_pdf.save(
                        self.active_pdf.name,
                        incremental=True,
                        encryption=pymupdf.PDF_ENCRYPT_KEEP,
                    )
            return json.dumps({"status": "ok"})
        return json.dumps({"error": "Failed to add annotation"})

    def _handle_lib_open_native(self, req):
        try:
            from native_pdf_editor import NativePDFEditor

            filename = req.get("filename")
            filepath = os.path.join(self.lib_path, filename)
            if os.path.exists(filepath):
                if not hasattr(self, "pdf_editors"):
                    self.pdf_editors = []
                editor = NativePDFEditor(filepath)
                editor.show()
                self.pdf_editors.append(editor)
                return json.dumps({"status": "opened"})
            return json.dumps({"error": f"File not found at {filepath}"})
        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return json.dumps({"error": f"Native boot failure: {str(e)}"})

    def _handle_get_processes(self, req):
        return json.dumps(
            {
                "processes": [
                    {"name": p["name"], "pid": p["pid"], "cpu": p["cpu"], "memory": p["memory"]}
                    for p in self.get_running_processes()[:50]
                ],
            }
        )

    def _handle_get_app_monitoring_status(self, req):
        return json.dumps(
            {
                "enabled": config.get("app_monitoring_enabled", False),
                "allowed_apps": config.get("allowed_apps", []),
                "blocked_apps": config.get("blocked_apps", []),
                "auto_block": config.get("auto_block", False),
            }
        )

    def _handle_set_allowed_apps(self, req):
        apps = req.get("apps", [])
        config.set("allowed_apps", apps)
        return json.dumps({"status": "ok", "allowed_apps": apps})

    def _handle_set_blocked_apps(self, req):
        apps = req.get("apps", [])
        config.set("blocked_apps", apps)
        return json.dumps({"status": "ok", "blocked_apps": apps})

    def _handle_set_app_monitoring(self, req):
        enabled = req.get("enabled", False)
        config.set("app_monitoring_enabled", enabled)
        return json.dumps({"status": "ok", "enabled": enabled})

    def _handle_set_auto_block(self, req):
        enabled = req.get("enabled", False)
        config.set("auto_block", enabled)
        return json.dumps({"status": "ok", "auto_block": enabled})

    def _handle_check_distractions(self, req):
        return json.dumps({"distractions": self.check_processes_for_distraction()})

    def _handle_import_body_scan(self, req):
        parent = QApplication.activeWindow()
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "Select Body Scan Image",
            "",
            "Images (*.png *.jpg *.jpeg)",
        )
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

    def _handle_start_timer(self, req):
        if req.get("queue_id") == "auto":
            db.c.execute(
                "SELECT id, duration, course, type FROM focus_queue WHERE status='pending' ORDER BY id ASC LIMIT 1"
            )
            q = db.c.fetchone()
            if q:
                self.active_queue_id = q[0]
                self.total_time = int(q[1]) * 60
                self.current_course = q[2] or "General"
                db.c.execute("UPDATE focus_queue SET status='active' WHERE id=?", (self.active_queue_id,))
                db.safe_commit()
        else:
            self.current_course = req.get("course", "General")
            self.total_time = int(req.get("duration", 25)) * 60

        self.time_left = self.total_time
        self.distractions = 0
        self.distraction_markers = []
        self.distraction_log = []
        self.was_distracted = False
        self.last_completed_session_id = None
        self.last_session_data = None
        self.distraction_type_current = "Manual"

        self.is_running = True
        self.ovl.show()

        if not config.get("quiet_mode", False):
            self.vision.start()
            course_safe = self.current_course.replace(" ", "_").replace("/", "")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.vision.start_rec(f"timelapses/Work_{course_safe}_{ts}.avi")

        self.timer.start(1000)
        self.push_state()
        return json.dumps({"status": "started"})

    def _handle_stop_timer(self, req):
        self.is_running = False
        self.timer.stop()
        self.ovl.hide()
        self.vision.stop()
        self.time_left = 0

        if self.active_queue_id:
            db.c.execute("UPDATE focus_queue SET status='pending' WHERE id=?", (self.active_queue_id,))
            self.active_queue_id = None
            db.safe_commit()

        self.push_state()
        return json.dumps({"status": "stopped"})

    def _handle_pause_timer(self, req):
        if self.is_running:
            self.is_running = False
            self.timer.stop()
            self.vision.stop()
            if self.was_distracted:
                dur = (self.total_time - self.time_left) - self.distraction_start
                self.distraction_log.append(
                    [
                        self.distraction_start / 60.0,
                        dur / 60.0,
                        self.distraction_type_current,
                    ]
                )
                self.was_distracted = False
            self.push_state()
        return json.dumps({"status": "paused"})

    def _handle_resume_timer(self, req):
        if not self.is_running and self.time_left > 0:
            self.is_running = True
            self.timer.start(1000)
            if not config.get("quiet_mode", False):
                self.vision.start()
            self.push_state()
        return json.dumps({"status": "resumed"})

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
                        set_clause = ", ".join([f"{k} = ?" for k in row if k != "id"])
                        values = [row[k] for k in row if k != "id"] + [existing_id]
                        db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                else:
                    row.pop("id", None)
                    cols = ", ".join(row.keys())
                    placeholders = ", ".join(["?"] * len(row))
                    db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
        db.safe_commit()
        return self.request(json.dumps({"action": "init"}))
