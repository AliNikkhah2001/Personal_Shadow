import hashlib
import json
import os
import sqlite3
import threading

from PyQt6.QtGui import QColor


def load_env_file():
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, encoding='utf-8-sig') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip().strip('"\'')
            return True
        except Exception as e:
            print(f"⚠️ Could not load .env: {e}")
            return False
    return False

load_env_file()
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
CACHE_DIR = os.path.abspath("shadow_os_cache")

class ConfigManager:
    def __init__(self, fn="config.json"):
        self.fn = fn
        self.defaults = {
            "font_family": "Inter", "custom_font_path": "", "font_color": "#e2e8f0", "font_size": 16,
            "clock_style": "Analog Classic", "clock_case_shape": "Round", "clock_bezel": "Plain",
            "clock_indices": "Baton", "clock_ticks": "Standard", "clock_hands": "Classic", "clock_complication": "None",
            "dist_delay": 3, "vision_mode": "Strict (Face & Eyes)", "bg_image_path": "img/bg.jpg", "quotes_path": "",
            "panel_opacity": 180, "face_scale_factor": 1.2, "face_min_neighbors": 8, "face_min_size": 120,
            "vision_sample_interval": 30, "force_close_apps_mins": 5, "sound_app_dist": "Ping",
            "sound_cam_dist": "Basso", "sound_cam_err": "Hero", "beep_freq": 3,
            "loop_1m": 2, "loop_5m": 5, "loop_15m": 10, "loop_30m": 20, "loop_60m": 30,
            "speech_dist": "You have been distracted. Please return to work.",
            "speech_comp": "Fantastic job! Your deep work session is complete.",
            "mute_sounds": False, "mute_speech": False,
            "sync_enabled": True, "sync_repo_url": "", "sync_interval": 3600, "sync_local_paths": [],
            "quiet_mode": False, "app_monitoring_enabled": False, "allowed_apps": [], "blocked_apps": [], "auto_block": False,
            "dashboard_layout": {},
            "timeline_start_hour": 0, "timeline_end_hour": 24, "timeline_pixel_per_hour": 120
        }
        try:
            with open(fn) as f: self.cfg = json.load(f)
        except: self.cfg = self.defaults.copy()
        for k, v in self.defaults.items():
            if self.cfg.get(k) is None: self.cfg[k] = v

    def get(self, k, d=None): return self.cfg.get(k, d if d is not None else self.defaults.get(k))
    def set(self, k, v):
        self.cfg[k] = v
        try:
            with open(self.fn, 'w') as f:
                json.dump(self.cfg, f)
        except PermissionError as e:
            print(f"⚠️ Permission denied writing to {self.fn}: {e}")
            # Write to a temp file as fallback
            import tempfile
            tmp_path = os.path.join(tempfile.gettempdir(), "config_fallback.json")
            with open(tmp_path, 'w') as f:
                json.dump(self.cfg, f)
            print(f"⚠️ Config saved to fallback location: {tmp_path}")

config = ConfigManager()

# Ensure PDF Library is automatically created and synced
lib_path = os.path.expanduser("~/MindPalace_Library")
os.makedirs(lib_path, exist_ok=True)
if lib_path not in config.cfg.get("sync_local_paths", []):
    paths = config.cfg.get("sync_local_paths", [])
    paths.append(lib_path)
    config.set("sync_local_paths", paths)

class DatabaseManager:
    def __init__(self, db_name="second_brain.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.c = self.conn.cursor()
        self._lock = threading.Lock()
        self.setup()
        self.auto_migrate()

    def setup(self):
        self.c.executescript('''
            CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY, name TEXT UNIQUE, target_hours REAL DEFAULT 0, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS pomodoro_sessions (id INTEGER PRIMARY KEY, course TEXT, duration INTEGER, actual_duration INTEGER, timestamp TEXT, type TEXT, distractions INTEGER DEFAULT 0, timelapse_path TEXT, distraction_data TEXT, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS cascading_goals (id INTEGER PRIMARY KEY, parent_id INTEGER, level TEXT, title TEXT, category TEXT, target_hours REAL DEFAULT 0, logged_hours REAL DEFAULT 0, deadline TEXT, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS habits (id INTEGER PRIMARY KEY, name TEXT UNIQUE, created_at TEXT, type TEXT DEFAULT 'Positive', uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS habit_logs (id INTEGER PRIMARY KEY, habit_id INTEGER, date TEXT, status INTEGER DEFAULT 0, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS flashcards (id INTEGER PRIMARY KEY, front TEXT, back TEXT, deck TEXT, next_review TEXT, course TEXT, folder TEXT DEFAULT 'Uncategorized', color TEXT DEFAULT '#3b82f6', uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS quizzes (id INTEGER PRIMARY KEY, title TEXT, questions_json TEXT, course TEXT, folder TEXT DEFAULT 'Uncategorized', color TEXT DEFAULT '#3b82f6', uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS focus_queue (id INTEGER PRIMARY KEY, title TEXT, duration INTEGER, type TEXT, status TEXT, course TEXT, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT, timestamp TEXT, course TEXT, folder TEXT DEFAULT 'Uncategorized', color TEXT DEFAULT '#3b82f6', uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS health_profile (id INTEGER PRIMARY KEY, data_json TEXT, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS health_logs (id INTEGER PRIMARY KEY, log_type TEXT, date TEXT, data_json TEXT, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS custom_foods (id INTEGER PRIMARY KEY, name TEXT UNIQUE, kcal REAL, protein REAL, fat REAL, carbs REAL, category TEXT, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS custom_activities (id INTEGER PRIMARY KEY, name TEXT UNIQUE, met REAL, category TEXT, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS health_plans (id INTEGER PRIMARY KEY, type TEXT, title TEXT, details TEXT, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY, timestamp TEXT, module TEXT, description TEXT, uuid TEXT UNIQUE, modified_at TEXT);
            CREATE TABLE IF NOT EXISTS deleted_uuids(table_name TEXT, uuid TEXT, deleted_at TEXT, PRIMARY KEY (table_name, uuid));
            CREATE TABLE IF NOT EXISTS ingredients (id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT, name TEXT UNIQUE, kcal REAL, protein REAL, fat REAL, carbs REAL, serving_size REAL DEFAULT 100, serving_unit TEXT DEFAULT 'g', category TEXT DEFAULT 'General', image_path TEXT, is_iranian INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS composite_foods (id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT, name TEXT UNIQUE, image_path TEXT, instructions TEXT, prep_time_min INTEGER DEFAULT 0, cook_time_min INTEGER DEFAULT 0, servings INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS recipe_ingredients (id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT, composite_food_id INTEGER, ingredient_id INTEGER, amount_grams REAL, FOREIGN KEY(composite_food_id) REFERENCES composite_foods(id), FOREIGN KEY(ingredient_id) REFERENCES ingredients(id));
            CREATE TABLE IF NOT EXISTS food_logs (id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT, date TEXT, meal_type TEXT, food_type TEXT, food_id INTEGER, amount_grams REAL, uuid_ref TEXT);
            CREATE TABLE IF NOT EXISTS daily_metrics (id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT, date TEXT UNIQUE, sleep_hours REAL, sleep_quality INTEGER, energy_level INTEGER, mood_tags TEXT, stress_level INTEGER, notes TEXT);
        ''')
        self.safe_commit()

    def auto_migrate(self):
        import uuid
        from datetime import datetime

        tables_to_sync = [
            "courses", "pomodoro_sessions", "cascading_goals", "habits",
            "habit_logs", "flashcards", "quizzes", "focus_queue", "notes",
            "health_profile", "health_logs", "custom_foods", "custom_activities", "health_plans", "activity_logs",
            "ingredients", "composite_foods", "recipe_ingredients", "food_logs",
            "daily_metrics"
        ]

        # Column migrations for existing tables
        column_migrations = {
            "ingredients": [
                ("serving_size", "REAL DEFAULT 100"),
                ("serving_unit", "TEXT DEFAULT 'g'"),
                ("category", "TEXT DEFAULT 'General'"),
            ],
            "composite_foods": [
                ("instructions", "TEXT DEFAULT ''"),
                ("prep_time_min", "INTEGER DEFAULT 0"),
                ("cook_time_min", "INTEGER DEFAULT 0"),
                ("servings", "INTEGER DEFAULT 1"),
            ],
        }

        self.c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = [r[0] for r in self.c.fetchall()]

        for table in tables_to_sync:
            if table not in existing: continue

            self.c.execute(f"PRAGMA table_info({table})")
            cols = [col[1] for col in self.c.fetchall()]

            if "uuid" not in cols:
                try:
                    self.c.execute(f"ALTER TABLE {table} ADD COLUMN uuid TEXT UNIQUE")
                    self.c.execute(f"ALTER TABLE {table} ADD COLUMN modified_at TEXT")
                    print(f"[DB Migration] Upgraded table: {table}")
                except Exception as e:
                    print(f"Migration error on {table}: {e}")

            # Add missing columns for nutrition tables
            if table in column_migrations:
                for col_name, col_def in column_migrations[table]:
                    if col_name not in cols:
                        try:
                            self.c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                            print(f"[DB Migration] Added column {col_name} to {table}")
                        except Exception as e:
                            print(f"Migration error adding {col_name} to {table}: {e}")

            self.c.execute(f"SELECT id FROM {table} WHERE uuid IS NULL")
            rows = self.c.fetchall()
            if rows:
                now = datetime.now().isoformat()
                for r in rows:
                    self.c.execute(f"UPDATE {table} SET uuid=?, modified_at=? WHERE id=?", (uuid.uuid4().hex, now, r[0]))
                print(f"[DB Migration] Generated {len(rows)} UUIDs for {table}")

        self.safe_commit()

    def safe_commit(self):
        with self._lock:
            self.conn.commit()

db = DatabaseManager()

def get_color(c_name):
    if c_name == "Break": return QColor(100,100,100,200)
    if not c_name or c_name == "None": return QColor("#40c463")
    return QColor(f"#{hashlib.md5(c_name.encode()).hexdigest()[:6]}")
