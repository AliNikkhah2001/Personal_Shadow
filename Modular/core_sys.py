import os
import sys
import json
import sqlite3
import hashlib
import subprocess
import platform

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

def load_env_file():
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    print(f"Looking for .env at: {env_file}")
    
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip().strip('"\'')
            token = os.getenv('GITHUB_TOKEN', '')
            if token:
                print(f"✅ GitHub token loaded from .env ({token[:4]}...{token[-4:]})")
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
            "dashboard_layout": {}
        }
        try:
            with open(fn, 'r') as f: self.cfg = json.load(f)
        except: self.cfg = self.defaults.copy()
        
    def get(self, k, d=None): return self.cfg.get(k, d if d is not None else self.defaults.get(k))
    def set(self, k, v):
        self.cfg[k] = v
        with open(self.fn, 'w') as f: json.dump(self.cfg, f)

config = ConfigManager()

class DatabaseManager:
    def __init__(self, db_name="second_brain.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.c = self.conn.cursor()
        self.setup()
        
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
        ''')
        self.conn.commit()

db = DatabaseManager()

def get_color(c_name): 
    if c_name == "Break": return QColor(100,100,100,200)
    if not c_name or c_name == "None": return QColor("#40c463")
    return QColor(f"#{hashlib.md5(c_name.encode()).hexdigest()[:6]}")

def play_system_sound(sound_name):
    if config.get("mute_sounds", False) or config.get("quiet_mode", False): return
    if sys.platform == "darwin":
        path = f"/System/Library/Sounds/{sound_name}.aiff"
        if os.path.exists(path): subprocess.Popen(["afplay", path])
        else: QApplication.beep()
    elif sys.platform == "win32":
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except: QApplication.beep()
    else: QApplication.beep()

def speak_text(text):
    if config.get("mute_speech", False) or config.get("quiet_mode", False): return
    if sys.platform == "darwin": subprocess.Popen(["say", text])
    elif sys.platform == "win32":
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except: pass
    else: subprocess.Popen(["espeak", text], stderr=subprocess.DEVNULL)

def set_max_volume():
    if sys.platform == "darwin":
        try: subprocess.Popen(["osascript", "-e", "set volume output volume 100"])
        except: pass