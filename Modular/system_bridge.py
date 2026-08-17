"""System Bridge - Central backend for Mind Palace OS.

Handles communication between the frontend and PyQt6 backend via QWebChannel.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys

# Force Python to look in the current directory for custom modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from bridge import (
    DashboardActionsMixin,
    MediaActionsMixin,
    RuntimeServicesMixin,
    SessionMixin,
    SyncDataActionsMixin,
)
from core_logger import audit_log
from core_sys import config, db
from handlers.analytics import AnalyticsHandler
from handlers.flashcard import FlashcardHandler
from handlers.food_detection import FoodDetectionHandler
from handlers.goal import GoalHandler
from handlers.habit import HabitHandler
from handlers.health import HealthHandler
from handlers.note import NoteHandler
from handlers.nutrition import NutritionHandler
from handlers.queue import QueueHandler
from handlers.sync import SyncHandler
from handlers.filesharing import FileSharingHandler
from handlers.wallpaper import WallpaperHandler
from sync_manager import SyncManager
from ui import OverlayWidget
from vision_tracker import VisionTracker

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
        is_bridge_module = (
            os.path.basename(filename) == "system_bridge.py" or os.path.basename(os.path.dirname(filename)) == "bridge"
        )
        if "main.py" in filename or is_bridge_module:
            func_name = frame.f_code.co_name
            if not func_name.startswith("<") and func_name not in ["tick", "process_frame", "push_state"]:
                logging.debug(f"CALL: {func_name} (Line {frame.f_lineno} in {os.path.basename(filename)})")
    return global_audit_tracer


if os.getenv("MINDPALACE_TRACE") == "1":
    sys.setprofile(global_audit_tracer)

# --------------------------------------


class SystemBridge(
    RuntimeServicesMixin,
    SessionMixin,
    DashboardActionsMixin,
    MediaActionsMixin,
    SyncDataActionsMixin,
    QObject,
):
    """Central backend bridge handling all frontend requests."""

    state_update = pyqtSignal(str)
    video_feed = pyqtSignal(str)
    clock_feed = pyqtSignal(str)
    sync_completed = pyqtSignal(bool, str)
    scan_ready = pyqtSignal(str)
    sync_progress = pyqtSignal(str)

    @property
    def config(self):
        from core_sys import config as cfg
        return cfg

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
        """Initialize background timers and managed storage locations."""
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
            FileSharingHandler(self),
            AnalyticsHandler(self),
            FoodDetectionHandler(self),
            WallpaperHandler(self),
        ]

    def _dispatch(self, action, req):
        """Dispatch an action to the appropriate domain handler."""
        for handler in self.handlers:
            result = handler.handle(action, req)
            if result is not None:
                return result
        return None

    @pyqtSlot(str, result=str)
    @audit_log
    def request(self, payload):
        req = json.loads(payload)
        action = req.get("action")

        result = self._dispatch(action, req)
        if result is not None:
            return result

        handler = self._core_action_handlers.get(action)
        if handler:
            return handler(req)

        return json.dumps({"error": "Unknown action"})

    @property
    def _core_action_handlers(self):
        """Map core actions requiring bridge state to implementation methods."""
        return {
            "init": self._handle_init,
            "get_today_data": self._handle_get_today_data,
            "force_reset_all_data": self._handle_force_reset_all_data,
            "get_history_data": self._handle_get_history_data,
            "play_timelapse": self._handle_play_timelapse,
            "save_session_note": self._handle_save_session_note,
            "save_settings": self._handle_save_settings,
            "dump_ui_state": self._handle_dump_ui_state,
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
