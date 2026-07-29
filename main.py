import sys, sqlite3, json, os, requests, hashlib, cv2, base64, urllib3, time, subprocess, random, re
from datetime import datetime, timedelta
import numpy as np

from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QTextEdit, QWidget, QVBoxLayout, QProgressBar
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QTimer, QUrl, Qt, QTime, QRectF, QByteArray, QBuffer, QIODevice, QPoint, QThread
from PyQt6.QtGui import QImage, QPainter, QPainterPath, QColor, QPen, QBrush, QFont, QPixmap
from PyQt6.QtMultimedia import QSoundEffect
import uuid
import zipfile
import io
import tempfile
import shutil
from PyQt6.QtWidgets import QFileDialog
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


import git
import machineid
from pathlib import Path
import threading
import shutil
import hashlib
# Add this after the imports
import os
from dotenv import load_dotenv




CACHE_DIR = os.path.abspath("shadow_os_cache")






# At the top of main.py, after imports
import os

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
                print(f"✅ GitHub token loaded from .env ({token[:10]}...{token[-4:]})")
            else:
                print("⚠️ GITHUB_TOKEN not found in .env file")
            return True
        except Exception as e:
            print(f"⚠️ Could not load .env: {e}")
            return False
    else:
        print("ℹ️ No .env file found. GitHub sync will use token from config if available.")
        return False

# Load environment variables
load_env_file()

# Get GitHub token
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

class DownloaderThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def run(self):
        dirs = ['js', 'css', 'webfonts', 'img']
        for d in dirs:
            os.makedirs(os.path.join(CACHE_DIR, d), exist_ok=True)

        assets = [
            ("js/react.js", "https://unpkg.com/react@18/umd/react.production.min.js"),
            ("js/react-dom.js", "https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"),
            ("js/babel.js", "https://unpkg.com/@babel/standalone/babel.min.js"),
            ("js/tailwind.js", "https://cdn.tailwindcss.com"),
            ("js/marked.js", "https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
            ("css/all.min.css", "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"),
            ("webfonts/fa-solid-900.woff2", "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2"),
            ("webfonts/fa-regular-400.woff2", "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-regular-400.woff2"),
            ("webfonts/fa-brands-400.woff2", "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-brands-400.woff2"),
            ("img/bg.jpg", "https://images.unsplash.com/photo-1518531933037-91b2f5f229cc?q=80&w=2000&auto=format&fit=crop")
        ]

        for i, (path, url) in enumerate(assets):
            target = os.path.join(CACHE_DIR, path)
            if not os.path.exists(target):
                self.status.emit(f"Caching {path.split('/')[-1]}...")
                try:
                    r = requests.get(url, timeout=15)
                    with open(target, 'wb') as f:
                        f.write(r.content)
                except: pass
            self.progress.emit(int(((i + 1) / len(assets)) * 70))

        self.status.emit("Verifying Fonts...")
        css_path = os.path.join(CACHE_DIR, "css", "fonts.css")
        if not os.path.exists(css_path):
            font_url = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Cinzel:wght@600;800&display=swap"
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}
                r = requests.get(font_url, headers=headers, timeout=15)
                css_content = r.text
                urls = re.findall(r'url\([\'"]?(https://[^\'")]+)[\'"]?\)', css_content)
                for url in set(urls):
                    fname = url.split('/')[-1]
                    wpath = os.path.join(CACHE_DIR, 'webfonts', fname)
                    if not os.path.exists(wpath):
                        self.status.emit(f"Downloading font {fname}...")
                        wr = requests.get(url, headers=headers, timeout=15)
                        with open(wpath, 'wb') as f:
                            f.write(wr.content)
                    css_content = css_content.replace(url, f"../webfonts/{fname}")
                with open(css_path, 'w') as f:
                    f.write(css_content)
            except: pass
            
        self.progress.emit(100)
        self.status.emit("Booting Mind Palace OS...")
        self.finished.emit()

class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(450, 160)
        self.setStyleSheet("background-color: #0a0a0f; color: #e2e8f0; border: 1px solid #1e1e2b; border-radius: 12px;")
        
        lay = QVBoxLayout(self)
        self.lbl = QLabel("Initializing Mind Palace OS Offline Cache...", alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.pbar.setStyleSheet("""
            QProgressBar { border: 1px solid #1e1e2b; border-radius: 6px; text-align: center; background-color: #14141d; color: white; font-weight: bold; } 
            QProgressBar::chunk { background-color: #3b82f6; border-radius: 5px; }
        """)
        lay.addStretch()
        lay.addWidget(self.lbl)
        lay.addSpacing(15)
        lay.addWidget(self.pbar)
        lay.addStretch()

    def start_download(self):
        self.thread = DownloaderThread()
        self.thread.progress.connect(self.pbar.setValue)
        self.thread.status.connect(self.lbl.setText)
        self.thread.finished.connect(self.launch_main)
        self.thread.start()

    def launch_main(self):
        self.main_window = MindPalaceWebOS()
        self.main_window.show()
        self.close()

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
            "deadline_name": "Goal",
            "deadline_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M"),
            "mute_sounds": True,
            "mute_speech": True,
            "sync_enabled": True,
            "sync_repo_url": "https://github.com/alinikkhah2001/Personal_Shadow.git",
            "sync_device_name": "Win",
            "sync_interval": 360,  # seconds (1 hour)
            "sync_local_paths": ['sample'],  # List of folders to sync
            "sync_github_token": "",  # Store securely
            "quiet_mode": False,
            "app_monitoring_enabled": False,  # Enable/disable app monitoring
            "allowed_apps": [],  # List of allowed app names
            "blocked_apps": [],  # List of blocked app names
            "auto_block": False,  # Auto-block disallowed apps
            "target_hours": 5000,
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
        # Create all tables with uuid and modified_at from the start
        self.c.executescript('''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY, 
                name TEXT UNIQUE, 
                target_hours REAL DEFAULT 0,
                uuid TEXT UNIQUE,
                modified_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                id INTEGER PRIMARY KEY, 
                course TEXT, 
                duration INTEGER, 
                actual_duration INTEGER, 
                timestamp TEXT, 
                type TEXT, 
                distractions INTEGER DEFAULT 0, 
                timelapse_path TEXT, 
                distraction_data TEXT,
                uuid TEXT UNIQUE,
                modified_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS cascading_goals (
                id INTEGER PRIMARY KEY, 
                parent_id INTEGER, 
                level TEXT, 
                title TEXT, 
                category TEXT, 
                target_hours REAL DEFAULT 0, 
                logged_hours REAL DEFAULT 0, 
                deadline TEXT,
                uuid TEXT UNIQUE,
                modified_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY, 
                name TEXT UNIQUE, 
                created_at TEXT,
                type TEXT DEFAULT 'Positive',
                uuid TEXT UNIQUE,
                modified_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY, 
                habit_id INTEGER, 
                date TEXT, 
                status INTEGER DEFAULT 0,
                uuid TEXT UNIQUE,
                modified_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY, 
                front TEXT, 
                back TEXT, 
                deck TEXT, 
                next_review TEXT,
                course TEXT,
                folder TEXT DEFAULT 'Uncategorized',
                color TEXT DEFAULT '#3b82f6',
                uuid TEXT UNIQUE,
                modified_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY, 
                title TEXT, 
                questions_json TEXT,
                course TEXT,
                folder TEXT DEFAULT 'Uncategorized',
                color TEXT DEFAULT '#3b82f6',
                uuid TEXT UNIQUE,
                modified_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS focus_queue (
                id INTEGER PRIMARY KEY, 
                title TEXT, 
                duration INTEGER, 
                type TEXT, 
                status TEXT,
                course TEXT,
                uuid TEXT UNIQUE,
                modified_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY, 
                title TEXT, 
                content TEXT, 
                timestamp TEXT,
                course TEXT,
                folder TEXT DEFAULT 'Uncategorized',
                color TEXT DEFAULT '#3b82f6',
                uuid TEXT UNIQUE,
                modified_at TEXT
            );
        ''')
        
        self.conn.commit()

db = DatabaseManager()

def get_color(c_name): 
    if c_name == "Break": return QColor(100,100,100,200)
    if not c_name or c_name == "None": return QColor("#40c463")
    return QColor(f"#{hashlib.md5(c_name.encode()).hexdigest()[:6]}")

def draw_clock_face(p, radius, bg_color):
    shape = config.get("clock_case_shape", "Round")
    bezel = config.get("clock_bezel", "Plain")
    
    if bezel == "GMT (Pepsi)":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(200, 40, 40, 220)))
        p.drawPie(QRectF(-radius-6, -radius-6, (radius+6)*2, (radius+6)*2), 0, 180*16)
        p.setBrush(QBrush(QColor(40, 80, 200, 220)))
        p.drawPie(QRectF(-radius-6, -radius-6, (radius+6)*2, (radius+6)*2), 180*16, 180*16)
    elif bezel == "Diver":
        p.setPen(QPen(QColor(30, 30, 35, 255), 14))
        p.drawEllipse(-radius-2, -radius-2, (radius+2)*2, (radius+2)*2)
    
    p.setBrush(QBrush(bg_color))
    p.setPen(Qt.PenStyle.NoPen)
    
    if shape == "Square": p.drawRect(int(-radius), int(-radius), int(radius*2), int(radius*2))
    elif shape == "Cushion": p.drawRoundedRect(int(-radius), int(-radius), int(radius*2), int(radius*2), int(radius*0.3), int(radius*0.3))
    elif shape == "Tonneau":
        path = QPainterPath()
        path.moveTo(-radius*0.7, -radius); path.lineTo(radius*0.7, -radius)
        path.quadTo(radius, 0, radius*0.7, radius); path.lineTo(-radius*0.7, radius)
        path.quadTo(-radius, 0, -radius*0.7, -radius); p.drawPath(path)
    else: p.drawEllipse(int(-radius), int(-radius), int(radius*2), int(radius*2))
        
    if bezel == "Fluted":
        p.save(); p.setPen(QPen(QColor(200, 200, 200, 80), 3))
        for _ in range(60): p.drawLine(int(radius-8), 0, int(radius), 0); p.rotate(6.0)
        p.restore()
    elif bezel == "Coin-Edge":
        p.save(); p.setPen(QPen(QColor(150, 150, 150, 100), 1))
        for _ in range(120): p.drawLine(int(radius-4), 0, int(radius), 0); p.rotate(3.0)
        p.restore()
    elif bezel == "Diver":
        p.save(); p.setPen(QPen(QColor("white"), 2)); p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        for i in range(0, 60, 10):
            if i == 0:
                p.setBrush(QColor("white"))
                p.drawPolygon([QPoint(0, int(-radius-8)), QPoint(-5, int(-radius)), QPoint(5, int(-radius))])
            else:
                angle = (i * 6 - 90) * np.pi / 180
                p.drawText(QRectF(int((radius+2)*np.cos(angle))-10, int((radius+2)*np.sin(angle))-10, 20, 20), Qt.AlignmentFlag.AlignCenter, str(i))
        p.restore()

def draw_clock_ticks_and_indices(p, radius):
    ticks = config.get("clock_ticks", "Standard")
    indices = config.get("clock_indices", "None")
    
    if ticks != "Clean":
        p.save()
        if ticks == "Railroad":
            p.setPen(QPen(QColor(255,255,255,100), 1))
            p.drawEllipse(int(-radius+15), int(-radius+15), int((radius-15)*2), int((radius-15)*2))
            p.drawEllipse(int(-radius+20), int(-radius+20), int((radius-20)*2), int((radius-20)*2))
            for i in range(60):
                p.drawLine(int(radius-20), 0, int(radius-15), 0); p.rotate(6.0)
        elif ticks == "Crosshair":
            p.setPen(QPen(QColor(255,255,255,50), 1))
            p.drawLine(int(-radius+10), 0, int(radius-10), 0); p.drawLine(0, int(-radius+10), 0, int(radius-10))
            for i in range(60):
                if i % 5 != 0: p.drawLine(int(radius-12), 0, int(radius-10), 0)
                p.rotate(6.0)
        else:
            for i in range(60):
                if i % 5 == 0: p.setPen(QPen(QColor(255,255,255,180), 2)); p.drawLine(int(radius-15), 0, int(radius-10), 0)
                else: p.setPen(QPen(QColor(255,255,255,60), 1)); p.drawLine(int(radius-12), 0, int(radius-10), 0)
                p.rotate(6.0)
        p.restore()
        
    if indices != "None":
        p.save()
        p.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        for i in range(1, 13):
            angle = (i * 30 - 90) * np.pi / 180
            x = (radius - 25) * np.cos(angle); y = (radius - 25) * np.sin(angle)
            if indices == "Baton":
                p.save(); p.translate(x, y); p.rotate(i * 30); p.setBrush(QBrush(QColor("white"))); p.setPen(Qt.PenStyle.NoPen); p.drawRect(-2, -6, 4, 12); p.restore()
            elif indices == "Dot":
                if i % 3 == 0: p.setBrush(QBrush(QColor("white"))); p.drawRect(int(x)-2, int(y)-6, 4, 12)
                else: p.setBrush(QBrush(QColor("white"))); p.drawEllipse(int(x)-4, int(y)-4, 8, 8)
            elif indices == "California":
                p.setPen(QPen(QColor("white")))
                if i == 12: p.save(); p.translate(x, y); p.setBrush(QBrush(QColor("white"))); p.drawPolygon([QPoint(0, -6), QPoint(-6, 6), QPoint(6, 6)]); p.restore()
                elif i in [3, 6, 9]: p.save(); p.translate(x, y); p.rotate(i * 30); p.setBrush(QBrush(QColor("white"))); p.drawRect(-6, -2, 12, 4); p.restore()
                elif i in [10, 11, 1, 2]: p.drawText(QRectF(x-15, y-15, 30, 30), Qt.AlignmentFlag.AlignCenter, ["", "I", "II", "", "", "", "", "", "", "", "X", "XI"][i])
                else: p.drawText(QRectF(x-15, y-15, 30, 30), Qt.AlignmentFlag.AlignCenter, str(i))
            else:
                p.setPen(QPen(QColor("white")))
                text = str(i) if "Arabic" in indices else ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"][i-1]
                p.drawText(QRectF(x-15, y-15, 30, 30), Qt.AlignmentFlag.AlignCenter, text)
        p.restore()

def draw_clock_complications(p, radius):
    comp = config.get("clock_complication", "None")
    if comp == "Date Window":
        p.save(); p.setBrush(QBrush(QColor("white"))); p.setPen(QPen(QColor("black"), 1)); p.drawRect(int(radius - 40), -8, 20, 16); p.setPen(QPen(QColor("black"))); p.setFont(QFont("Arial", 8, QFont.Weight.Bold)); p.drawText(QRectF(radius - 40, -8, 20, 16), Qt.AlignmentFlag.AlignCenter, str(datetime.now().day)); p.restore()
    elif comp == "Small Seconds":
        p.save(); p.translate(0, int(radius - 40)); p.setPen(QPen(QColor(255,255,255,100), 1)); p.drawEllipse(-15, -15, 30, 30)
        for i in range(12): p.drawLine(12, 0, 15, 0); p.rotate(30.0)
        p.restore()

def draw_horological_hand(p, style, length, w, is_hour=False):
    color = p.brush().color()
    length, w = int(length), int(w)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color))
    
    if style == "Spade":
        p.setPen(QPen(color, 2)); p.drawLine(0, 0, 0, -length + 15); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(-6, -length+3, 12, 12)
    elif style == "Breguet":
        p.setPen(QPen(color, 2)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawLine(0, 0, 0, -length + 12); p.drawEllipse(-4, -length+4, 8, 8); p.drawLine(0, -length+4, 0, -length); p.setBrush(QBrush(color)); p.setPen(Qt.PenStyle.NoPen)
    elif style == "Dauphine":
        p.drawConvexPolygon([QPoint(-w*2, 0), QPoint(w*2, 0), QPoint(0, -length)])
    elif style == "Alpha":
        p.drawConvexPolygon([QPoint(-w*2, -10), QPoint(w*2, -10), QPoint(0, -length)]); p.setPen(QPen(color, 2)); p.drawLine(0, 0, 0, -10); p.setPen(Qt.PenStyle.NoPen)
    elif style == "Serpentine":
        p.setPen(QPen(color, 2)); p.setBrush(Qt.BrushStyle.NoBrush); path = QPainterPath(); path.moveTo(0, 0); path.cubicTo(w*4, -length//3, -w*4, -length*2//3, 0, -length); p.strokePath(path, p.pen()); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(color))
    elif style == "Mercedes" and is_hour:
        p.drawRect(-w//2, -length + 20, w, length - 20); p.drawEllipse(-8, -length+4, 16, 16); p.setPen(QPen(QColor(15,15,17), 1)); p.drawLine(0, -length+12, 0, -length+20); p.drawLine(0, -length+12, -6, -length+6); p.drawLine(0, -length+12, 6, -length+6); p.setPen(Qt.PenStyle.NoPen)
    elif style == "Mercedes" and not is_hour:
        p.drawRect(-w//2, -length, w, length)
    elif style == "Sword":
        p.drawConvexPolygon([QPoint(-w//2, 0), QPoint(-w*2, int(-length*0.6)), QPoint(0, -length), QPoint(w*2, int(-length*0.6)), QPoint(w//2, 0)])
    elif style == "Baton":
        p.drawRect(-w, 0, w*2, -length)
    elif style == "Arrow":
        p.drawRect(-w//2, 0, w, -length+15); p.drawConvexPolygon([QPoint(-w*3, -length+15), QPoint(w*3, -length+15), QPoint(0, -length)])
    else: 
        p.drawRect(-w, 0, w*2, -length+5); p.drawConvexPolygon([QPoint(-w, -length+5), QPoint(w, -length+5), QPoint(0, -length)])

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
        
        p.setPen(QPen(QColor(255,255,255,30), 8)); p.drawArc(-70, -70, 140, 140, 0, 360*16)
        p.setPen(QPen(self.ring_color, 8, cap=Qt.PenCapStyle.RoundCap)); p.drawArc(-70, -70, 140, 140, 90*16, int(-self.sp * 360 * 16))
        p.setPen(QPen(QColor(255,255,255,30), 4)); p.drawArc(-55, -55, 110, 110, 0, 360*16)
        p.setPen(QPen(QColor("#40c463"), 4, cap=Qt.PenCapStyle.RoundCap)); p.drawArc(-55, -55, 110, 110, 90*16, int(-self.dp * 360 * 16))
        p.setPen(QColor("white")); p.setFont(QFont("Arial", 16, QFont.Weight.Bold)); p.drawText(QRectF(-90, 20, 180, 40), Qt.AlignmentFlag.AlignCenter, self.txt)
        p.setFont(QFont("Arial", 9)); p.setPen(QColor(200, 200, 200)); p.drawText(QRectF(-90, 45, 180, 30), Qt.AlignmentFlag.AlignCenter, f"{int(self.sm)}/{int(self.pm)}m")
        
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

class VisionTracker(QObject):
    def __init__(self):
        super().__init__()
        self.cap = None
        self.fc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml')

    def start(self):
        # Check if Quiet Mode is enabled
        if config.get("quiet_mode", False):
            print("🔇 Quiet Mode: Webcam disabled")
            return  # Don't start webcam
            
        if not self.cap or not self.cap.isOpened():
            for i in [0, 1]:
                if sys.platform == "win32":
                    tc = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                else:
                    tc = cv2.VideoCapture(i)
                if tc.isOpened():
                    self.cap = tc
                    break

    def stop(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def process_frame(self):
        if not self.cap or not self.cap.isOpened(): return False, None
        ret, frm = self.cap.read()
        if not ret: return False, None
        
        gray = cv2.equalizeHist(cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY))
        faces = self.fc.detectMultiScale(gray, config.get("face_scale_factor", 1.2), config.get("face_min_neighbors", 8), minSize=(100,100))
        
        att = False
        if len(faces) > 0:
            (x,y,w,h) = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)[0]
            cv2.rectangle(frm, (x,y), (x+w,y+h), (0,255,0), 2)
            att = True
            
        _, buffer = cv2.imencode('.jpg', cv2.resize(frm, (480, 360)), [cv2.IMWRITE_JPEG_QUALITY, 60])
        b64 = base64.b64encode(buffer).decode('utf-8')
        return att, b64

class SystemBridge(QObject):
    state_update = pyqtSignal(str)
    video_feed = pyqtSignal(str)
    clock_feed = pyqtSignal(str)
    sync_completed = pyqtSignal(bool, str)  # Add this line

    def __init__(self):
        super().__init__()
        self.ovl = OverlayWidget()
        self.vision = VisionTracker()
        
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
        
        self.snd_dist = QSoundEffect()
        self.snd_dist.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_cam_dist', 'Basso')}.aiff"))
        self.snd_dist.setVolume(1.0)
        self.backup_timer = QTimer()
        self.backup_timer.timeout.connect(self.backup_data)
        self.backup_timer.start(3600 * 1000) 
        # Quiet Mode - disable webcam and sounds if enabled
        self.quiet_mode = config.get("quiet_mode", False)
        if self.quiet_mode:
            self.snd_dist.setVolume(0.0)  # Mute sounds
            print("🔇 Quiet Mode enabled - Webcam and sounds disabled")



                # Add sync manager
        self.sync_manager = SyncManager()
        
        # Sync timer
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.auto_sync)
        if config.get("sync_enabled", False):
            interval = config.get("sync_interval", 3600) * 1000  # convert to ms
            self.sync_timer.start(interval)
        
    def handle_sync_result(self, success, msg):
        """Handle the result of a sync operation"""
        print(f"Sync completed: {success} - {msg}")
        if success:
            print(f"✅ Sync successful: {msg}")
        else:
            print(f"❌ Sync failed: {msg}")
            # Show the error in a more visible way
            QApplication.beep()
    def get_running_processes(self):
        """Get list of running processes with details"""
        processes = []
        
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cpu_percent', 'memory_percent', 'create_time']):
                try:
                    info = proc.info
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'],
                        'exe': info['exe'],
                        'cpu': info['cpu_percent'] or 0,
                        'memory': info['memory_percent'] or 0,
                        'create_time': info['create_time']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            processes.sort(key=lambda x: x['cpu'], reverse=True)
            return processes
        except ImportError:
            # Fallback for when psutil is not installed
            if sys.platform == "win32":
                try:
                    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], 
                                        capture_output=True, text=True)
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        parts = line.strip('"').split('","')
                        if len(parts) >= 2:
                            processes.append({
                                'pid': parts[1],
                                'name': parts[0],
                                'exe': '',
                                'cpu': 0,
                                'memory': 0,
                                'create_time': 0
                            })
                except:
                    pass
            else:
                try:
                    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                    lines = result.stdout.strip().split('\n')[1:]
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 11:
                            processes.append({
                                'pid': parts[1],
                                'name': parts[10] if len(parts) > 10 else parts[0],
                                'exe': '',
                                'cpu': float(parts[2]) if len(parts) > 2 else 0,
                                'memory': float(parts[3]) if len(parts) > 3 else 0,
                                'create_time': 0
                            })
                except:
                    pass
        return processes

    def check_processes_for_distraction(self):
        """Check if any disallowed processes are running"""
        if not config.get("app_monitoring_enabled", False):
            return []
        
        allowed = config.get("allowed_apps", [])
        blocked = config.get("blocked_apps", [])
        
        if not blocked and not allowed:
            return []  # No monitoring configured
        
        running = self.get_running_processes()
        distractions = []
        
        for proc in running:
            proc_name = proc['name'].lower()
            
            # If blocked list exists, check against it
            if blocked:
                for blocked_name in blocked:
                    if blocked_name.lower() in proc_name:
                        distractions.append(proc)
                        break
            # If only allowed list exists, check against it
            elif allowed:
                is_allowed = False
                for allowed_name in allowed:
                    if allowed_name.lower() in proc_name:
                        is_allowed = True
                        break
                if not is_allowed:
                    distractions.append(proc)
        
        return distractions

    def get_app_monitoring_status(self):
        """Get current app monitoring configuration"""
        return {
            'enabled': config.get("app_monitoring_enabled", False),
            'allowed_apps': config.get("allowed_apps", []),
            'blocked_apps': config.get("blocked_apps", []),
            'auto_block': config.get("auto_block", False)
        }

    def set_allowed_apps(self, apps):
        """Set allowed apps list"""
        config.set("allowed_apps", apps)
        return True

    def set_blocked_apps(self, apps):
        """Set blocked apps list"""
        config.set("blocked_apps", apps)
        return True


    def auto_sync(self):
        if config.get("sync_enabled", False):
            self.sync_manager.sync()


    def backup_data(self):
        # Create a backup in the user's home folder
        backup_dir = os.path.join(os.path.expanduser("~"), "MindPalaceBackups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"auto_backup_{timestamp}.zip")
        
        # Remove token from backup
        settings = config.cfg.copy()
        if "sync_github_token" in settings:
            settings["sync_github_token"] = ""
        
        data = {
            "settings": settings,
            "tables": {}
        }
        tables = ["courses", "pomodoro_sessions", "cascading_goals", "habits", "habit_logs",
                "flashcards", "quizzes", "focus_queue", "notes"]
        for table in tables:
            db.c.execute(f"SELECT * FROM {table}")
            columns = [desc[0] for desc in db.c.description]
            rows = [dict(zip(columns, row)) for row in db.c.fetchall()]
            data["tables"][table] = rows
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("data.json", json.dumps(data, indent=2))
        with open(backup_path, 'wb') as f:
            f.write(zip_buffer.getvalue())




    def play_sound(self):
        if config.get("mute_sounds", False):
            return
        if self.snd_dist and self.snd_dist.isLoaded():
            self.snd_dist.play()
        else:
            QApplication.beep()

    def speak(self, text):
        if config.get("mute_speech", False):
            return
        if sys.platform == "darwin":
            subprocess.Popen(["say", text])
        elif sys.platform == "win32":
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except ImportError:
                print("Speech unavailable – install pyttsx3")
        else:  # Linux
            subprocess.Popen(["espeak", text], stderr=subprocess.DEVNULL)









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
                "metrics_data": {
                    "tdy_study": tdy_study / 60.0,
                    "ydy_study": ydy_study / 60.0,
                    "tdy_dist": tdy_dist,
                    "ydy_dist": ydy_dist,
                    "hourly_vol": vols,
                    "total_study_hours": tdy_study / 60.0  # Add this line
                }
            })










        elif action == "save_settings":
            new_settings = req.get("data", {})
            for k, v in new_settings.items():
                config.set(k, v)
            self.snd_dist.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_cam_dist', 'Basso')}.aiff"))
            return json.dumps({"status": "saved"})

        elif action == "get_git_status":
            try:
                repo_path = os.path.join(os.path.expanduser("~"), ".mindpalace_sync_repo")
                if os.path.exists(repo_path):
                    repo = git.Repo(repo_path)
                    # Check if remote exists
                    try:
                        remote = repo.remotes.origin
                        # Check if we can fetch
                        remote.fetch(dry_run=True)
                        status = "connected"
                    except:
                        status = "error"
                    last_commit = repo.head.commit.committed_datetime.isoformat() if repo.head.is_valid() else None
                    return json.dumps({
                        "status": status,
                        "last_sync": last_commit,
                        "branch": repo.active_branch.name if repo.head.is_valid() else "none"
                    })
                else:
                    return json.dumps({"status": "not_initialized", "last_sync": None})
            except Exception as e:
                return json.dumps({"status": "error", "error": str(e)})

        elif action == "open_folder_dialog":
            parent = QApplication.activeWindow()
            folder_path = QFileDialog.getExistingDirectory(
                parent, "Select Folder to Sync", "",
                QFileDialog.Option.ShowDirsOnly
            )
            return json.dumps({"path": folder_path if folder_path else ""})

        elif action == "sync_now":
            # Run sync in a separate thread to prevent UI freeze
            import threading
            import traceback
            
            def sync_thread():
                try:
                    success, msg = self.sync_manager.sync()
                    # Emit result back to the UI
                    self.sync_completed.emit(success, msg if msg else "Sync completed" if success else "Sync failed - unknown error")
                except Exception as e:
                    error_msg = f"Sync error: {str(e)}\n{traceback.format_exc()}"
                    print(error_msg)
                    self.sync_completed.emit(False, f"Error: {str(e)}")
            
            # Make sure the signal is connected
            try:
                self.sync_completed.disconnect()
            except:
                pass
            self.sync_completed.connect(self.handle_sync_result)
            
            thread = threading.Thread(target=sync_thread)
            thread.daemon = True
            thread.start()
            
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
            return json.dumps({"folders": config.get("sync_local_paths", [])})

        elif action == "get_sync_status":
            return json.dumps({
                "enabled": config.get("sync_enabled", False),
                "device_id": self.sync_manager.device_id,
                "repo_url": config.get("sync_repo_url", ""),
                "interval": config.get("sync_interval", 3600),
                "has_token": bool(GITHUB_TOKEN)  # Use the global variable
            })

        elif action == "set_quiet_mode":
            enabled = req.get("enabled", False)
            config.set("quiet_mode", enabled)
            self.quiet_mode = enabled
            if enabled:
                self.snd_dist.setVolume(0.0)
                self.vision.stop()
                self.vision.cap = None
                print("🔇 Quiet Mode enabled")
            else:
                self.snd_dist.setVolume(1.0)
                print("🔊 Quiet Mode disabled")
            return json.dumps({"status": "ok", "quiet_mode": enabled})

        elif action == "reset_data":
            db.c.execute("DELETE FROM pomodoro_sessions")
            db.c.execute("DELETE FROM habit_logs")
            db.c.execute("DELETE FROM focus_queue")
            db.conn.commit()
            return json.dumps({"status": "cleared"})

        elif action == "open_file_dialog":
            parent = QApplication.activeWindow()
            file_path, _ = QFileDialog.getOpenFileName(
                parent, "Select a file", "",
                "All Files (*.*);;JSON (*.json);;Images (*.png *.jpg)"
            )
            return json.dumps({"path": file_path if file_path else ""})



        elif action == "get_processes":
            processes = self.get_running_processes()
            # Return only the process name and pid for UI
            process_list = [{'name': p['name'], 'pid': p['pid']} for p in processes[:50]]
            return json.dumps({"processes": process_list})

        elif action == "get_app_monitoring_status":
            return json.dumps(self.get_app_monitoring_status())

        elif action == "set_allowed_apps":
            apps = req.get("apps", [])
            self.set_allowed_apps(apps)
            return json.dumps({"status": "ok", "allowed_apps": apps})

        elif action == "set_blocked_apps":
            apps = req.get("apps", [])
            self.set_blocked_apps(apps)
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
            distractions = self.check_processes_for_distraction()
            return json.dumps({"distractions": distractions})



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
            
            # Debug print
            print(f"✅ Timer started: {self.current_course}, {self.total_time//60}m")
            print(f"   Timer running: {self.is_running}, time_left: {self.time_left}")
            
            return json.dumps({"status": "started"})

        elif action == "stop_timer":
            self.is_running = False
            self.timer.stop()
            self.ovl.hide()
            self.vision.stop()
            db.c.execute("""
                INSERT INTO pomodoro_sessions (uuid, modified_at, course, duration, actual_duration, timestamp, type, distractions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uuid.uuid4().hex,
                datetime.now().isoformat(),
                self.current_course,
                self.total_time // 60,
                (self.total_time - self.time_left) // 60,
                datetime.now().isoformat(),
                'Work',
                self.distractions
            ))
            db.conn.commit()
            self.push_state()
            return json.dumps({"status": "stopped"})

        elif action == "manage_queue":
            sub = req.get("sub")
            if sub == "add":
                db.c.execute("""
                    INSERT INTO focus_queue (uuid, modified_at, title, duration, type, status, course)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    uuid.uuid4().hex,
                    datetime.now().isoformat(),
                    req.get("title"),
                    int(req.get("duration")),
                    req.get("type"),
                    'pending',
                    req.get("course")
                ))
            elif sub == "edit":
                db.c.execute("UPDATE focus_queue SET title=?, duration=?, type=?, course=?, modified_at=? WHERE id=?",
                             (req.get("title"), int(req.get("duration")), req.get("type"), req.get("course"), datetime.now().isoformat(), req.get("id")))
            elif sub == "delete":
                db.c.execute("DELETE FROM focus_queue WHERE id=?", (req.get("id"),))
            elif sub == "clear":
                db.c.execute("DELETE FROM focus_queue")
            db.conn.commit()
            return json.dumps({"queue": [{"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]} for r in db.c.execute("SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id").fetchall()]})

        elif action == "manage_habit":
            sub = req.get("sub")
            if sub == "add":
                db.c.execute("""
                    INSERT INTO habits (uuid, modified_at, name, type, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    uuid.uuid4().hex,
                    datetime.now().isoformat(),
                    req.get("name"),
                    req.get("type", "Positive"),
                    datetime.now().isoformat()
                ))
            elif sub == "edit":
                db.c.execute("UPDATE habits SET name=?, type=?, modified_at=? WHERE id=?", 
                            (req.get("name"), req.get("type"), datetime.now().isoformat(), req.get("id")))
            elif sub == "delete":
                db.c.execute("DELETE FROM habits WHERE id=?", (req.get("id"),))
                # Also delete associated logs
                db.c.execute("DELETE FROM habit_logs WHERE habit_id=?", (req.get("id"),))
            elif sub == "toggle_log":
                hid = req.get("habit_id")
                dt = req.get("date")
                st = req.get("status", 1)  # Default to 1 if not provided
                
                print(f"🔄 Toggling log: habit_id={hid}, date={dt}, status={st}")
                
                # Check if log exists
                db.c.execute("SELECT id FROM habit_logs WHERE habit_id=? AND date=?", (hid, dt))
                existing = db.c.fetchone()
                
                if existing:
                    # Update existing
                    db.c.execute("UPDATE habit_logs SET status=?, modified_at=? WHERE id=?", 
                                (st, datetime.now().isoformat(), existing[0]))
                    print(f"✅ Updated habit log for {hid} on {dt} to {st}")
                else:
                    # Insert new
                    db.c.execute("""
                        INSERT INTO habit_logs (uuid, modified_at, habit_id, date, status)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        uuid.uuid4().hex,
                        datetime.now().isoformat(),
                        hid,
                        dt,
                        st
                    ))
                    print(f"✅ Created habit log for {hid} on {dt} with status {st}")
            
            db.conn.commit()
            
            # Fetch updated data
            habits = [{"id": r[0], "name": r[1], "type": r[2]} for r in db.c.execute("SELECT id, name, type FROM habits").fetchall()]
            habit_logs = [{"habit_id": r[0], "date": r[1], "status": r[2]} for r in db.c.execute("SELECT habit_id, date, status FROM habit_logs").fetchall()]
            
            print(f"📊 Current habits: {habits}")
            print(f"📊 Current habit logs: {habit_logs}")
            
            return json.dumps({
                "habits": habits,
                "habit_logs": habit_logs
            })

        elif action == "manage_note":
            sub = req.get("sub")
            if sub == "save":
                if req.get("id"):
                    db.c.execute("UPDATE notes SET title=?, content=?, course=?, folder=?, color=?, modified_at=? WHERE id=?",
                                 (req.get("title"), req.get("content"), req.get("course"), req.get("folder"), req.get("color"), datetime.now().isoformat(), req.get("id")))
                else:
                    db.c.execute("""
                        INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        uuid.uuid4().hex,
                        datetime.now().isoformat(),
                        req.get("title"),
                        req.get("content"),
                        datetime.now().isoformat(),
                        req.get("course"),
                        req.get("folder"),
                        req.get("color")
                    ))
            elif sub == "delete":
                db.c.execute("DELETE FROM notes WHERE id=?", (req.get("id"),))
            db.conn.commit()
            return json.dumps({"notes": [{"id": r[0], "title": r[1], "content": r[2], "course": r[3], "folder": r[4], "color": r[5]} for r in db.c.execute("SELECT id, title, content, course, folder, color FROM notes ORDER BY id DESC").fetchall()]})

        elif action == "manage_flashcard":
            sub = req.get("sub")
            if sub == "add":
                db.c.execute("""
                    INSERT INTO flashcards (uuid, modified_at, front, back, deck, course, folder, color)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    uuid.uuid4().hex,
                    datetime.now().isoformat(),
                    req.get("front"),
                    req.get("back"),
                    req.get("deck"),
                    req.get("course"),
                    req.get("folder"),
                    req.get("color")
                ))
            elif sub == "delete":
                db.c.execute("DELETE FROM flashcards WHERE id=?", (req.get("id"),))
            db.conn.commit()
            return json.dumps({"flashcards": [{"id": r[0], "front": r[1], "back": r[2], "deck": r[3], "course": r[4], "folder": r[5], "color": r[6]} for r in db.c.execute("SELECT id, front, back, deck, course, folder, color FROM flashcards").fetchall()]})

        elif action == "manage_quiz":
            sub = req.get("sub")
            if sub == "add":
                db.c.execute("""
                    INSERT INTO quizzes (uuid, modified_at, title, questions_json, course, folder, color)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    uuid.uuid4().hex,
                    datetime.now().isoformat(),
                    req.get("title"),
                    req.get("json"),
                    req.get("course"),
                    req.get("folder"),
                    req.get("color")
                ))
            elif sub == "delete":
                db.c.execute("DELETE FROM quizzes WHERE id=?", (req.get("id"),))
            db.conn.commit()
            return json.dumps({"quizzes": [{"id": r[0], "title": r[1], "json": r[2], "course": r[3], "folder": r[4], "color": r[5]} for r in db.c.execute("SELECT id, title, questions_json, course, folder, color FROM quizzes").fetchall()]})

        elif action == "manage_goal":
            sub = req.get("sub")
            if sub == "add":
                db.c.execute("""
                    INSERT INTO cascading_goals (uuid, modified_at, parent_id, title, target_hours, deadline)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    uuid.uuid4().hex,
                    datetime.now().isoformat(),
                    req.get("parent_id"),
                    req.get("title"),
                    float(req.get("target_hours") or 0),
                    req.get("deadline")
                ))
            elif sub == "delete":
                db.c.execute("DELETE FROM cascading_goals WHERE id=?", (req.get("id"),))
            db.conn.commit()
            return json.dumps({"goals": self.get_goals_tree(), "flat_goals": self.get_flat_goals()})

        elif action == "export_data":
            parent = QApplication.activeWindow()
            file_path, _ = QFileDialog.getSaveFileName(
                parent, "Export Data", "mindpalace_backup.zip", "ZIP (*.zip)"
            )
            if not file_path:
                return json.dumps({"error": "Export cancelled"})
            data = {
                "settings": config.cfg,
                "tables": {}
            }
            tables = ["courses", "pomodoro_sessions", "cascading_goals", "habits", "habit_logs",
                    "flashcards", "quizzes", "focus_queue", "notes"]
            for table in tables:
                db.c.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in db.c.description]
                rows = [dict(zip(columns, row)) for row in db.c.fetchall()]
                data["tables"][table] = rows
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.writestr("data.json", json.dumps(data, indent=2))
            with open(file_path, 'wb') as f:
                f.write(zip_buffer.getvalue())
            return json.dumps({"status": "exported", "path": file_path})

        elif action == "import_data":
            parent = QApplication.activeWindow()
            file_path, _ = QFileDialog.getOpenFileName(
                parent, "Import Data", "", "ZIP (*.zip)"
            )
            if not file_path:
                return json.dumps({"error": "Import cancelled"})
            with zipfile.ZipFile(file_path, 'r') as zipf:
                with zipf.open("data.json") as f:
                    data = json.load(f)
            tables_data = data.get("tables", {})
            order = ["courses", "habits", "cascading_goals", "flashcards", "quizzes",
                    "notes", "focus_queue", "habit_logs", "pomodoro_sessions"]
            for table in order:
                if table not in tables_data:
                    continue
                rows = tables_data[table]
                for row in rows:
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
                            set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k != "id"])
                            values = [row[k] for k in row.keys() if k != "id"] + [existing_id]
                            db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                    else:
                        row.pop("id", None)
                        cols = ", ".join(row.keys())
                        placeholders = ", ".join(["?"] * len(row))
                        db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
            db.conn.commit()
            return self.request(json.dumps({"action": "init"}))

        return json.dumps({"error": "Unknown action"})



    






    def emit_clock(self):
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
        b64 = base64.b64encode(buf.data()).decode('utf-8')
        self.clock_feed.emit(f"data:image/png;base64,{b64}")

 
    def tick(self):
        if not self.is_running: 
            return
        
        # Check webcam if not in quiet mode
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
                if self.distractions % 5 == 0 and not config.get("quiet_mode", False):
                    self.play_sound()
        
        # Check running processes for distractions
        if config.get("app_monitoring_enabled", False):
            app_distractions = self.check_processes_for_distraction()
            if app_distractions:
                # Mark as distraction (App mode)
                if dist_mode == "None":
                    dist_mode = "App"
                    self.distractions += 1
                    self.distraction_markers.append(100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0)
                
                # Log the distracting apps
                for proc in app_distractions[:3]:  # Log up to 3
                    print(f"⚠️ Distracting app detected: {proc['name']} (PID: {proc['pid']})")
                
                # Auto-block if enabled
                if config.get("auto_block", False):
                    self.kill_processes(app_distractions)

        if self.time_left > 0:
            self.time_left -= 1
        else:
            self.is_running = False
            self.timer.stop()
            self.ovl.hide()
            self.vision.stop()
            if not config.get("quiet_mode", False):
                self.speak(config.get("speech_comp", "Session Complete."))
        
        self.push_state(dist_mode)

    def kill_processes(self, processes):
        """Kill distracting processes (cross-platform)"""
        try:
            import psutil
            for proc in processes[:3]:  # Kill up to 3 processes
                try:
                    p = psutil.Process(proc['pid'])
                    p.terminate()
                    print(f"🔫 Killed process: {proc['name']} (PID: {proc['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except:
            pass

    def push_state(self, dist_mode="None"):
        mins, secs = divmod(self.time_left, 60)
        time_str = f"{mins:02d}:{secs:02d}"
        pct = 100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0
        
        self.ovl.update_state(time_str, pct, (self.total_time-self.time_left)//60, self.total_time//60, self.current_course, dist_mode)
        
        state = {
            "is_running": self.is_running,
            "time_str": time_str,
            "progress": pct,
            "distractions": self.distractions,
            "distraction_markers": self.distraction_markers,
            "course": self.current_course
        }
        self.state_update.emit(json.dumps(state))

    def get_goals_tree(self):
        db.c.execute("SELECT id, parent_id, title, target_hours, deadline FROM cascading_goals")
        rows = db.c.fetchall()
        return [{"id": r[0], "parent_id": r[1], "title": r[2], "target_hours": r[3], "deadline": r[4]} for r in rows]

    def get_flat_goals(self):
        db.c.execute("SELECT id, parent_id, title FROM cascading_goals")
        rows = db.c.fetchall()
        tree = {r[0]: {"parent": r[1], "title": r[2]} for r in rows}
        
        paths = []
        for gid, data in tree.items():
            path = [data["title"]]
            curr = data["parent"]
            while curr in tree:
                path.insert(0, tree[curr]["title"])
                curr = tree[curr]["parent"]
            paths.append(" > ".join(path))
        return sorted(paths)
        
    def get_heatmap_data(self):
        weeks = 28
        matrix = [[0]*7 for _ in range(weeks)]
        td = datetime.now().date()
        db.c.execute("SELECT date(timestamp), sum(duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY date(timestamp)")
        history = {r[0]: r[1]/60.0 for r in db.c.fetchall()}
        
        for w in range(weeks):
            for d in range(7):
                target_date = (td - timedelta(days=(weeks-w-1)*7 + (6-d))).isoformat()
                hrs = history.get(target_date, 0)
                intensity = 0
                if hrs > 0: intensity = 1
                if hrs > 2: intensity = 2
                if hrs > 4: intensity = 3
                if hrs > 6: intensity = 4
                matrix[w][d] = intensity
        return matrix





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
        
        # Get token from environment variable FIRST
        self.token = os.getenv('GITHUB_TOKEN', '')
        # If not in env, fallback to config (but don't save to config)
        if not self.token:
            self.token = config.get("sync_github_token", "")
        
        self.repo_url = config.get("sync_repo_url", "")
    def safe_insert_or_update(self, table, row):
        """Safely insert or update a record handling UNIQUE constraints"""
        uid = row.get("uuid")
        if not uid:
            uid = uuid.uuid4().hex
            row["uuid"] = uid
        
        # Check by UUID first
        db.c.execute(f"SELECT id FROM {table} WHERE uuid = ?", (uid,))
        existing = db.c.fetchone()
        
        if existing:
            # Update existing
            existing_id = existing[0]
            set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid"]])
            values = [row[k] for k in row.keys() if k not in ["id", "uuid"]] + [existing_id]
            try:
                db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                return True, "updated"
            except sqlite3.IntegrityError as e:
                # If UUID update fails, try finding by name for habits
                if table == "habits" and "name" in row:
                    name = row.get("name")
                    db.c.execute(f"SELECT id FROM {table} WHERE name = ? AND uuid != ?", (name, uid))
                    by_name = db.c.fetchone()
                    if by_name:
                        # Update by name instead
                        existing_id = by_name[0]
                        set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid", "name"]])
                        values = [row[k] for k in row.keys() if k not in ["id", "uuid", "name"]] + [existing_id]
                        db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                        return True, "updated_by_name"
                return False, str(e)
        else:
            # Insert new
            row.pop("id", None)
            cols = ", ".join(row.keys())
            placeholders = ", ".join(["?"] * len(row))
            try:
                db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
                return True, "inserted"
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint" in str(e) and table == "habits":
                    # Try to find by name and update
                    name = row.get("name")
                    if name:
                        db.c.execute(f"SELECT id FROM {table} WHERE name = ?", (name,))
                        by_name = db.c.fetchone()
                        if by_name:
                            existing_id = by_name[0]
                            set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid", "name"]])
                            values = [row[k] for k in row.keys() if k not in ["id", "uuid", "name"]] + [existing_id]
                            db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                            return True, "updated_by_name_after_fail"
                return False, str(e)
    def get_device_id(self):
        """Get a consistent device ID using multiple strategies"""
        try:
            # Try py-machineid first
            return machineid.id()
        except:
            try:
                # Fallback: generate from system info
                import platform
                import socket
                data = f"{platform.node()}-{platform.processor()}-{platform.machine()}"
                return hashlib.sha256(data.encode()).hexdigest()[:16]
            except:
                # Ultimate fallback: generate and save locally
                id_file = os.path.join(os.path.expanduser("~"), ".mindpalace_device_id")
                if os.path.exists(id_file):
                    with open(id_file, 'r') as f:
                        return f.read().strip()
                else:
                    import uuid
                    device_id = str(uuid.uuid4())
                    with open(id_file, 'w') as f:
                        f.write(device_id)
                    return device_id
    
    def setup_repo(self):
        """Initialize or clone the sync repository"""
        if not self.repo_url:
            return False, "No repository URL configured"
        
        # Ensure URL has https:// prefix
        url = self.repo_url
        if not url.startswith('https://') and not url.startswith('http://'):
            url = 'https://' + url
            print(f"🔧 Fixed URL: {url}")
        
        # Embed token in URL if provided
        if self.token:
            url = url.replace("https://", f"https://{self.token}@")
            
        if os.path.exists(self.repo_path):
            try:
                # Try to use GitPython first
                self.repo = git.Repo(self.repo_path)
                
                # Check if it's valid by using subprocess instead of GitPython's fetch
                import subprocess
                result = subprocess.run(['git', 'fetch', '--dry-run'], cwd=self.repo_path, capture_output=True, text=True)
                if result.returncode == 0:
                    return True, "Repository ready"
                else:
                    # Try git pull
                    result = subprocess.run(['git', 'pull'], cwd=self.repo_path, capture_output=True, text=True)
                    if result.returncode == 0:
                        return True, "Repository pulled successfully"
                    else:
                        raise Exception(result.stderr)
            except Exception as e:
                print(f"Error with repo: {e}")
                # If corrupt, try re-cloning
                import shutil
                shutil.rmtree(self.repo_path)
                return self.setup_repo()
        else:
            try:
                os.makedirs(os.path.dirname(self.repo_path), exist_ok=True)
                # Use subprocess to clone
                import subprocess
                print(f"🔄 Cloning from: {url[:50]}...")  # Show first 50 chars (hides token)
                result = subprocess.run(['git', 'clone', url, self.repo_path], capture_output=True, text=True)
                if result.returncode == 0:
                    self.repo = git.Repo(self.repo_path)
                    
                    # Create .gitignore to ONLY sync data files (NOT code)
                    gitignore_path = os.path.join(self.repo_path, '.gitignore')
                    with open(gitignore_path, 'w') as f:
                        f.write('''
    # ============================================
    # DATA-ONLY SYNC REPOSITORY
    # This repo should ONLY contain data files
    # Code is stored in a separate repository
    # ============================================

    # Ignore everything except sync_data.json and files/
    *
    !sync_data.json
    !files/
    !files/**

    # Ignore IDE files
    .idea/
    .vscode/
    *.swp
    *.swo

    # Ignore OS files
    .DS_Store
    Thumbs.db

    # Ignore temporary files
    *.tmp
    *.temp
    *.log
    ''')
                    
                    # Add and commit .gitignore
                    subprocess.run(['git', 'add', '.gitignore'], cwd=self.repo_path, capture_output=True, text=True)
                    subprocess.run(['git', 'commit', '-m', 'Add .gitignore for data-only sync'], cwd=self.repo_path, capture_output=True, text=True)
                    
                    # Push the .gitignore
                    result = subprocess.run(['git', 'push', '--set-upstream', 'origin', 'main'], cwd=self.repo_path, capture_output=True, text=True)
                    if result.returncode != 0:
                        # Try with master branch if main fails
                        result = subprocess.run(['git', 'push', '--set-upstream', 'origin', 'master'], cwd=self.repo_path, capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"⚠️ Could not push .gitignore: {result.stderr}")
                    
                    return True, "Repository cloned successfully with data-only config"
                else:
                    error_msg = result.stderr
                    print(f"❌ Clone failed: {error_msg}")
                    return False, f"Clone failed: {error_msg}"
            except Exception as e:
                return False, f"Failed to clone: {str(e)}"
                
    def sync(self):
        """Main sync method - push and pull all data"""
        if not config.get("sync_enabled", False):
            return False, "Sync is disabled in settings"
            
        self.sync_progress.emit("Starting sync...")
        
        # 1. Ensure repo is ready
        success, msg = self.setup_repo()
        if not success:
            self.sync_completed.emit(False, msg)
            return False, msg
            
        self.sync_progress.emit(msg)
        
        # 2. Pull latest changes from GitHub
        self.sync_progress.emit("Pulling latest data from GitHub...")
        try:
            import subprocess
            result = subprocess.run(['git', 'pull', '--rebase'], cwd=self.repo_path, capture_output=True, text=True)
            if result.returncode != 0:
                # If rebase fails, try a normal pull
                self.sync_progress.emit("Rebase failed, trying normal pull...")
                result = subprocess.run(['git', 'pull'], cwd=self.repo_path, capture_output=True, text=True)
                if result.returncode != 0:
                    error_msg = f"Pull failed: {result.stderr}"
                    self.sync_completed.emit(False, error_msg)
                    return False, error_msg
        except Exception as e:
            error_msg = f"Pull failed: {str(e)}"
            self.sync_completed.emit(False, error_msg)
            return False, error_msg
        
        # 3. Merge remote data into local DB
        self.sync_progress.emit("Merging remote data...")
        remote_data_path = os.path.join(self.repo_path, self.sync_data_file)
        if os.path.exists(remote_data_path):
            try:
                with open(remote_data_path, 'r') as f:
                    remote_data = json.load(f)
                self.merge_remote_data(remote_data)
            except Exception as e:
                error_msg = f"Merge failed: {str(e)}"
                self.sync_completed.emit(False, error_msg)
                return False, error_msg
        
        # 4. Export local data to the repo
        self.sync_progress.emit("Exporting local data...")
        try:
            local_data = self.export_local_data()
            with open(os.path.join(self.repo_path, self.sync_data_file), 'w') as f:
                json.dump(local_data, f, indent=2)
        except Exception as e:
            error_msg = f"Export failed: {str(e)}"
            self.sync_completed.emit(False, error_msg)
            return False, error_msg
        
        # 5. Handle file sharing
        self.sync_progress.emit("Syncing files...")
        try:
            self.sync_files()
        except Exception as e:
            error_msg = f"File sync failed: {str(e)}"
            self.sync_completed.emit(False, error_msg)
            return False, error_msg
        
        # 6. Commit and push
        self.sync_progress.emit("Pushing to GitHub...")
        try:
            import subprocess
            result = subprocess.run(['git', 'status', '--porcelain'], cwd=self.repo_path, capture_output=True, text=True)
            if result.stdout.strip():
                subprocess.run(['git', 'add', '-A'], cwd=self.repo_path, capture_output=True, text=True)
                commit_msg = f"Sync from {self.device_id} at {datetime.now().isoformat()}"
                subprocess.run(['git', 'commit', '-m', commit_msg], cwd=self.repo_path, capture_output=True, text=True)
                result = subprocess.run(['git', 'push'], cwd=self.repo_path, capture_output=True, text=True)
                if result.returncode != 0:
                    self.sync_progress.emit("Push failed, retrying after pull...")
                    subprocess.run(['git', 'pull', '--rebase'], cwd=self.repo_path, capture_output=True, text=True)
                    result = subprocess.run(['git', 'push'], cwd=self.repo_path, capture_output=True, text=True)
                    if result.returncode != 0:
                        error_msg = f"Push failed: {result.stderr}"
                        self.sync_completed.emit(False, error_msg)
                        return False, error_msg
            else:
                self.sync_progress.emit("No changes to sync")
        except Exception as e:
            error_msg = f"Push failed: {str(e)}"
            self.sync_completed.emit(False, error_msg)
            return False, error_msg
        
        self.sync_completed.emit(True, "Sync completed successfully")
        self.sync_progress.emit("Sync completed!")
        return True, "Sync completed successfully"
    def merge_remote_data(self, remote_data):
        """Merge remote data into local database - MERGE, NOT REPLACE"""
        tables = remote_data.get("tables", {})
        order = ["courses", "habits", "cascading_goals", "flashcards", "quizzes",
                "notes", "focus_queue", "habit_logs", "pomodoro_sessions"]
        
        for table in order:
            if table not in tables:
                continue
            rows = tables[table]
            for row in rows:
                uid = row.get("uuid")
                if not uid:
                    uid = uuid.uuid4().hex
                    row["uuid"] = uid
                
                # Check if record exists locally by UUID
                db.c.execute(f"SELECT id, modified_at FROM {table} WHERE uuid = ?", (uid,))
                existing = db.c.fetchone()
                
                if existing:
                    existing_id, existing_mod = existing
                    incoming_mod = row.get("modified_at", "")
                    # Only update if incoming is newer OR if local doesn't have modified_at
                    if not existing_mod or (incoming_mod and incoming_mod > existing_mod):
                        # Update ALL fields except id and uuid
                        set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid"]])
                        values = [row[k] for k in row.keys() if k not in ["id", "uuid"]] + [existing_id]
                        try:
                            db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                            print(f"🔄 Updated {table} record {uid}")
                        except sqlite3.IntegrityError as e:
                            # Handle UNIQUE constraint violations
                            if "UNIQUE constraint" in str(e):
                                print(f"⚠️ Skipping {table} record {uid} - {e}")
                            else:
                                raise
                    else:
                        print(f"⏭️ Skipped {table} record {uid} (local is newer)")
                else:
                    # Insert new record - handle potential UNIQUE violations
                    row.pop("id", None)
                    cols = ", ".join(row.keys())
                    placeholders = ", ".join(["?"] * len(row))
                    try:
                        db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
                        print(f"➕ Added new {table} record {uid}")
                    except sqlite3.IntegrityError as e:
                        if "UNIQUE constraint" in str(e):
                            print(f"⚠️ UNIQUE constraint violation for {table} - trying to handle gracefully")
                            
                            # Handle specific tables with UNIQUE constraints
                            if table == "habits":
                                # Try to find the habit by name and update it
                                name = row.get("name")
                                if name:
                                    db.c.execute(f"SELECT id, modified_at FROM {table} WHERE name = ?", (name,))
                                    existing = db.c.fetchone()
                                    if existing:
                                        existing_id, existing_mod = existing
                                        incoming_mod = row.get("modified_at", "")
                                        if not existing_mod or (incoming_mod and incoming_mod > existing_mod):
                                            # Update all fields except id, uuid, and name (keep the name as is)
                                            set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid", "name"]])
                                            values = [row[k] for k in row.keys() if k not in ["id", "uuid", "name"]] + [existing_id]
                                            db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                                            print(f"🔄 Updated existing habit by name: {name}")
                                        else:
                                            print(f"⏭️ Skipped habit {name} (local is newer)")
                                    else:
                                        # If not found by name, try by uuid with a different approach
                                        db.c.execute(f"SELECT id, modified_at FROM {table} WHERE uuid = ?", (uid,))
                                        existing = db.c.fetchone()
                                        if existing:
                                            existing_id, existing_mod = existing
                                            incoming_mod = row.get("modified_at", "")
                                            if not existing_mod or (incoming_mod and incoming_mod > existing_mod):
                                                set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid"]])
                                                values = [row[k] for k in row.keys() if k not in ["id", "uuid"]] + [existing_id]
                                                db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                                                print(f"🔄 Updated existing habit by uuid: {uid}")
                            elif table == "courses":
                                # Handle duplicate course names
                                name = row.get("name")
                                if name:
                                    db.c.execute(f"SELECT id, modified_at FROM {table} WHERE name = ?", (name,))
                                    existing = db.c.fetchone()
                                    if existing:
                                        existing_id, existing_mod = existing
                                        incoming_mod = row.get("modified_at", "")
                                        if not existing_mod or (incoming_mod and incoming_mod > existing_mod):
                                            set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid", "name"]])
                                            values = [row[k] for k in row.keys() if k not in ["id", "uuid", "name"]] + [existing_id]
                                            db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                                            print(f"🔄 Updated existing course by name: {name}")
                            else:
                                # Generic fallback: try to find by name or title
                                name_key = "name" if "name" in row else "title" if "title" in row else None
                                if name_key:
                                    value = row.get(name_key)
                                    if value:
                                        db.c.execute(f"SELECT id, modified_at FROM {table} WHERE {name_key} = ?", (value,))
                                        existing = db.c.fetchone()
                                        if existing:
                                            existing_id, existing_mod = existing
                                            incoming_mod = row.get("modified_at", "")
                                            if not existing_mod or (incoming_mod and incoming_mod > existing_mod):
                                                set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid", name_key]])
                                                values = [row[k] for k in row.keys() if k not in ["id", "uuid", name_key]] + [existing_id]
                                                db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                                                print(f"🔄 Updated existing {table} by {name_key}: {value}")
                        else:
                            raise
        
        db.conn.commit()
        print("✅ Merge completed successfully")
    
    def export_local_data(self):
        """Export local data without sensitive info"""
        # Get settings but remove any sensitive data
        settings = config.cfg.copy()
        settings.pop("sync_github_token", None)  # Remove token
        
        data = {
            "device_id": self.device_id,
            "last_sync": datetime.now().isoformat(),
            "settings": settings,
            "tables": {}
        }
        tables = ["courses", "pomodoro_sessions", "cascading_goals", "habits", "habit_logs",
                "flashcards", "quizzes", "focus_queue", "notes"]
        for table in tables:
            db.c.execute(f"SELECT * FROM {table}")
            columns = [desc[0] for desc in db.c.description]
            rows = [dict(zip(columns, row)) for row in db.c.fetchall()]
            data["tables"][table] = rows
        return data
    
    def sync_files(self):
        """Sync files from mapped folders"""
        local_paths = config.get("sync_local_paths", [])
        if not local_paths:
            return
            
        device_files_dir = os.path.join(self.repo_path, self.files_dir, self.device_id)
        os.makedirs(device_files_dir, exist_ok=True)
        
        for local_path in local_paths:
            if not os.path.exists(local_path):
                continue
            # Copy files to the repo
            for item in os.listdir(local_path):
                src = os.path.join(local_path, item)
                dst = os.path.join(device_files_dir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                elif os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
    
    def map_folder(self, local_path):
        """Add a folder to be monitored and synced"""
        paths = config.get("sync_local_paths", [])
        if local_path not in paths:
            paths.append(local_path)
            config.set("sync_local_paths", paths)
    
    def unmap_folder(self, local_path):
        """Remove a folder from sync"""
        paths = config.get("sync_local_paths", [])
        if local_path in paths:
            paths.remove(local_path)
            config.set("sync_local_paths", paths)






def get_html_content():
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kourosh's Mind Palace</title>
    
    <script src="js/react.js"></script>
    <script src="js/react-dom.js"></script>
    <script src="js/babel.js"></script>
    <script src="js/tailwind.js"></script>
    <script src="js/marked.js"></script>
    <link rel="stylesheet" href="css/all.min.css">
    <link rel="stylesheet" href="css/fonts.css">
    
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>

    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: { sans: ['Inter', 'sans-serif'], serif: ['Cinzel', 'serif'] },
                    colors: { shadow: { 900: '#0a0a0f', 800: '#14141d', 700: '#1e1e2b', blue: '#3b82f6', gold: '#fbbf24' } }
                }
            }
        }
        
        // Lightweight Jalali Converter
        function g2j(gy, gm, gd) {
            var g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
            var gy2 = (gm > 2) ? (gy + 1) : gy;
            var days = 355666 + (365 * gy) + ~~( (gy2 + 3) / 4 ) - ~~( (gy2 + 99) / 100 ) + ~~( (gy2 + 399) / 400 ) + gd + g_d_m[gm - 1];
            var jy = -1595 + (33 * ~~(days / 12053));
            days %= 12053;
            jy += 4 * ~~(days / 1461);
            days %= 1461;
            if (days > 365) {
                jy += ~~((days - 1) / 365);
                days = (days - 1) % 365;
            }
            var jm = (days < 186) ? 1 + ~~(days / 31) : 7 + ~~((days - 186) / 30);
            var jd = 1 + ((days < 186) ? (days % 31) : ((days - 186) % 30));
            return [jy, jm, jd];
        }
        const jalaliMonths = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];
        const toFarsi = (num) => num.toString().replace(/\d/g, x => '۰۱۲۳۴۵۶۷۸۹'[x]);
    </script>

    <style>
        body {
            background-color: #050505;
            background-repeat: no-repeat; background-position: center center; background-attachment: fixed; background-size: cover;
            margin: 0; padding: 0; color: #e2e8f0; overflow: hidden;
        }
        .glass-panel {
            background: rgba(15, 20, 25, 0.45); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border-top: 1px solid rgba(255, 255, 255, 0.15); border-left: 1px solid rgba(255, 255, 255, 0.1);
            border-right: 1px solid rgba(255, 255, 255, 0.05); border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255,255,255,0.05);
        }
        .glass-panel-darker {
            background: rgba(5, 8, 12, 0.7); backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px); border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .glass-input {
            background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255, 255, 255, 0.1); color: inherit; transition: all 0.2s;
        }
        .glass-input:focus { background: rgba(10, 15, 25, 0.5); border-color: rgba(59, 130, 246, 0.5); outline: none; }
        .glass-button { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); transition: all 0.2s; cursor: pointer; }
        .glass-button:hover { background: rgba(255, 255, 255, 0.15); transform: translateY(-1px); }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.2); border-radius: 3px; }
        .fade-in { animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
        .perspective-1000 { perspective: 1000px; }
        .transform-style-3d { transform-style: preserve-3d; }
        .backface-hidden { backface-visibility: hidden; }
        .rotate-y-180 { transform: rotateY(180deg); }
    </style>
</head>
<body>
    <div id="root"></div>

    <script type="text/babel">
        const { useState, useEffect, useMemo, useRef } = React;

        const DEFAULT_LAYOUT = [
            { id: 'clock', type: 'Clock', size: 'half', visible: true, order: 0 },
            { id: 'targets', type: 'GlobalTargets', size: 'half', visible: true, order: 1 },
            { id: 'calendar', type: 'Calendar', size: 'full', visible: true, order: 2 },
            { id: 'matrix', type: 'GitHubMatrix', size: 'full', visible: true, order: 3 },
            { id: 'habits', type: 'HabitsWidget', size: 'half', visible: true, order: 4 },
            { id: 'metrics', type: 'MetricsWidget', size: 'half', visible: true, order: 5 },
            { id: 'architecture', type: 'ArchitectureWidget', size: 'full', visible: true, order: 6 },
        ];

        // --- DASHBOARD COMPONENTS ---
        const NativeGitHubMatrix = ({ heatmap }) => {
            const matrix = heatmap && heatmap.length > 0 ? heatmap : Array.from({ length: 28 }, () => Array(7).fill(0));
            const getColor = (val) => {
                if (val === 0) return 'bg-[#161b22]/50 border border-white/5'; 
                if (val === 1) return 'bg-[#0e4429] border border-[#0e4429]';
                if (val === 2) return 'bg-[#006d32] border border-[#006d32]';
                if (val === 3) return 'bg-[#26a641] border border-[#26a641]';
                return 'bg-[#39d353] border border-[#39d353] shadow-[0_0_8px_rgba(57,211,83,0.4)]';
            };
            return (
                <div className="p-6 h-full flex flex-col">
                    <h3 className="text-gray-300 text-sm font-semibold tracking-wide mb-4 border-b border-white/10 pb-2">Contribution Matrix</h3>
                    <div className="flex-grow flex items-center justify-center overflow-x-auto">
                        <div className="flex gap-1.5 pb-2">
                            <div className="flex flex-col gap-1.5 justify-between py-1 pr-2 text-[10px] text-gray-500 font-bold">
                                <span>Mon</span><span></span><span>Wed</span><span></span><span>Fri</span><span></span><span>Sun</span>
                            </div>
                            {matrix.map((week, wIdx) => (
                                <div key={wIdx} className="flex flex-col gap-1.5">
                                    {week.map((day, dIdx) => (
                                        <div key={`${wIdx}-${dIdx}`} className={`w-3.5 h-3.5 sm:w-4 sm:h-4 rounded-[3px] ${getColor(day)} transition-all hover:ring-1 hover:ring-white cursor-pointer`}></div>
                                    ))}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            );
        };

        const DualCalendar = ({ backend }) => {
            const [currentDate, setCurrentDate] = useState(new Date());
            const [showModal, setShowModal] = useState(false);
            const [selectedDate, setSelectedDate] = useState(null);
            
            const [gTitle, setGTitle] = useState("");
            const [gCat, setGCat] = useState("Goal");
            const [gTgt, setGTgt] = useState("");

            const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
            const year = currentDate.getFullYear(); const month = currentDate.getMonth();
            const daysInMonth = new Date(year, month + 1, 0).getDate();
            const firstDayOfMonth = new Date(year, month, 1).getDay();

            // Jalali specific rendering
            const [jYear, jMonth, jDay] = g2j(year, month + 1, 1);
            
            const handleDayClick = (i) => {
                const d = new Date(year, month, i);
                const offset = new Date(d.getTime() - (d.getTimezoneOffset() * 60000));
                setSelectedDate(offset.toISOString().slice(0, 16).replace('T', ' '));
                setShowModal(true);
            };
            
            const handleSaveGoal = () => {
                backend.request(JSON.stringify({action: 'manage_goal', sub: 'add', title: gTitle || "New Objective", target_hours: gTgt || 0, category: gCat, deadline: selectedDate})).then(() => {
                    setShowModal(false); setGTitle(""); setGTgt("");
                });
            };

            const renderDays = () => {
                let days = [];
                for (let i = 0; i < firstDayOfMonth; i++) days.push(<div key={`empty-${i}`} className="min-h-[70px]"></div>);
                for (let i = 1; i <= daysInMonth; i++) {
                    const dateObj = new Date(year, month, i);
                    const isToday = new Date().toDateString() === dateObj.toDateString();
                    const [jy, jm, jd] = g2j(year, month + 1, i);
                    
                    days.push(
                        <div key={i} onClick={() => handleDayClick(i)} className={`relative p-1.5 flex flex-col min-h-[70px] border border-white/5 rounded-lg 
                            ${isToday ? 'bg-blue-600/30 border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.5)]' : 'bg-black/20 hover:bg-white/10'} transition-all overflow-hidden cursor-pointer`}>
                            <div className="flex justify-between items-start w-full">
                                <span className={`text-sm font-bold ${isToday ? 'text-white' : 'text-gray-200'}`}>{i}</span>
                                <span className="text-[10px] font-bold text-yellow-500 font-[Tahoma]">{toFarsi(jd)}</span>
                            </div>
                        </div>
                    );
                }
                return days;
            };

            return (
                <div className="p-4 h-full flex flex-col w-full relative">
                    <div className="flex justify-between items-center mb-4 bg-black/40 p-2 rounded-xl border border-white/10 backdrop-blur-md">
                        <button onClick={() => setCurrentDate(new Date(year, month - 1, 1))} className="w-6 h-6 hover:bg-white/10 rounded-full transition text-gray-300"><i className="fas fa-chevron-left text-xs"></i></button>
                        <div className="flex flex-col items-center">
                            <h2 className="text-sm font-bold text-white tracking-widest uppercase">{monthNames[month]} {year}</h2>
                            <h3 className="text-[10px] font-bold text-yellow-500 font-[Tahoma] tracking-wider">{jalaliMonths[jMonth-1]} {toFarsi(jYear)}</h3>
                        </div>
                        <button onClick={() => setCurrentDate(new Date(year, month + 1, 1))} className="w-6 h-6 hover:bg-white/10 rounded-full transition text-gray-300"><i className="fas fa-chevron-right text-xs"></i></button>
                    </div>
                    <div className="calendar-grid mb-1">
                        {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((day, i) => (<div key={day} className={`text-center text-[10px] font-bold uppercase ${(i===0||i===6)?'text-red-400':'text-gray-400'}`}>{day}</div>))}
                    </div>
                    <div className="calendar-grid flex-grow overflow-y-auto pr-1">{renderDays()}</div>
                    
                    {showModal && (
                        <div className="absolute inset-0 bg-black/90 z-50 flex items-center justify-center rounded-xl p-4 backdrop-blur-md">
                            <div className="w-full max-w-sm flex flex-col gap-3">
                                <h3 className="text-white font-bold text-lg mb-2">Set Goal for {selectedDate.split(' ')[0]}</h3>
                                <input type="text" placeholder="Goal Title..." className="glass-input p-2 rounded text-sm w-full" value={gTitle} onChange={e=>setGTitle(e.target.value)} />
                                <select className="glass-input p-2 rounded text-sm w-full" value={gCat} onChange={e=>setGCat(e.target.value)}>
                                    <option>Career</option><option>Health</option><option>Education</option><option>Finance</option><option>Project</option>
                                </select>
                                <input type="number" placeholder="Target Hours" className="glass-input p-2 rounded text-sm w-full" value={gTgt} onChange={e=>setGTgt(e.target.value)} />
                                <div className="flex gap-2 mt-4">
                                    <button onClick={handleSaveGoal} className="glass-button bg-blue-600/50 hover:bg-blue-600 text-white font-bold py-2 rounded flex-grow">Save Goal</button>
                                    <button onClick={() => setShowModal(false)} className="glass-button bg-red-600/30 hover:bg-red-600 text-white font-bold py-2 rounded flex-grow">Cancel</button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            );
        };

        const GlobalTargets = ({ metrics }) => {
            // Calculate actual progress from metrics
            const totalHours = metrics?.total_study_hours || 0;
            const targetHours = 50; // This could be made configurable
            const progress = targetHours > 0 ? Math.min((totalHours / targetHours) * 100, 100) : 0;
            
            return (
                <div className="p-4 h-full flex flex-col items-center justify-center text-center w-full">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-[11px] mb-6">Global Progress</h3>
                    <div className="w-32 h-32 sm:w-40 sm:h-40 rounded-full border-[8px] border-black/40 relative flex items-center justify-center shadow-inner">
                        <div className="absolute inset-0 border-[8px] border-blue-500 rounded-full border-t-transparent border-r-transparent opacity-80 shadow-[0_0_15px_rgba(59,130,246,0.6)]" 
                            style={{ transform: `rotate(${-45 + (progress / 100) * 360}deg)` }}></div>
                        <div className="flex flex-col items-center z-10">
                            <span className="text-3xl font-bold text-white drop-shadow-lg">{Math.round(progress)}%</span>
                            <span className="text-[10px] text-gray-400 mt-1 font-mono tracking-wider">{totalHours.toFixed(1)} / {targetHours} Hrs</span>
                        </div>
                    </div>
                    <div className="mt-6 text-[11px] text-green-400 font-bold bg-green-900/30 px-4 py-1.5 rounded-full border border-green-500/30">
                        <i className="fas fa-satellite-dish mr-1"></i> {metrics ? `${Math.round(progress)}% Complete` : 'No Data'}
                    </div>
                </div>
            );
        };

        const MetricsWidget = ({ metrics }) => {
            const hVol = metrics && metrics.hourly_vol ? metrics.hourly_vol : [10, 20, 5, 40, 80, 60, 30, 90, 100, 50, 20, 10];
            const maxVol = Math.max(...hVol, 1);
            return (
                <div className="p-4 h-full flex flex-col w-full">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4 w-full text-left">Study Volume by Hour (08:00 - 20:00)</h3>
                    <div className="flex-grow flex items-end justify-between gap-1 mt-auto">
                        {hVol.map((h, i) => (
                            <div key={i} className="w-full bg-blue-500/60 hover:bg-blue-400 rounded-t-sm transition-all relative group" style={{height: `${(h/maxVol)*100}%`}}>
                                <span className="absolute -top-6 left-1/2 -translate-x-1/2 bg-black text-white text-[10px] px-1 rounded opacity-0 group-hover:opacity-100 transition">{h.toFixed(1)}m</span>
                            </div>
                        ))}
                    </div>
                    <div className="flex justify-between text-[8px] text-gray-500 mt-2 font-mono"><span>08:00</span><span>20:00</span></div>
                </div>
            );
        };

        const DashboardHabitWidget = ({ habits, habitLogs }) => {
            return (
                <div className="p-4 h-full flex flex-col w-full overflow-y-auto">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Habit Streaks</h3>
                    <div className="flex flex-col gap-2">
                        {habits && habits.map(h => {
                            const isPos = h.type === 'Positive';
                            return (
                                <div key={h.id} className="flex justify-between items-center p-2 bg-white/5 rounded border border-white/5">
                                    <span className={`text-xs font-bold ${isPos ? 'text-green-400' : 'text-red-400'}`}>{h.name}</span>
                                    <span className="text-[10px] font-mono text-gray-400">Streak: Active</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            );
        };

        const DashboardArchitectureWidget = ({ goals }) => {
            const sortedGoals = goals ? [...goals].filter(g => g.deadline).sort((a,b) => new Date(a.deadline) - new Date(b.deadline)) : [];
            return (
                <div className="p-4 h-full flex flex-col w-full overflow-y-auto">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Upcoming Deadlines</h3>
                    <div className="flex flex-col gap-2">
                        {sortedGoals.slice(0, 5).map(g => (
                            <div key={g.id} className="flex justify-between items-center p-2 bg-white/5 rounded border border-white/5">
                                <span className="text-xs font-bold text-gray-200">{g.title}</span>
                                <span className="text-[10px] font-mono text-yellow-400">{g.deadline.split(' ')[0]}</span>
                            </div>
                        ))}
                    </div>
                </div>
            );
        };

        const DashboardView = ({ layout, setLayout, goals, isEditingLayout, setIsEditingLayout, clockFeed, heatmap, habits, habitLogs, metrics, backend }) => {
            const toggleWidgetVisibility = (id) => setLayout(prev => prev.map(w => w.id === id ? { ...w, visible: !w.visible } : w));
            const toggleWidgetSize = (id) => setLayout(prev => prev.map(w => w.id === id ? { ...w, size: w.size === 'full' ? 'half' : 'full' } : w));
            
            const renderWidget = (widget) => {
                switch(widget.type) {
                    case 'Clock': return (
                        <div className="flex flex-col items-center justify-center h-full p-4 w-full">
                            {clockFeed ? <img src={clockFeed} className="w-56 h-56 drop-shadow-2xl object-contain" /> : <div className="text-gray-500">Loading Native Horology...</div>}
                        </div>
                    );
                    case 'Calendar': return <DualCalendar backend={backend} />;
                    case 'GlobalTargets': return <GlobalTargets metrics={metrics} />;
                    case 'GitHubMatrix': return <NativeGitHubMatrix heatmap={heatmap} />;
                    case 'HabitsWidget': return <DashboardHabitWidget habits={habits} habitLogs={habitLogs} />;
                    case 'MetricsWidget': return <MetricsWidget metrics={metrics} />;
                    case 'ArchitectureWidget': return <DashboardArchitectureWidget goals={goals} />;
                    default: return null;
                }
            };

            const sortedLayout = [...layout].sort((a, b) => a.order - b.order);

            return (
                <div className="h-full flex flex-col fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase text-shadow-blue drop-shadow-md">Dashboard</h2>
                        <button onClick={() => setIsEditingLayout(!isEditingLayout)}
                            className={`px-4 py-2 rounded text-xs font-bold transition-all shadow-lg border backdrop-blur-md
                                ${isEditingLayout ? 'bg-blue-600 text-white border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.6)]' : 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/15'}`}>
                            <i className={`fas ${isEditingLayout ? 'fa-check' : 'fa-sliders-h'} mr-2`}></i> {isEditingLayout ? 'Save Layout' : 'Edit Layout'}
                        </button>
                    </div>

                    <div className="flex flex-wrap -mx-3 items-stretch overflow-y-auto pb-10 flex-grow content-start">
                        {sortedLayout.filter(w => isEditingLayout || w.visible).map((widget) => {
                            const widthClass = widget.size === 'full' ? 'w-full' : 'w-full md:w-1/2';
                            return (
                                <div key={widget.id} className={`${widthClass} px-3 mb-6 transition-all duration-300`}>
                                    <div className={`glass-panel overflow-hidden h-full flex flex-col relative ${!widget.visible ? 'opacity-30 grayscale' : ''}`} style={{ minHeight: '320px' }}>
                                        {isEditingLayout && (
                                            <div className="absolute inset-0 bg-black/80 z-50 flex flex-col items-center justify-center backdrop-blur-sm gap-3 rounded-xl border-2 border-blue-500 border-dashed">
                                                <div className="text-white font-bold text-lg uppercase tracking-widest">{widget.type}</div>
                                                <div className="flex gap-3 mt-4">
                                                    <button onClick={() => toggleWidgetVisibility(widget.id)} className={`px-4 py-2 rounded text-xs font-bold ${widget.visible ? 'bg-green-600' : 'bg-red-600'} text-white`}>
                                                        <i className={`fas fa-${widget.visible ? 'eye' : 'eye-slash'} mr-2`}></i> Toggle
                                                    </button>
                                                    <button onClick={() => toggleWidgetSize(widget.id)} className="px-4 py-2 rounded text-xs font-bold bg-blue-600 text-white">
                                                        <i className={`fas fa-${widget.size === 'full' ? 'compress' : 'expand'} mr-2`}></i> Resize
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                        {renderWidget(widget)}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            );
        };

        // --- ALL OTHER VIEWS ---
            const ProductivityHubView = ({ backend, timerState, camFeed, flatGoals, queue, refreshQueue, settings }) => {
            const [dur, setDur] = useState(25);
            const [crs, setCrs] = useState("");
            const [type, setType] = useState("Work");
            const [editingId, setEditingId] = useState(null);
            const [activeTab, setActiveTab] = useState("timeline");
            const [showProcessList, setShowProcessList] = useState(false);
            const [selectedProcesses, setSelectedProcesses] = useState([]);
            const [isPaused, setIsPaused] = useState(false);
const startFocusSession = () => {
    if (!backend) {
        console.error('Backend not available');
        return;
    }
    
    // If app monitoring is enabled and we haven't shown the process list yet
    if (settings && settings.app_monitoring_enabled && !showProcessList) {
        backend.request(JSON.stringify({action: 'get_processes'})).then(res => {
            const data = JSON.parse(res);
            setSelectedProcesses(data.processes || []);
            setShowProcessList(true);
        });
        return;
    }
    
    // Check if there are items in the queue
    if (queue && queue.length > 0) {
        // Start the first item in the queue
        const firstItem = queue[0];
        setCurrentQueueIndex(0);
        
        console.log(`Starting queue item: ${firstItem.title} (${firstItem.duration}m) - ${firstItem.type}`);
        
        backend.request(JSON.stringify({
            action: 'start_timer', 
            duration: firstItem.duration, 
            course: firstItem.course || "General",
            type: firstItem.type || "Work"
        })).then(res => {
            const data = JSON.parse(res);
            if (data.status === 'started') {
                setShowProcessList(false);
                setIsPaused(false);
            }
        }).catch(err => {
            console.error('Failed to start timer:', err);
            alert('Failed to start timer. Check console for details.');
        });
    } else {
        // If no queue items, create a new session from form
        const duration = parseInt(dur) || 25;
        const course = crs || "General";
        const sessionType = type || "Work";
        
        console.log(`No queue items. Starting custom timer: ${duration}m, ${course}, ${sessionType}`);
        
        backend.request(JSON.stringify({
            action: 'start_timer', 
            duration: duration, 
            course: course,
            type: sessionType
        })).then(res => {
            const data = JSON.parse(res);
            if (data.status === 'started') {
                setShowProcessList(false);
                setIsPaused(false);
            }
        }).catch(err => {
            console.error('Failed to start timer:', err);
            alert('Failed to start timer. Check console for details.');
        });
    }
};
            // Add this modal before the main content
            {showProcessList && (
                <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4 backdrop-blur-md">
                    <div className="glass-panel p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                        <h3 className="text-white font-bold text-xl mb-4">📋 Running Applications</h3>
                        <p className="text-gray-400 text-sm mb-4">
                            The following apps are currently running. They will be monitored during your focus session.
                        </p>
                        <div className="flex flex-col gap-1 mb-4 max-h-60 overflow-y-auto">
                            {selectedProcesses.map((p, i) => (
                                <div key={i} className="flex items-center justify-between p-2 bg-white/5 rounded border border-white/10 text-sm">
                                    <span className="text-gray-300">{p.name}</span>
                                    <span className="text-gray-500 text-xs">PID: {p.pid}</span>
                                </div>
                            ))}
                        </div>
                        <div className="flex gap-3">
<button onClick={() => {
    // Close modal and start timer
    setShowProcessList(false);
    const duration = parseInt(dur) || 25;
    const course = crs || "General";
    const sessionType = type || "Work";
    
    console.log(`Starting timer from modal: ${duration}m, ${course}, ${sessionType}`);
    
    backend.request(JSON.stringify({
        action: 'start_timer', 
        duration: duration, 
        course: course,
        type: sessionType
    })).then(res => {
        const data = JSON.parse(res);
        console.log('Timer start response from modal:', data);
        if (data.status !== 'started') {
            alert('Failed to start timer. Please try again.');
        }
    }).catch(err => {
        console.error('Failed to start timer from modal:', err);
        alert('Failed to start timer. Check console for details.');
    });
}} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-green-600/50 border-green-500/50 hover:bg-green-600">
    <i className="fas fa-play mr-2"></i> Start Session
</button>
                        </div>
                    </div>
                </div>
            )}

            const getTaskColor = (courseName, isBreak) => {
                if (isBreak) return 'rgba(100, 100, 100, 0.8)';
                if (!courseName || courseName === 'General') return 'rgba(59, 130, 246, 0.8)';
                let hash = 0;
                for (let i = 0; i < courseName.length; i++) hash = courseName.charCodeAt(i) + ((hash << 5) - hash);
                return `hsl(${Math.abs(hash) % 360}, 65%, 45%)`;
            };

            const handleAction = (sub, item={}) => {
                const payload = { action: 'manage_queue', sub: sub, id: item.id, title: item.title || crs || "General", duration: item.duration || dur, type: item.type || type, course: item.course || crs || "General" };
                backend.request(JSON.stringify(payload)).then(res => {
                    const data = JSON.parse(res);
                    if(data.queue) refreshQueue(data.queue);
                    setEditingId(null);
                });
            };

            const toggleTimer = () => {
                if (!backend) return;
                if (timerState.is_running) {
                    backend.request(JSON.stringify({action: 'stop_timer'}));
                    setIsPaused(true);
                } else {
                    backend.request(JSON.stringify({action: 'start_timer', duration: dur, course: crs || "General"}));
                    setIsPaused(false);
                }
            };

            return (
                <div className="h-full flex flex-col fade-in">
                    <div className="flex justify-between items-center mb-4 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Focus Hub</h2>
                    </div>

                    <div className="flex gap-6 border-b border-white/10 mb-6 shrink-0">
                        <button onClick={() => setActiveTab('timeline')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'timeline' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Timeline & Queue</button>
                        <button onClick={() => setActiveTab('vision')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'vision' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Vision Tracker</button>
                    </div>

                    {activeTab === 'timeline' && (
                        <div className="flex flex-col flex-grow overflow-hidden">
                            <div className="flex flex-wrap items-center gap-3 mb-4 w-full glass-panel p-3 shrink-0 bg-black/40">
                                <select className="glass-input px-3 py-1.5 rounded text-xs font-bold uppercase w-48" value={crs} onChange={e => setCrs(e.target.value)}>
                                    <option value="">General</option>
                                    {flatGoals && flatGoals.map(c => <option key={c} value={c}>{c}</option>)}
                                </select>
                                <input type="number" className="glass-input px-3 py-1.5 rounded text-xs font-bold uppercase w-20" value={dur} onChange={e => setDur(parseInt(e.target.value))} />
                                <select className="glass-input px-3 py-1.5 rounded text-xs font-bold uppercase w-28" value={type} onChange={e => setType(e.target.value)}>
                                    <option>Work</option><option>Break</option>
                                </select>
                                
                                {editingId ? (
                                    <button onClick={() => handleAction('edit', {id: editingId})} className="glass-button px-5 py-1.5 rounded text-[11px] font-bold text-blue-300 uppercase">Save</button>
                                ) : (
                                    <button onClick={() => handleAction('add')} className="glass-button px-5 py-1.5 rounded text-[11px] font-bold text-gray-200 uppercase">+ Add</button>
                                )}
                                <button onClick={() => handleAction('clear')} className="glass-button px-5 py-1.5 rounded text-[11px] font-bold text-red-300 uppercase ml-auto">Clear All</button>
                            </div>

                            <div className="glass-panel flex-grow rounded-xl relative p-6 flex flex-col gap-6 overflow-hidden bg-black/20">
                                <div className="flex-grow rounded-lg overflow-y-auto">
                                    <div className="flex flex-col gap-1.5">
                                        {timerState.is_running && (
                                            <div className="flex items-center justify-between p-3 bg-blue-600/20 border border-blue-500/40 rounded-lg shadow-[inset_0_0_15px_rgba(59,130,246,0.2)]">
                                                <span className="text-xs font-bold text-white tracking-wide">[Active] [Work] {timerState.course}</span>
                                                <span className="text-xs text-red-400 font-bold"><i className="fas fa-exclamation-triangle mr-1"></i> {timerState.distractions} Distractions</span>
                                            </div>
                                        )}
                                        {queue && queue.map(q => (
                                            <div key={q.id} className="flex items-center justify-between p-3 bg-white/5 hover:bg-white/10 border border-white/5 rounded-lg transition group">
                                                <span className="text-xs text-gray-400 font-medium group-hover:text-gray-200">[{q.type}] {q.course} ({q.duration}m)</span>
                                                <div className="flex gap-5 opacity-50 group-hover:opacity-100 transition">
                                                    <button onClick={() => {setEditingId(q.id); setCrs(q.course); setDur(q.duration); setType(q.type);}} className="text-[10px] font-bold text-gray-400 hover:text-yellow-400 uppercase tracking-widest">Edit</button>
                                                    <button onClick={() => handleAction('delete', {id: q.id})} className="text-[10px] font-bold text-gray-400 hover:text-red-400 uppercase tracking-widest">- Remove</button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div className="w-full flex flex-col shrink-0 mt-2">
                                    <div className="w-full h-8 bg-black/60 rounded-md flex overflow-hidden border border-white/10 relative gap-1 p-1">
                                        {timerState.is_running && (
                                            <div style={{width: '30%', backgroundColor: getTaskColor(timerState.course, false)}} className="relative rounded-sm overflow-hidden flex items-center justify-center shadow-inner">
                                                {timerState.distraction_markers && timerState.distraction_markers.map((d, i) => (
                                                    <div key={i} className="absolute top-0 w-1 h-full bg-red-500 shadow-[0_0_8px_red]" style={{left: `${d}%`}}></div>
                                                ))}
                                            </div>
                                        )}
                                        {queue && queue.map((q, i) => (
                                            <div key={q.id} style={{flex: q.duration, backgroundColor: getTaskColor(q.course, q.type === 'Break')}} className="relative rounded-sm opacity-80 hover:opacity-100 transition-opacity">
                                            </div>
                                        ))}
                                    </div>
                                </div>
{/* Bottom Controls */}
<div className="flex justify-between items-end mt-2 shrink-0">
    <div>
        <div className={`text-5xl font-mono font-bold tracking-widest drop-shadow-lg ${timerState.is_running ? 'text-white' : isPaused ? 'text-yellow-400' : 'text-gray-300'}`}>
            {timerState.time_str || "25:00"}
        </div>
        <div className="text-xs text-gray-500 mt-1">
            {timerState.is_running ? 'Session in progress' : isPaused ? '⏸ Paused' : 'Ready'}
        </div>
    </div>
    <div className="flex gap-3">
        {/* Start/Pause Toggle Button */}
        <button onClick={toggleTimer} 
            className={`px-6 py-3 rounded-lg text-xs font-bold tracking-widest text-white uppercase shadow-lg transition-colors 
                ${timerState.is_running ? 'bg-yellow-600/50 hover:bg-yellow-600 border border-yellow-500/50' : 'bg-green-600/50 hover:bg-green-600 border border-green-500/50'}`}>
            <i className={`fas ${timerState.is_running ? 'fa-pause' : 'fa-play'} mr-2`}></i>
            {timerState.is_running ? 'Pause' : 'Start'}
        </button>
        
        {/* Stop Button */}
        <button onClick={() => { 
            if (timerState.is_running) {
                backend.request(JSON.stringify({action: 'stop_timer'}));
                setIsPaused(false);
            }
        }} 
            className="px-6 py-3 rounded-lg text-xs font-bold tracking-widest text-white uppercase bg-red-600/50 hover:bg-red-600 border border-red-500/50 shadow-lg transition-colors">
            <i className="fas fa-stop mr-2"></i> Stop
        </button>
    </div>
</div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'vision' && (
                        <div className="flex-grow glass-panel rounded-xl flex items-center justify-center p-4 relative overflow-hidden bg-black/40">
                            {camFeed ? (
                                <img src={camFeed} className="w-full h-full object-contain opacity-90 rounded drop-shadow-2xl" />
                            ) : (
                                <div className="text-gray-500 flex flex-col items-center">
                                    <i className="fas fa-video-slash text-5xl mb-4 opacity-50"></i>
                                    <p className="text-sm font-bold uppercase tracking-widest">Vision Tracker Offline / Paused</p>
                                </div>
                            )}
                            <div className="absolute top-6 left-6 bg-black/80 px-4 py-2 rounded text-[10px] font-mono text-blue-400 font-bold border border-white/10 shadow-lg">
                                <i className="fas fa-circle text-[8px] text-red-500 mr-2 animate-pulse"></i> VISION ENGINE ACTIVE
                            </div>
                        </div>
                    )}
                </div>
            );
        };

        const LifeArchitectureView = ({ goals, backend, refreshGoals }) => {
            const [title, setTitle] = useState("");
            const [target, setTarget] = useState("");
            const [parent, setParent] = useState("");
            const [deadline, setDeadline] = useState(new Date(new Date().getTime() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 16));
            
            const addGoal = () => {
                backend.request(JSON.stringify({action: 'manage_goal', sub: 'add', title: title, target_hours: target, parent_id: parent || null, deadline: deadline.replace('T', ' ')})).then(res => {
                    refreshGoals(JSON.parse(res));
                    setTitle(""); setTarget("");
                });
            };
            const delGoal = (id) => {
                backend.request(JSON.stringify({action: 'manage_goal', sub: 'delete', id: id})).then(res => {
                    refreshGoals(JSON.parse(res));
                });
            };

            const buildTree = (items) => {
                let map = {}, roots = [];
                items.forEach(g => { map[g.id] = {...g, children: []}; });
                items.forEach(g => {
                    if (g.parent_id && map[g.parent_id]) map[g.parent_id].children.push(map[g.id]);
                    else roots.push(map[g.id]);
                });
                return roots;
            };

            const renderNode = (node, depth=0) => (
                <div key={node.id} style={{ marginLeft: depth * 20 }} className="mb-2">
                    <div className="flex justify-between items-center bg-black/20 p-2 rounded hover:bg-white/5 border border-white/5">
                        <span><strong className="text-white">{node.title}</strong> {node.target_hours > 0 && `- Target: ${node.target_hours}h`} <span className="text-[10px] text-yellow-500 ml-2">DL: {node.deadline}</span></span>
                        <div className="flex gap-3">
                            <button onClick={() => setParent(node.id)} className="text-xs text-blue-400 hover:text-blue-300">+ Sub</button>
                            <i onClick={() => delGoal(node.id)} className="fas fa-trash text-red-500 cursor-pointer hover:scale-110"></i>
                        </div>
                    </div>
                    {node.children.map(child => renderNode(child, depth + 1))}
                </div>
            );

            return (
                <div className="h-full flex flex-col fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Life Architecture</h2>
                    </div>
                    <div className="flex gap-2 mb-4 shrink-0 glass-panel p-2 flex-wrap">
                        {parent && <span className="text-xs text-blue-400 self-center">Adding sub-goal... <i className="fas fa-times cursor-pointer text-red-400" onClick={()=>setParent("")}></i></span>}
                        <input type="text" placeholder="Goal Title..." className="glass-input px-3 py-1.5 rounded text-xs font-bold flex-grow min-w-[150px]" value={title} onChange={e=>setTitle(e.target.value)} />
                        <input type="number" placeholder="Target Hrs..." className="glass-input px-3 py-1.5 rounded text-xs font-bold w-24" value={target} onChange={e=>setTarget(e.target.value)} />
                        <input type="datetime-local" className="glass-input px-3 py-1.5 rounded text-xs font-bold" value={deadline} onChange={e=>setDeadline(e.target.value)} />
                        <button onClick={addGoal} className="glass-button px-4 py-1.5 rounded text-[11px] font-bold text-blue-300 uppercase">+ Add Goal</button>
                    </div>
                    <div className="glass-panel p-6 flex-grow overflow-y-auto text-sm text-gray-300">
                        {goals && goals.length > 0 ? buildTree(goals).map(root => renderNode(root)) : <p>No goals defined.</p>}
                    </div>
                </div>
            );
        };

            const HabitMatrixView = ({ habits, backend, refreshHabits, habitLogs, setHabitLogs }) => {
    const [newName, setNewName] = useState("");
    const [newType, setNewType] = useState("Positive");
    const [editingId, setEditingId] = useState(null);
    
    // Generate last 7 days
    const days = [];
    const today = new Date();
    for (let i = 6; i >= 0; i--) {
        const date = new Date(today);
        date.setDate(date.getDate() - i);
        const dateStr = date.toLocaleDateString('en-US', { 
            weekday: 'short', 
            month: 'numeric', 
            day: 'numeric' 
        });
        days.push(dateStr);
    }
    
    const calculateStreak = (habitId) => {
        if (!habitLogs || habitLogs.length === 0) return 0;
        
        const logs = habitLogs
            .filter(log => log.habit_id === habitId)
            .sort((a, b) => new Date(a.date) - new Date(b.date));
        
        if (logs.length === 0) return 0;
        
        let streak = 0;
        for (let i = 0; i < days.length; i++) {
            const log = logs.find(l => l.date === days[i]);
            if (log && log.status === 1) {
                streak++;
            } else if (i > 0 && (!log || log.status === 0)) {
                break;
            }
        }
        return streak;
    };
    
    const handleAction = (sub, id, name, type) => {
        backend.request(JSON.stringify({
            action: 'manage_habit', 
            sub: sub, 
            id: id, 
            name: name || newName, 
            type: type || newType
        })).then(res => {
            const data = JSON.parse(res);
            console.log('Habit action response:', data);
            if (data.habits) refreshHabits(data.habits);
            if (data.habit_logs) setHabitLogs(data.habit_logs);
            setNewName("");
            setEditingId(null);
        }).catch(err => {
            console.error('Failed to manage habit:', err);
            alert('Failed to update habit. Check console.');
        });
    };
    
    const toggleLog = (hid, dateStr) => {
        console.log(`Toggling log for habit ${hid} on ${dateStr}`);
        
        const logExists = habitLogs && habitLogs.some(log => log.habit_id === hid && log.date === dateStr);
        const currentStatus = logExists ? 1 : 0;
        const newStatus = currentStatus === 1 ? 0 : 1;
        
        backend.request(JSON.stringify({
            action: 'manage_habit', 
            sub: 'toggle_log', 
            habit_id: hid, 
            date: dateStr, 
            status: newStatus
        })).then(res => {
            const data = JSON.parse(res);
            console.log('Toggle response:', data);
            if (data.habits) refreshHabits(data.habits);
            if (data.habit_logs) setHabitLogs(data.habit_logs);
        }).catch(err => {
            console.error('Failed to toggle habit log:', err);
            alert('Failed to update habit. Check console.');
        });
    };
    
    return (
        <div className="h-full flex flex-col fade-in">
            <div className="flex justify-between items-center mb-6 shrink-0">
                <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Habit Matrix</h2>
                <span className="text-xs text-gray-400 font-mono">7-DAY ROLLING</span>
            </div>
            <div className="flex gap-2 mb-4 shrink-0 glass-panel p-2">
                <select className="glass-input px-3 py-1.5 rounded text-xs font-bold" value={newType} onChange={e => setNewType(e.target.value)}>
                    <option value="Positive">Positive (+)</option>
                    <option value="Negative">Negative (-)</option>
                </select>
                <input type="text" placeholder="New Habit Name..." className="glass-input px-3 py-1.5 rounded text-xs font-bold flex-grow" value={newName} onChange={e => setNewName(e.target.value)} />
                <button onClick={() => handleAction('add')} className="glass-button px-4 py-1.5 rounded text-[11px] font-bold text-blue-300 uppercase">+ Add Habit</button>
            </div>
            <div className="glass-panel p-1 rounded-xl overflow-x-auto">
                <table className="w-full text-left border-collapse min-w-[600px]">
                    <thead>
                        <tr className="border-b border-white/10 bg-black/40">
                            <th className="p-4 text-xs font-bold text-gray-400 uppercase w-12 text-center">#</th>
                            <th className="p-4 text-xs font-bold text-gray-400 uppercase">Habit</th>
                            <th className="p-4 text-xs font-bold text-gray-400 uppercase text-center">Streak</th>
                            {days.map(day => (
                                <th key={day} className="p-4 text-[10px] font-bold text-gray-400 uppercase text-center whitespace-nowrap">
                                    {day}
                                </th>
                            ))}
                            <th className="p-4 text-[10px] font-bold text-gray-400 uppercase text-center">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {habits && habits.map((h, idx) => {
                            const isPos = h.type === 'Positive';
                            const streak = calculateStreak(h.id);
                            return (
                                <tr key={h.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                    <td className="p-4 text-xs font-mono text-gray-500 text-center">{idx + 1}</td>
                                    <td className={`p-4 text-sm font-bold tracking-wide ${isPos ? 'text-green-400' : 'text-red-400'}`}>
                                        {editingId === h.id ? (
                                            <input type="text" className="glass-input px-2 py-1 rounded text-xs w-full" defaultValue={h.name} onBlur={(e) => handleAction('edit', h.id, e.target.value, h.type)} autoFocus />
                                        ) : (
                                            <span>{isPos ? '+' : '-'} {h.name}</span>
                                        )}
                                    </td>
                                    <td className="p-4 text-xs font-mono text-blue-400 text-center font-bold">
                                        {streak > 0 ? `${streak}d` : '—'}
                                    </td>
                                    {days.map((day, dIdx) => (
                                        <td key={dIdx} className="p-4 text-center">
                                            <input type="checkbox" 
                                                onChange={() => toggleLog(h.id, day)}
                                                checked={habitLogs && habitLogs.some(log => log.habit_id === h.id && log.date === day && log.status === 1)}
                                                className={`w-5 h-5 rounded bg-black/40 border border-white/20 checked:border-transparent appearance-none cursor-pointer transition-all flex items-center justify-center checked:after:content-['✓'] checked:after:text-white checked:after:text-sm ${isPos ? 'checked:bg-green-500' : 'checked:bg-red-500'}`} />
                                        </td>
                                    ))}
                                    <td className="p-4 text-center">
                                        <i onClick={() => setEditingId(h.id)} className="fas fa-edit text-yellow-400 cursor-pointer mx-2 hover:scale-110"></i>
                                        <i onClick={() => handleAction('delete', h.id)} className="fas fa-trash text-red-400 cursor-pointer mx-2 hover:scale-110"></i>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

        const DaySummaryView = ({ metrics }) => {
            const tdyStudy = metrics ? metrics.tdy_study : 0;
            const ydyStudy = metrics ? metrics.ydy_study : 0;
            const tdyDist = metrics ? metrics.tdy_dist : 0;
            const ydyDist = metrics ? metrics.ydy_dist : 0;
            
            const studyDiff = tdyStudy - ydyStudy;
            const distDiff = tdyDist - ydyDist;

            return (
                <div className="flex flex-col h-full fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Day Summary</h2>
                    </div>
                    <div className="flex flex-col gap-4 overflow-y-auto">
                        <div className="glass-panel p-8 text-center border-t-2 border-t-blue-500/50">
                            <h3 className="text-gray-400 font-bold uppercase tracking-widest text-xs mb-2">Time Studied Today</h3>
                            <div className="text-5xl font-mono text-white mb-2">{Math.floor(tdyStudy/60)}h {Math.floor(tdyStudy%60)}m</div>
                            <span className={`text-sm font-semibold ${studyDiff >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                <i className={`fas fa-arrow-${studyDiff >= 0 ? 'up' : 'down'} mr-1`}></i> {Math.abs(studyDiff).toFixed(1)}m compared to yesterday
                            </span>
                        </div>
                        <div className="glass-panel p-8 text-center border-t-2 border-t-red-500/50">
                            <h3 className="text-gray-400 font-bold uppercase tracking-widest text-xs mb-2">Total Distractions</h3>
                            <div className="text-5xl font-mono text-white mb-2">{tdyDist}</div>
                            <span className={`text-sm font-semibold ${distDiff <= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                <i className={`fas fa-arrow-${distDiff >= 0 ? 'up' : 'down'} mr-1`}></i> {Math.abs(distDiff)} compared to yesterday
                            </span>
                        </div>
                    </div>
                </div>
            );
        };

        const QuizEngineView = ({ quizzes, backend, refreshQuizzes, flatGoals }) => {
            const [activeTab, setActiveTab] = useState('library');
            const [qTitle, setQTitle] = useState("");
            const [qCourse, setQCourse] = useState("");
            const [qFolder, setQFolder] = useState("Uncategorized");
            const [qColor, setQColor] = useState("#3b82f6");
            const [qJson, setQJson] = useState('[\n  {"q": "Difference between Process and Thread?", "opts": ["Memory Isolation", "No Difference"], "ans": 0}\n]');
            const [activeQuiz, setActiveQuiz] = useState(null);
            const [qIndex, setQIndex] = useState(0);
            const [score, setScore] = useState(0);
            const [selectedOpt, setSelectedOpt] = useState(null);

            const parsedQuiz = useMemo(() => {
                if (!activeQuiz) return null;
                try { return JSON.parse(activeQuiz.json); } catch { return []; }
            }, [activeQuiz]);

            const addQuiz = () => {
                backend.request(JSON.stringify({action: 'manage_quiz', sub: 'add', title: qTitle || "New Quiz", course: qCourse || "General", folder: qFolder, color: qColor, json: qJson})).then(res => {
                    refreshQuizzes(JSON.parse(res).quizzes); setQTitle("");
                });
            };

            const handleNext = () => {
                if (selectedOpt === parsedQuiz[qIndex].ans) setScore(s => s + 1);
                setQIndex(i => i + 1);
                setSelectedOpt(null);
            };

            return (
                <div className="flex flex-col h-full fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Quiz Engine</h2>
                    </div>

                    <div className="flex gap-6 border-b border-white/10 mb-6 shrink-0">
                        <button onClick={() => setActiveTab('library')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'library' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Library & Import</button>
                        <button onClick={() => setActiveTab('study')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'study' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Active Quiz</button>
                    </div>

                    {activeTab === 'library' && (
                        <div className="flex flex-col lg:flex-row gap-6 h-full overflow-hidden">
                            <div className="w-full lg:w-1/2 flex flex-col gap-4">
                                <div className="glass-panel p-4 flex flex-col gap-2">
                                    <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2 border-b border-white/10 pb-1">Import JSON Quiz</h3>
                                    <div className="flex gap-2">
                                        <select className="glass-input p-2 rounded text-xs flex-grow" value={qCourse} onChange={e=>setQCourse(e.target.value)}><option value="">Goal / Course...</option>{flatGoals.map(c=><option key={c} value={c}>{c}</option>)}</select>
                                        <input type="text" placeholder="Folder..." value={qFolder} onChange={e=>setQFolder(e.target.value)} className="glass-input p-2 rounded text-xs w-32" />
                                        <input type="color" value={qColor} onChange={e=>setQColor(e.target.value)} className="w-8 h-8 rounded cursor-pointer border-0 p-0" />
                                    </div>
                                    <input type="text" placeholder="Quiz Title" value={qTitle} onChange={e=>setQTitle(e.target.value)} className="glass-input p-2 rounded text-xs" />
                                    <textarea value={qJson} onChange={e=>setQJson(e.target.value)} className="glass-input p-2 rounded text-xs font-mono h-24"></textarea>
                                    <button onClick={addQuiz} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-green-300 uppercase shadow-lg">Save JSON Quiz</button>
                                </div>
                            </div>
                            <div className="glass-panel flex-grow flex flex-col p-4 overflow-y-auto w-full lg:w-1/2">
                                <h3 className="text-gray-300 text-[10px] font-bold tracking-widest uppercase mb-4 border-b border-white/10 pb-1">SAVED QUIZZES</h3>
                                <div className="flex flex-col gap-2">
                                    {quizzes && quizzes.map(q => (
                                        <div key={q.id} className="flex items-center gap-3 p-3 bg-white/5 hover:bg-white/10 rounded cursor-pointer border border-white/10 transition group" onClick={() => {setActiveQuiz(q); setQIndex(0); setScore(0); setActiveTab('study');}}>
                                            <div className="w-3 h-3 rounded-full" style={{backgroundColor: q.color}}></div>
                                            <div className="flex flex-col flex-grow">
                                                <span className="text-[10px] text-gray-500 font-bold tracking-wider uppercase">{q.folder} / {q.course}</span>
                                                <span className="text-sm font-bold text-gray-200">{q.title}</span>
                                            </div>
                                            <i onClick={(e) => {e.stopPropagation(); backend.request(JSON.stringify({action: 'manage_quiz', sub: 'delete', id: q.id})).then(res => refreshQuizzes(JSON.parse(res).quizzes));}} className="fas fa-trash text-red-500 opacity-0 group-hover:opacity-100 hover:scale-110 transition"></i>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'study' && (
                        <div className="flex-grow glass-panel p-8 flex flex-col justify-center items-center text-center overflow-y-auto relative">
                            {parsedQuiz ? (
                                qIndex < parsedQuiz.length ? (
                                    <div className="w-full max-w-lg">
                                        <div className="absolute top-4 left-4 text-xs font-mono text-gray-500">Q {qIndex + 1}/{parsedQuiz.length}</div>
                                        <h3 className="text-xl font-serif text-white mb-8 leading-relaxed">{parsedQuiz[qIndex].q}</h3>
                                        <div className="flex flex-col gap-3 w-full text-left">
                                            {parsedQuiz[qIndex].opts.map((opt, i) => (
                                                <label key={i} className={`flex items-center gap-3 p-4 rounded-lg border transition cursor-pointer ${selectedOpt === i ? 'bg-blue-600/30 border-blue-400' : 'border-white/10 bg-black/30 hover:bg-white/10'}`}>
                                                    <input type="radio" name="quiz_opt" checked={selectedOpt === i} onChange={() => setSelectedOpt(i)} className="w-4 h-4 accent-blue-500" />
                                                    <span className="text-sm text-gray-200">{opt}</span>
                                                </label>
                                            ))}
                                        </div>
                                        <button onClick={handleNext} disabled={selectedOpt === null} className="mt-8 glass-button px-8 py-3 rounded text-[11px] font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600 disabled:opacity-50 transition">NEXT</button>
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center">
                                        <h2 className="text-3xl font-bold text-white mb-4">Quiz Complete!</h2>
                                        <p className="text-xl text-green-400 font-mono">Score: {score} / {parsedQuiz.length}</p>
                                        <button onClick={() => {setQIndex(0); setScore(0);}} className="mt-8 glass-button px-8 py-3 rounded text-[11px] font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">Restart Quiz</button>
                                    </div>
                                )
                            ) : (
                                <div className="text-gray-500 font-bold uppercase tracking-widest flex flex-col items-center gap-4">
                                    <i className="fas fa-book-open text-4xl opacity-50"></i>
                                    Select a Quiz from the Library
                                </div>
                            )}
                        </div>
                    )}
                </div>
            );
        };

        const FlashcardsView = ({ flashcards, backend, refreshCards, flatGoals }) => {
            const [activeTab, setActiveTab] = useState('library');
            const [isFlipped, setIsFlipped] = useState(false);
            const [currentIndex, setCurrentIndex] = useState(0);
            const [f, setF] = useState(""); const [b, setB] = useState(""); const [c, setC] = useState("");
            const [folder, setFolder] = useState("Uncategorized"); const [color, setColor] = useState("#3b82f6");

            const activeDeckCards = flashcards; 
            const card = activeDeckCards && activeDeckCards.length > 0 ? activeDeckCards[currentIndex] : null;

            const addCard = () => {
                backend.request(JSON.stringify({action: 'manage_flashcard', sub: 'add', front: f, back: b, deck: "Main", course: c || "General", folder: folder, color: color})).then(res => {
                    refreshCards(JSON.parse(res).flashcards); setF(""); setB("");
                });
            };
            const nextCard = () => { setIsFlipped(false); setTimeout(() => setCurrentIndex((currentIndex + 1) % activeDeckCards.length), 300); };
            const delCard = (id) => { backend.request(JSON.stringify({action: 'manage_flashcard', sub: 'delete', id: id})).then(res => { refreshCards(JSON.parse(res).flashcards); setIsFlipped(false); setCurrentIndex(0); }); };

            return (
                <div className="flex flex-col h-full fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Flashcards</h2>
                    </div>

                    <div className="flex gap-6 border-b border-white/10 mb-6 shrink-0">
                        <button onClick={() => setActiveTab('library')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'library' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Library & Create</button>
                        <button onClick={() => setActiveTab('study')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'study' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Review Mode</button>
                    </div>

                    {activeTab === 'library' && (
                        <div className="flex flex-col gap-6 h-full overflow-hidden">
                            <div className="glass-panel p-4 rounded-xl flex flex-col gap-3 shrink-0">
                                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1">Create Flashcard</h3>
                                <div className="flex flex-wrap sm:flex-nowrap gap-2">
                                    <select className="glass-input px-3 py-2 rounded text-xs font-bold w-full sm:w-48" value={c} onChange={e=>setC(e.target.value)}><option value="">Goal / Course...</option>{flatGoals.map(g=><option key={g} value={g}>{g}</option>)}</select>
                                    <input type="text" placeholder="Folder..." value={folder} onChange={e=>setFolder(e.target.value)} className="glass-input px-3 py-2 rounded text-xs font-bold w-32" />
                                    <input type="color" value={color} onChange={e=>setColor(e.target.value)} className="w-8 h-8 rounded cursor-pointer border-0 p-0 self-center" />
                                </div>
                                <div className="flex flex-wrap sm:flex-nowrap gap-2">
                                    <input type="text" placeholder="FRONT..." className="glass-input flex-grow px-4 py-2 rounded text-sm min-w-[150px]" value={f} onChange={e=>setF(e.target.value)} />
                                    <input type="text" placeholder="BACK..." className="glass-input flex-grow px-4 py-2 rounded text-sm min-w-[150px]" value={b} onChange={e=>setB(e.target.value)} />
                                    <button onClick={addCard} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 w-full sm:w-auto">ADD</button>
                                </div>
                            </div>
                            
                            <div className="glass-panel flex-grow p-4 overflow-y-auto">
                                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4 border-b border-white/10 pb-1">ALL CARDS</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {flashcards && flashcards.map(c => (
                                        <div key={c.id} className="flex flex-col p-3 bg-white/5 border border-white/10 rounded group relative">
                                            <div className="flex items-center gap-2 mb-2">
                                                <div className="w-2 h-2 rounded-full" style={{backgroundColor: c.color}}></div>
                                                <span className="text-[9px] text-gray-500 font-bold uppercase tracking-wider">{c.folder} / {c.course}</span>
                                                <i onClick={() => delCard(c.id)} className="fas fa-trash text-red-500 ml-auto opacity-0 group-hover:opacity-100 cursor-pointer hover:scale-110 transition"></i>
                                            </div>
                                            <div className="text-xs font-bold text-white truncate mb-1">F: {c.front}</div>
                                            <div className="text-[10px] text-gray-400 truncate">B: {c.back}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'study' && (
                        <div className="flex-grow flex flex-col items-center justify-center perspective-1000 p-4 relative">
                            {card ? (
                                <div className={`relative w-full max-w-2xl h-64 sm:h-80 cursor-pointer transition-all duration-700 transform-style-3d ${isFlipped ? 'rotate-y-180' : ''}`} onClick={() => setIsFlipped(!isFlipped)}>
                                    <div className="absolute inset-0 glass-panel rounded-2xl flex flex-col justify-center items-center p-8 backface-hidden shadow-[0_20px_50px_rgba(0,0,0,0.5)] border-t-2" style={{borderTopColor: card.color}}>
                                        <span className="absolute top-4 left-4 text-[10px] font-bold tracking-widest text-gray-500 uppercase">{card.folder} / {card.course}</span>
                                        <span className="absolute bottom-4 left-4 text-[10px] font-bold tracking-widest text-gray-600 uppercase">FRONT</span>
                                        <h2 className="text-xl sm:text-3xl font-serif text-white tracking-wider text-center">{card.front}</h2>
                                    </div>
                                    <div className="absolute inset-0 glass-panel-darker rounded-2xl flex flex-col justify-center items-center p-8 backface-hidden rotate-y-180 shadow-[0_20px_50px_rgba(0,0,0,0.5)] border-b-2 border-b-green-500/30 overflow-y-auto">
                                        <span className="absolute bottom-4 right-4 text-[10px] font-bold tracking-widest text-gray-600 uppercase">BACK</span>
                                        <p className="text-sm sm:text-lg text-gray-200 text-center leading-relaxed mt-4">{card.back}</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-gray-500 font-bold uppercase flex flex-col items-center gap-4 tracking-widest">
                                    <i className="fas fa-layer-group text-4xl opacity-50"></i>
                                    No Flashcards Built Yet
                                </div>
                            )}
                            {card && (
                                <div className="flex gap-4 mt-12 shrink-0">
                                    <button onClick={() => setIsFlipped(!isFlipped)} className="glass-button px-8 py-3 rounded-lg text-xs font-bold tracking-widest text-gray-300 uppercase shadow-lg transition">FLIP</button>
                                    <button onClick={nextCard} className="glass-button px-8 py-3 rounded-lg text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600 shadow-lg transition">NEXT</button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            );
        };

        const NotesView = ({ notes, backend, refreshNotes, flatGoals }) => {
            const [activeNoteId, setActiveNoteId] = useState(null);
            const [title, setTitle] = useState("");
            const [content, setContent] = useState("");
            const [course, setCourse] = useState("");
            const [folder, setFolder] = useState("Uncategorized");
            const [color, setColor] = useState("#3b82f6");

            const handleSave = () => {
                backend.request(JSON.stringify({action: 'manage_note', sub: 'save', id: activeNoteId, title: title || "Untitled Note", content, course: course || "General", folder: folder, color: color})).then(res => {
                    refreshNotes(JSON.parse(res).notes);
                });
            };

            const selectNote = (n) => { setActiveNoteId(n.id); setTitle(n.title); setContent(n.content); setCourse(n.course); setFolder(n.folder); setColor(n.color); };
            const newNote = () => { setActiveNoteId(null); setTitle(""); setContent(""); setCourse(""); setFolder("Uncategorized"); setColor("#3b82f6"); };

            return (
                <div className="flex flex-col h-full fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Markdown Notes</h2>
                    </div>
                    <div className="flex flex-col md:flex-row gap-4 flex-grow overflow-hidden">
                        
                        <div className="w-full md:w-1/4 glass-panel p-4 flex flex-col gap-2 overflow-y-auto">
                            <button onClick={newNote} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-green-300 uppercase shadow-lg mb-2 border border-green-500/30">+ New Note</button>
                            {notes && notes.map(n => (
                                <div key={n.id} onClick={() => selectNote(n)} className={`p-3 rounded cursor-pointer border text-sm transition-all group relative ${activeNoteId === n.id ? 'bg-blue-600/30 border-blue-400 text-white' : 'bg-white/5 border-white/10 hover:bg-white/10 text-gray-300'}`}>
                                    <div className="flex items-center gap-2 mb-1">
                                        <div className="w-2 h-2 rounded-full" style={{backgroundColor: n.color}}></div>
                                        <div className="text-[9px] font-bold uppercase tracking-widest text-gray-500">{n.folder}</div>
                                    </div>
                                    <div className="font-bold truncate">{n.title}</div>
                                    <i onClick={(e) => {e.stopPropagation(); backend.request(JSON.stringify({action: 'manage_note', sub: 'delete', id: n.id})).then(res => refreshNotes(JSON.parse(res).notes));}} className="fas fa-trash text-red-500 absolute top-3 right-3 opacity-0 group-hover:opacity-100 hover:scale-110 transition"></i>
                                </div>
                            ))}
                        </div>

                        <div className="w-full md:w-1/2 glass-panel p-0 flex flex-col overflow-hidden">
                            <div className="flex flex-col gap-2 p-3 border-b border-white/10 bg-black/40 text-xs font-mono text-gray-400 shrink-0">
                                <div className="flex flex-wrap gap-2">
                                    <input type="text" placeholder="Title..." className="glass-input px-2 py-1.5 rounded w-full sm:w-auto flex-grow font-bold text-white" value={title} onChange={e=>setTitle(e.target.value)} />
                                    <button onClick={handleSave} className="glass-button px-6 py-1.5 rounded font-bold text-white tracking-widest uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600 transition">Save</button>
                                </div>
                                <div className="flex flex-wrap gap-2 items-center">
                                    <select className="glass-input px-2 py-1 rounded w-32" value={course} onChange={e=>setCourse(e.target.value)}><option value="">Goal / Course...</option>{flatGoals.map(g=><option key={g} value={g}>{g}</option>)}</select>
                                    <input type="text" placeholder="Folder..." className="glass-input px-2 py-1 rounded w-24" value={folder} onChange={e=>setFolder(e.target.value)} />
                                    <input type="color" value={color} onChange={e=>setColor(e.target.value)} className="w-6 h-6 rounded cursor-pointer border-0 p-0" />
                                    <div className="ml-auto flex gap-1">
                                        <button onClick={() => setContent(prev => prev + '**Bold**')} className="w-6 h-6 bg-white/10 rounded hover:bg-white/20 transition"><i className="fas fa-bold"></i></button>
                                        <button onClick={() => setContent(prev => prev + '*Italic*')} className="w-6 h-6 bg-white/10 rounded hover:bg-white/20 transition"><i className="fas fa-italic"></i></button>
                                        <button onClick={() => setContent(prev => prev + '\n```python\n# Code\n```\n')} className="w-6 h-6 bg-white/10 rounded hover:bg-white/20 transition"><i className="fas fa-code"></i></button>
                                    </div>
                                </div>
                            </div>
                            <textarea className="w-full flex-grow bg-transparent text-gray-200 p-4 outline-none resize-none font-mono text-sm leading-relaxed custom-scrollbar" value={content} onChange={e=>setContent(e.target.value)} placeholder="Type markdown here..."></textarea>
                        </div>

                        <div className="w-full md:w-1/4 glass-panel-darker p-0 flex flex-col overflow-hidden">
                            <div className="p-2 border-b border-white/10 bg-black/60 text-xs font-mono text-gray-400 shrink-0 font-bold tracking-widest uppercase">Live Preview</div>
                            <div className="w-full flex-grow p-6 overflow-y-auto text-gray-200 prose prose-invert max-w-none custom-scrollbar" dangerouslySetInnerHTML={{__html: marked.parse(content || "*Nothing to preview.*")}}></div>
                        </div>
                    </div>
                </div>
            );
        };

        const SettingsView = ({ settings, setSettings, backend }) => {
            const handleChange = (k, v) => setSettings(prev => ({...prev, [k]: v}));
            const saveSettings = () => backend.request(JSON.stringify({action: 'save_settings', data: settings}));
            const openFileDialog = (key) => { backend.request(JSON.stringify({action: 'open_file_dialog'})).then(res => { const data = JSON.parse(res); if(data.path) handleChange(key, data.path); }); };
            const [showProcessModal, setShowProcessModal] = useState(false);
            const [confirmReset, setConfirmReset] = useState(false);
            const handleReset = () => {
                backend.request(JSON.stringify({action: 'reset_data'})).then(() => {
                    setConfirmReset(false);
                });
            };

            return (
                <div className="flex flex-col h-full fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Settings</h2>
                        <div className="flex gap-4 items-center">
                            {!confirmReset ? (
                                <button onClick={() => setConfirmReset(true)} className="glass-button px-4 py-2 rounded text-[10px] font-bold tracking-widest uppercase bg-red-900/30 text-red-400 border border-red-500/30 hover:bg-red-900/60 transition-colors">
                                    <i className="fas fa-radiation mr-2"></i> Reset Data
                                </button>
                            ) : (
                                <div className="flex gap-2 items-center bg-red-900/50 p-1 rounded-lg border border-red-500/50">
                                    <span className="text-red-300 text-[10px] font-bold uppercase tracking-widest px-2">Are you sure?</span>
                                    <button onClick={handleReset} className="glass-button px-4 py-1 rounded text-[10px] font-bold tracking-widest uppercase bg-red-600 text-white hover:bg-red-500">Yes, Delete</button>
                                    <button onClick={() => setConfirmReset(false)} className="glass-button px-4 py-1 rounded text-[10px] font-bold tracking-widest uppercase text-gray-300">Cancel</button>
                                </div>
                            )}
                            <button onClick={saveSettings} className="glass-button px-6 py-2 rounded text-xs font-bold text-white uppercase bg-blue-600/30 hover:bg-blue-600 border-blue-500/50 shadow-lg">Apply All Settings</button>
                        </div>
                    </div>
                    <div className="glass-panel p-6 flex-grow overflow-y-auto custom-scrollbar">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6 max-w-4xl">
{/* App Monitoring */}
<div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">App Monitoring</div>

<div className="md:col-span-2 flex flex-col gap-3">
    <div className="flex items-center gap-4">
        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Enable App Monitoring</label>
        <input type="checkbox" checked={settings.app_monitoring_enabled || false} 
               onChange={e => {
                   const checked = e.target.checked;
                   handleChange('app_monitoring_enabled', checked);
                   backend.request(JSON.stringify({action: 'set_app_monitoring', enabled: checked}));
               }} 
               className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
    </div>
    
    <div className="flex items-center gap-4">
        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Auto-Block Disallowed Apps</label>
        <input type="checkbox" checked={settings.auto_block || false} 
               onChange={e => {
                   const checked = e.target.checked;
                   handleChange('auto_block', checked);
                   backend.request(JSON.stringify({action: 'set_auto_block', enabled: checked}));
               }} 
               className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-red-500" />
    </div>
    
    <div className="flex gap-3 mt-2">
        <button onClick={() => {
            backend.request(JSON.stringify({action: 'get_processes'})).then(res => {
                const data = JSON.parse(res);
                if (data.processes && data.processes.length > 0) {
                    setSettings(prev => ({...prev, process_list: data.processes}));
                    setShowProcessModal(true);
                } else {
                    alert('No processes found.\n\nInstall psutil for better monitoring:\npip install psutil');
                }
            });
        }} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-green-600/30 border-green-500/50 hover:bg-green-600">
            <i className="fas fa-sync mr-2"></i> Refresh Process List
        </button>
        <button onClick={() => {
            backend.request(JSON.stringify({action: 'check_current_distractions'})).then(res => {
                const data = JSON.parse(res);
                if (data.distractions && data.distractions.length > 0) {
                    let msg = '⚠️ Distracting Apps Found:\n\n';
                    data.distractions.forEach((p, i) => {
                        msg += `${i+1}. ${p.name} (PID: ${p.pid})\n`;
                    });
                    alert(msg);
                } else {
                    alert('✅ No distracting apps found!');
                }
            });
        }} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">
            <i className="fas fa-search mr-2"></i> Check Distractions
        </button>
    </div>
    
    {/* Current allowed/blocked lists display */}
    <div className="flex gap-6 mt-2">
        <div className="flex-1">
            <label className="text-[10px] font-bold text-green-400 uppercase tracking-widest">Allowed Apps ({settings.allowed_apps?.length || 0})</label>
            <div className="flex flex-wrap gap-1 mt-1 max-h-20 overflow-y-auto">
                {settings.allowed_apps && settings.allowed_apps.length > 0 ? (
                    settings.allowed_apps.map((app, i) => (
                        <span key={i} className="text-xs bg-green-900/30 text-green-400 px-2 py-0.5 rounded border border-green-500/30 flex items-center gap-1">
                            {app}
                            <button onClick={() => {
                                const newList = settings.allowed_apps.filter((_, idx) => idx !== i);
                                handleChange('allowed_apps', newList);
                                backend.request(JSON.stringify({action: 'set_allowed_apps', apps: newList}));
                            }} className="text-red-400 hover:text-red-300">
                                <i className="fas fa-times text-[8px]"></i>
                            </button>
                        </span>
                    ))
                ) : (
                    <span className="text-xs text-gray-500 italic">No allowed apps configured</span>
                )}
            </div>
        </div>
        <div className="flex-1">
            <label className="text-[10px] font-bold text-red-400 uppercase tracking-widest">Blocked Apps ({settings.blocked_apps?.length || 0})</label>
            <div className="flex flex-wrap gap-1 mt-1 max-h-20 overflow-y-auto">
                {settings.blocked_apps && settings.blocked_apps.length > 0 ? (
                    settings.blocked_apps.map((app, i) => (
                        <span key={i} className="text-xs bg-red-900/30 text-red-400 px-2 py-0.5 rounded border border-red-500/30 flex items-center gap-1">
                            {app}
                            <button onClick={() => {
                                const newList = settings.blocked_apps.filter((_, idx) => idx !== i);
                                handleChange('blocked_apps', newList);
                                backend.request(JSON.stringify({action: 'set_blocked_apps', apps: newList}));
                            }} className="text-red-400 hover:text-red-300">
                                <i className="fas fa-times text-[8px]"></i>
                            </button>
                        </span>
                    ))
                ) : (
                    <span className="text-xs text-gray-500 italic">No blocked apps configured</span>
                )}
            </div>
        </div>
    </div>
    
    <div className="text-[10px] text-gray-500 mt-1">
        <i className="fas fa-info-circle mr-1"></i> 
        {settings.app_monitoring_enabled ? 
            '✅ App monitoring is active. Disallowed apps will trigger distractions.' : 
            '❌ App monitoring is disabled. Enable it above to start monitoring.'}
    </div>
</div>

{/* Process Selection Modal */}
{showProcessModal && (
    <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4 backdrop-blur-md">
        <div className="glass-panel p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-white font-bold text-xl">📋 Running Applications</h3>
                <button onClick={() => setShowProcessModal(false)} className="text-gray-400 hover:text-white">
                    <i className="fas fa-times text-xl"></i>
                </button>
            </div>
            
            <div className="flex gap-3 mb-4">
                <button onClick={() => {
                    const allChecked = document.querySelectorAll('.process-checkbox');
                    allChecked.forEach(cb => cb.checked = true);
                }} className="glass-button px-3 py-1 rounded text-xs font-bold text-green-300 uppercase">
                    Select All
                </button>
                <button onClick={() => {
                    const allChecked = document.querySelectorAll('.process-checkbox');
                    allChecked.forEach(cb => cb.checked = false);
                }} className="glass-button px-3 py-1 rounded text-xs font-bold text-red-300 uppercase">
                    Deselect All
                </button>
                <button onClick={() => {
                    const checkedBoxes = document.querySelectorAll('.process-checkbox:checked');
                    const selectedApps = [];
                    checkedBoxes.forEach(cb => {
                        const appName = cb.getAttribute('data-app');
                        const action = document.querySelector(`[data-action="${appName}"]`).value;
                        if (action === 'allow') {
                            const current = settings.allowed_apps || [];
                            if (!current.includes(appName)) {
                                handleChange('allowed_apps', [...current, appName]);
                                backend.request(JSON.stringify({action: 'set_allowed_apps', apps: [...current, appName]}));
                            }
                        } else if (action === 'block') {
                            const current = settings.blocked_apps || [];
                            if (!current.includes(appName)) {
                                handleChange('blocked_apps', [...current, appName]);
                                backend.request(JSON.stringify({action: 'set_blocked_apps', apps: [...current, appName]}));
                            }
                        }
                    });
                    setShowProcessModal(false);
                    alert('✅ App rules updated!');
                }} className="glass-button px-4 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">
                    Apply Rules
                </button>
            </div>
            
            <div className="flex flex-col gap-1 max-h-60 overflow-y-auto">
                {settings.process_list && settings.process_list.map((p, i) => {
                    const isAllowed = settings.allowed_apps?.includes(p.name);
                    const isBlocked = settings.blocked_apps?.includes(p.name);
                    return (
                        <div key={i} className="flex items-center gap-3 p-2 bg-white/5 rounded border border-white/10 hover:bg-white/10 transition">
                            <input type="checkbox" className="process-checkbox" data-app={p.name} 
                                   defaultChecked={isAllowed || isBlocked} />
                            <span className="text-sm text-gray-300 flex-grow">{p.name}</span>
                            <span className="text-[10px] text-gray-500">PID: {p.pid}</span>
                            <select data-action={p.name} className="glass-input text-xs px-2 py-1 rounded w-24" defaultValue={isAllowed ? 'allow' : isBlocked ? 'block' : 'ignore'}>
                                <option value="ignore">Ignore</option>
                                <option value="allow">✅ Allow</option>
                                <option value="block">🚫 Block</option>
                            </select>
                            {isAllowed && <span className="text-xs text-green-400">✅</span>}
                            {isBlocked && <span className="text-xs text-red-400">🚫</span>}
                        </div>
                    );
                })}
            </div>
        </div>
    </div>
)}


{/* Git Sync Status */}
<div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1">Git Sync Status</div>

<div className="md:col-span-2 flex flex-col gap-3">
    <div className="flex items-center gap-4">
        <div className={`w-3 h-3 rounded-full ${settings.git_status === 'connected' ? 'bg-green-500 animate-pulse' : 
                                              settings.git_status === 'error' ? 'bg-red-500' : 
                                              settings.git_status === 'syncing' ? 'bg-yellow-500 animate-pulse' : 
                                              'bg-gray-500'}`}>
        </div>
        <span className="text-sm font-medium text-gray-300">
            {settings.git_status === 'connected' ? '✅ Connected to GitHub' :
             settings.git_status === 'syncing' ? '🔄 Syncing...' :
             settings.git_status === 'error' ? '❌ Sync Error' :
             '⏸️ Not Connected'}
        </span>
        <span className="text-xs text-gray-500">
            {settings.git_last_sync ? `Last sync: ${settings.git_last_sync}` : 'Never synced'}
        </span>
    </div>
    
    <div className="flex gap-3">
        <button onClick={() => {
            setSettings(prev => ({...prev, git_status: 'syncing'}));
            backend.request(JSON.stringify({action: 'get_sync_status'})).then(res => {
                const data = JSON.parse(res);
                setSettings(prev => ({
                    ...prev, 
                    git_status: data.enabled ? 'connected' : 'error',
                    git_last_sync: new Date().toLocaleString()
                }));
            }).catch(() => {
                setSettings(prev => ({...prev, git_status: 'error'}));
            });
        }} className="glass-button px-4 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">
            <i className="fas fa-sync mr-2"></i> Refresh Status
        </button>
<button onClick={() => {
    backend.request(JSON.stringify({action: 'sync_now'})).then(res => {
        const data = JSON.parse(res);
        if (data.status === 'started') {
            alert('🔄 Sync started... Check terminal for progress');
        } else {
            alert('❌ Failed to start sync: ' + (data.message || 'Unknown error'));
        }
    }).catch(err => {
        alert('❌ Error: ' + err);
    });
}} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">
    <i className="fas fa-sync mr-2"></i> Sync Now
</button>
    </div>
    
<div className="flex flex-col gap-1 text-[10px] text-gray-500">
    <div><span className="font-bold">Device ID:</span> {settings.device_id || 'Not set'}</div>
    <div><span className="font-bold">Repository:</span> {settings.sync_repo_url ? settings.sync_repo_url.split('/').slice(-2).join('/') : 'Not configured'}</div>
    <div><span className="font-bold">Last Sync:</span> {settings.git_last_sync || 'Never'}</div>
    {settings.git_status === 'connected' && (
        <div className="text-green-400">✓ GitHub connection verified</div>
    )}
    {settings.git_status === 'syncing' && (
        <div className="text-yellow-400 animate-pulse">🔄 Syncing in progress...</div>
    )}
    {settings.git_status === 'error' && (
        <div className="text-red-400">❌ Connection error - check token and repo</div>
    )}
</div>
</div>
                            {/* File & Device Sync */}
                            <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1">File & Device Sync</div>
                            
                            <div className="md:col-span-2 flex flex-col gap-3">
                                <div className="flex items-center gap-4">
                                    <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Device ID</label>
                                    <span className="text-xs font-mono text-blue-400 bg-black/40 px-3 py-1 rounded border border-white/10">{settings.device_id || 'Loading...'}</span>
                                </div>
                                
                                <div className="flex items-center gap-4">
                                    <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Enable Sync</label>
                                    <input type="checkbox" checked={settings.sync_enabled || false} 
                                           onChange={e => handleChange('sync_enabled', e.target.checked)} 
                                           className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
                                </div>
                                
                                <div className="flex flex-col gap-1">
                                    <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">GitHub Repository URL</label>
                                    <input type="text" value={settings.sync_repo_url || ''} 
                                           onChange={e => handleChange('sync_repo_url', e.target.value)} 
                                           className="glass-input p-2.5 rounded text-sm w-full" 
                                           placeholder="https://github.com/username/repo.git" />
                                </div>
                                
<div className="flex flex-col gap-1">
    <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">GitHub Token Status</label>
    <div className="flex items-center gap-3 p-2 bg-black/40 rounded border border-white/10">
        {settings.has_token ? (
            <span className="text-green-400">
                <i className="fas fa-check-circle mr-2"></i> ✅ Token configured in environment
            </span>
        ) : (
            <span className="text-yellow-400">
                <i className="fas fa-exclamation-triangle mr-2"></i> ⚠️ Token not set. Add GITHUB_TOKEN to .env file
            </span>
        )}
        <button onClick={() => {
            alert(`To set your GitHub token:\n\n1. Create a .env file in the project folder\n2. Add: GITHUB_TOKEN=your_token_here\n3. Restart the app\n\nGenerate token at: https://github.com/settings/tokens\nScope required: repo`);
        }} className="glass-button px-3 py-1 rounded text-xs text-gray-400 hover:text-white">
            <i className="fas fa-question-circle"></i>
        </button>
    </div>
    <div className="text-[10px] text-gray-500">
        <i className="fas fa-info-circle mr-1"></i> 
        Token is stored in .env file (not committed to Git)
    </div>
</div>
                                
                                <div className="flex flex-col gap-1">
                                    <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Sync Interval (seconds)</label>
                                    <input type="number" value={settings.sync_interval || 3600} 
                                           onChange={e => handleChange('sync_interval', parseInt(e.target.value))} 
                                           className="glass-input p-2.5 rounded text-sm w-32" />
                                </div>
                            </div>
                            
                            {/* Mapped Folders */}
                            <div className="md:col-span-2 flex flex-col gap-2">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Mapped Folders (Sync & Share)</label>
                                
                                <div className="flex gap-2">
                                    <input type="text" id="folder-input" placeholder="C:/Users/... or /Users/..." 
                                           className="glass-input p-2.5 rounded text-sm flex-grow" />
                                    <button onClick={() => {
                                        const input = document.getElementById('folder-input');
                                        if (input.value) {
                                            backend.request(JSON.stringify({action: 'map_folder', path: input.value})).then(() => {
                                                input.value = '';
                                                backend.request(JSON.stringify({action: 'get_mapped_folders'})).then(res => {
                                                    const folders = JSON.parse(res);
                                                    setSettings(prev => ({...prev, mapped_folders: folders.folders}));
                                                });
                                            });
                                        }
                                    }} className="glass-button px-4 py-2 rounded text-xs font-bold text-green-300 uppercase border border-green-500/30 hover:bg-green-900/30">
                                        <i className="fas fa-plus mr-1"></i> Add
                                    </button>
                                    <button onClick={() => {
                                        backend.request(JSON.stringify({action: 'open_folder_dialog'})).then(res => {
                                            const data = JSON.parse(res);
                                            if (data.path) {
                                                document.getElementById('folder-input').value = data.path;
                                            }
                                        });
                                    }} className="glass-button px-4 py-2 rounded text-xs font-bold text-blue-300 uppercase border border-blue-500/30 hover:bg-blue-900/30">
                                        <i className="fas fa-folder-open mr-1"></i> Browse
                                    </button>
                                </div>
                                
                                <div className="flex flex-wrap gap-2 mt-2 max-h-40 overflow-y-auto p-2 bg-black/20 rounded-lg border border-white/5">
                                    {settings.mapped_folders && settings.mapped_folders.length > 0 ? (
                                        settings.mapped_folders.map((path, i) => (
                                            <span key={i} className="flex items-center gap-2 bg-white/10 px-3 py-1.5 rounded-full text-xs border border-white/10 group hover:bg-white/20 transition-all">
                                                <i className="fas fa-folder text-yellow-400 text-xs"></i>
                                                <span className="font-mono text-gray-300 truncate max-w-xs" title={path}>{path}</span>
                                                <button onClick={() => {
                                                    backend.request(JSON.stringify({action: 'unmap_folder', path: path})).then(() => {
                                                        setSettings(prev => ({
                                                            ...prev, 
                                                            mapped_folders: prev.mapped_folders.filter(p => p !== path)
                                                        }));
                                                    });
                                                }} className="text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-all">
                                                    <i className="fas fa-times"></i>
                                                </button>
                                            </span>
                                        ))
                                    ) : (
                                        <span className="text-xs text-gray-500 italic">No folders mapped. Add a folder to sync across devices.</span>
                                    )}
                                </div>
                                <div className="text-[10px] text-gray-500 mt-1">
                                    <i className="fas fa-info-circle mr-1"></i> 
                                    Files in mapped folders will be synced to all devices via GitHub
                                </div>
                            </div>
                            
                            {/* Sync Buttons */}
                            <div className="md:col-span-2 flex gap-3 mt-2">
                                <button onClick={() => backend.request(JSON.stringify({action: 'sync_now'}))}
                                    className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">
                                    <i className="fas fa-sync mr-2"></i> Sync Now
                                </button>
                                <button onClick={() => backend.request(JSON.stringify({action: 'get_sync_status'})).then(res => {
                                    const data = JSON.parse(res);
                                    alert(`Sync Status:\nEnabled: ${data.enabled}\nDevice: ${data.device_id}\nInterval: ${data.interval}s`);
                                })}
                                    className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-gray-300 uppercase border-white/10 hover:bg-white/5">
                                    <i className="fas fa-info-circle mr-2"></i> Status
                                </button>
                                <button onClick={() => backend.request(JSON.stringify({action: 'export_data'}))}
                                    className="glass-button px-4 py-2 rounded text-[10px] font-bold tracking-widest uppercase bg-green-900/30 text-green-400 border border-green-500/30 hover:bg-green-900/60">
                                    <i className="fas fa-file-export mr-2"></i> Export
                                </button>
                                <button onClick={() => backend.request(JSON.stringify({action: 'import_data'}))}
                                    className="glass-button px-4 py-2 rounded text-[10px] font-bold tracking-widest uppercase bg-yellow-900/30 text-yellow-400 border border-yellow-500/30 hover:bg-yellow-900/60">
                                    <i className="fas fa-file-import mr-2"></i> Import
                                </button>
                            </div>

                            {/* Visual Engine Settings */}
                            <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Visual Engine & Theme</div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Background Image URL / Path</label>
                                <div className="flex gap-2">
                                    <input type="text" value={settings.bg_image_path || ''} onChange={e => handleChange('bg_image_path', e.target.value)} className="glass-input p-2.5 rounded text-sm flex-grow" placeholder="https://..." />
                                    <button onClick={() => openFileDialog('bg_image_path')} className="glass-button px-4 rounded text-xs"><i className="fas fa-folder-open"></i></button>
                                </div>
                            </div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Global Font Family / Path</label>
                                <div className="flex gap-2">
                                    <input type="text" value={settings.font_family || 'Inter'} onChange={e => handleChange('font_family', e.target.value)} className="glass-input p-2.5 rounded text-sm flex-grow" />
                                    <button onClick={() => openFileDialog('custom_font_path')} className="glass-button px-4 rounded text-xs"><i className="fas fa-folder-open"></i></button>
                                </div>
                            </div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Global Font Color</label>
                                <input type="color" value={settings.font_color || '#e2e8f0'} onChange={e => handleChange('font_color', e.target.value)} className="w-full h-10 rounded cursor-pointer border-0 p-0" />
                            </div>

                            {/* Horology Settings */}
                            <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Horology & Clock Styles</div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Clock Style</label>
                                <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_style || 'Analog Classic'} onChange={e => handleChange('clock_style', e.target.value)}><option>Analog Classic</option><option>Analog Minimal</option><option>Digital LED</option></select>
                            </div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Case Shape</label>
                                <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_case_shape || 'Round'} onChange={e => handleChange('clock_case_shape', e.target.value)}><option>Round</option><option>Square</option><option>Cushion</option><option>Tonneau</option></select>
                            </div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Bezel</label>
                                <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_bezel || 'Plain'} onChange={e => handleChange('clock_bezel', e.target.value)}><option>Plain</option><option>Fluted</option><option>Diver</option><option>GMT (Pepsi)</option><option>Coin-Edge</option></select>
                            </div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Hands Style</label>
                                <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_hands || 'Classic'} onChange={e => handleChange('clock_hands', e.target.value)}><option>Classic</option><option>Spade</option><option>Breguet</option><option>Dauphine</option><option>Serpentine</option><option>Mercedes</option><option>Sword</option><option>Arrow</option></select>
                            </div>

                            {/* System Behavior */}
                            <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">System & Behavior</div>
                            {/* Quiet Mode */}
<div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Work Mode</div>

<div className="md:col-span-2 flex flex-col gap-3">
    <div className="flex items-center gap-4">
        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Quiet Mode</label>
        <input type="checkbox" checked={settings.quiet_mode || false} 
               onChange={e => {
                   const checked = e.target.checked;
                   handleChange('quiet_mode', checked);
                   backend.request(JSON.stringify({action: 'set_quiet_mode', enabled: checked}));
               }} 
               className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
        <span className="text-xs text-gray-400">
            {settings.quiet_mode ? '🔇 Disables webcam, sounds, and speech' : '🔊 Full mode with webcam & sounds'}
        </span>
    </div>
    
    <div className="flex gap-3 mt-2">
        <button onClick={() => {
            backend.request(JSON.stringify({action: 'get_processes'})).then(res => {
                const data = JSON.parse(res);
                if (data.processes && data.processes.length > 0) {
                    let msg = '🔄 Running Processes:\n\n';
                    data.processes.forEach((p, i) => {
                        msg += `${i+1}. ${p.name} (PID: ${p.pid}) - CPU: ${p.cpu.toFixed(1)}% Mem: ${p.memory.toFixed(1)}%\n`;
                    });
                    alert(msg);
                } else {
                    alert('No processes found or psutil not installed.\n\nInstall with: pip install psutil');
                }
            });
        }} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-green-600/30 border-green-500/50 hover:bg-green-600">
            <i className="fas fa-list mr-2"></i> Show Processes
        </button>
        <span className="text-[10px] text-gray-500 self-center">
            <i className="fas fa-info-circle mr-1"></i> 
            Lists top processes by CPU usage
        </span>
    </div>
</div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Vision Sample Interval (ms)</label>
                                <input type="number" value={settings.vision_sample_interval || 30} onChange={e => handleChange('vision_sample_interval', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                            </div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Beep Frequency (seconds)</label>
                                <input type="number" value={settings.beep_freq || 3} onChange={e => handleChange('beep_freq', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                            </div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Panel Opacity</label>
                                <input type="range" min="50" max="255" value={settings.panel_opacity || 180} onChange={e => handleChange('panel_opacity', e.target.value)} className="w-full accent-blue-500 mt-2" />
                            </div>
                            <div className="flex flex-col gap-1">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Vision Mode</label>
                                <select className="glass-input p-2.5 rounded text-sm" value={settings.vision_mode || 'Strict (Face & Eyes)'} onChange={e => handleChange('vision_mode', e.target.value)}><option>Strict (Face & Eyes)</option><option>Visible (Face Only)</option></select>
                            </div>
                            <div className="flex flex-col gap-1 md:col-span-2">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Distraction Spoken Phrase</label>
                                <input type="text" value={settings.speech_dist || ''} onChange={e => handleChange('speech_dist', e.target.value)} className="glass-input p-2.5 rounded text-sm" />
                            </div>
                            <div className="flex flex-col gap-1 md:col-span-2">
                                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Completion Spoken Phrase</label>
                                <input type="text" value={settings.speech_comp || ''} onChange={e => handleChange('speech_comp', e.target.value)} className="glass-input p-2.5 rounded text-sm" />
                            </div>
                        </div>
                    </div>
                </div>
            );
        };

        const App = () => {
            const [currentView, setCurrentView] = useState('dashboard');
            const [backend, setBackend] = useState(null);
            
            const [courses, setCourses] = useState([]);
            const [goals, setGoals] = useState([]);
            const [flatGoals, setFlatGoals] = useState([]);
            const [heatmap, setHeatmap] = useState([]);
            const [settings, setSettings] = useState({
                // ... existing settings
                git_status: 'unknown',
                git_last_sync: null,
                process_list: [],
            });
            const [metrics, setMetrics] = useState(null);
            const [habits, setHabits] = useState([]);
            const [habitLogs, setHabitLogs] = useState([]);
            const [flashcards, setFlashcards] = useState([]);
            const [quizzes, setQuizzes] = useState([]);
            const [queue, setQueue] = useState([]);
            const [notes, setNotes] = useState([]);
            
            const [layout, setLayout] = useState(DEFAULT_LAYOUT);
            const [isEditingLayout, setIsEditingLayout] = useState(false);
            
            const [timerState, setTimerState] = useState({ is_running: false, time_str: "25:00", progress: 0, distractions: 0, course: "General" });
            const [camFeed, setCamFeed] = useState(null);
            const [clockFeed, setClockFeed] = useState(null);

            useEffect(() => {
                if (typeof qt !== 'undefined') {
                    new QWebChannel(qt.webChannelTransport, (channel) => {
                        const py = channel.objects.backend;
                        setBackend(py);
                        
                        py.state_update.connect((state_json) => { setTimerState(JSON.parse(state_json)); });
                        py.video_feed.connect((b64) => { setCamFeed(`data:image/jpeg;base64,${b64}`); });
                        py.clock_feed.connect((b64) => { setClockFeed(b64); });

                        py.request(JSON.stringify({action: 'init'})).then(res => {
                            const data = JSON.parse(res);
                            if (data.courses) setCourses(data.courses);
                            if (data.goals) setGoals(data.goals);
                            if (data.flat_goals) setFlatGoals(data.flat_goals);
                            if (data.heatmap) setHeatmap(data.heatmap);
                            if (data.settings) setSettings(data.settings);
                            if (data.habits) setHabits(data.habits);
                            if (data.habit_logs) setHabitLogs(data.habit_logs);
                            if (data.flashcards) setFlashcards(data.flashcards);
                            if (data.quizzes) setQuizzes(data.quizzes);
                            if (data.queue) setQueue(data.queue);
                            if (data.notes) setNotes(data.notes);
                            if (data.metrics_data) setMetrics(data.metrics_data);

                            py.request(JSON.stringify({action: 'get_sync_status'})).then(res => {
                                const syncData = JSON.parse(res);
                                setSettings(prev => ({
                                    ...prev,
                                    device_id: syncData.device_id,
                                    sync_enabled: syncData.enabled,
                                    sync_repo_url: syncData.repo_url,
                                    sync_interval: syncData.interval,
                                    has_token: syncData.has_token  // Add this line
                                }));
                            });
                            py.request(JSON.stringify({action: 'get_mapped_folders'})).then(res => {
                                const folders = JSON.parse(res);
                                setSettings(prev => ({...prev, mapped_folders: folders.folders}));
                            });
                        });
                    });
                }
            }, []);
            
            useEffect(() => {
                if (settings.bg_image_path) document.body.style.backgroundImage = `url('${settings.bg_image_path}')`;
                if (settings.font_family) document.body.style.fontFamily = settings.font_family;
                if (settings.font_color) document.body.style.color = settings.font_color;
            }, [settings.bg_image_path, settings.font_family, settings.font_color]);
            
            const renderContent = () => {
                switch(currentView) {
                    case 'dashboard': return <DashboardView layout={layout} setLayout={setLayout} goals={goals} isEditingLayout={isEditingLayout} setIsEditingLayout={setIsEditingLayout} clockFeed={clockFeed} heatmap={heatmap} habits={habits} habitLogs={habitLogs} metrics={metrics} backend={backend} />;
                    case 'hub': return <ProductivityHubView backend={backend} timerState={timerState} camFeed={camFeed} flatGoals={flatGoals} queue={queue} refreshQueue={setQueue} settings={settings} />;
                    case 'architecture': return <LifeArchitectureView goals={goals} backend={backend} refreshGoals={(d) => {setGoals(d.goals); setFlatGoals(d.flat_goals);}} />;
                    case 'habits': return <HabitMatrixView 
    habits={habits} 
    backend={backend} 
    refreshHabits={setHabits}
    habitLogs={habitLogs}
    setHabitLogs={setHabitLogs}
/>;
                    case 'summary': return <DaySummaryView metrics={metrics} />;
                    case 'quiz': return <QuizEngineView quizzes={quizzes} backend={backend} refreshQuizzes={setQuizzes} flatGoals={flatGoals} />;
                    case 'flashcards': return <FlashcardsView flashcards={flashcards} backend={backend} refreshCards={setFlashcards} flatGoals={flatGoals} />;
                    case 'notes': return <NotesView notes={notes} backend={backend} refreshNotes={setNotes} flatGoals={flatGoals} />;
                    case 'settings': return <SettingsView settings={settings} setSettings={setSettings} backend={backend} />;
                    default: return <div className="text-white text-center mt-20 font-bold">Module Loading...</div>;
                }
            };

            return (
                <div className="h-screen w-screen flex overflow-hidden">
                    <div className="w-20 md:w-64 glass-panel-darker border-r border-white/10 flex flex-col py-6 z-50 shrink-0 rounded-none border-y-0 border-l-0 shadow-2xl">
                        <div className="px-4 md:px-8 mb-8 flex items-center justify-center md:justify-start gap-3">
                            <i className="fas fa-layer-group text-2xl text-shadow-blue text-blue-500"></i>
                            <h1 className="text-xl font-serif font-bold tracking-widest text-white uppercase drop-shadow-md hidden md:block">Mind Palace OS</h1>
                        </div>
                        <nav className="flex flex-col gap-1 px-2 md:px-4 overflow-y-auto flex-grow custom-scrollbar">
                            {[
                                { id: 'dashboard', icon: 'fa-th-large', label: 'Dashboard' },
                                { id: 'hub', icon: 'fa-bolt', label: 'Productivity Hub' },
                                { id: 'architecture', icon: 'fa-sitemap', label: 'Life Architecture' },
                                { id: 'habits', icon: 'fa-check-square', label: 'Habit Matrix' },
                                { id: 'summary', icon: 'fa-calendar-day', label: 'Day Summary' },
                                { id: 'quiz', icon: 'fa-question-circle', label: 'Quiz Engine' },
                                { id: 'flashcards', icon: 'fa-clone', label: 'Flashcards' },
                                { id: 'notes', icon: 'fa-edit', label: 'Notes' },
                            ].map(nav => (
                                <button key={nav.id} onClick={() => setCurrentView(nav.id)}
                                    className={`flex items-center p-3 md:px-4 rounded-lg transition-all duration-200 group
                                        ${currentView === nav.id ? 'bg-white/10 text-white border border-white/10 shadow-[inset_0_0_15px_rgba(255,255,255,0.05)]' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'}`}>
                                    <i className={`fas ${nav.icon} text-lg md:mr-4 w-6 text-center ${currentView === nav.id ? 'text-blue-400' : ''}`}></i>
                                    <span className="font-bold text-[11px] hidden md:block tracking-widest uppercase">{nav.label}</span>
                                </button>
                            ))}
                        </nav>
                        <div className="px-2 md:px-4 mt-4 pt-4 border-t border-white/10">
                            <button onClick={() => setCurrentView('settings')}
                                className={`w-full flex items-center justify-center md:justify-start p-3 md:px-4 rounded-lg transition-all duration-200 group
                                    ${currentView === 'settings' ? 'bg-white/10 text-white border border-white/10' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'}`}>
                                <i className={`fas fa-cog text-lg md:mr-4 w-6 text-center ${currentView === 'settings' ? 'text-gray-200' : ''}`}></i>
                                <span className="font-bold text-[11px] hidden md:block tracking-widest uppercase">Settings</span>
                            </button>
                        </div>
                    </div>
                    <div className="flex-grow flex flex-col relative h-full overflow-hidden p-4 sm:p-6 lg:p-8">
                        {renderContent()}
                    </div>
                </div>
            );
        };

        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(<App />);
    </script>
</body>
</html>"""

class MindPalaceWebOS(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shadow OS - React/Python Integration")
        self.resize(1400, 900)
        
        self.browser = QWebEngineView()
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        self.channel = QWebChannel()
        self.bridge = SystemBridge()
        
        self.channel.registerObject("backend", self.bridge)
        self.browser.page().setWebChannel(self.channel)
        
        base_url = QUrl.fromLocalFile(CACHE_DIR + os.sep)
        self.browser.setHtml(get_html_content(), base_url)
        
        self.setCentralWidget(self.browser)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    splash = SplashScreen()
    splash.show()
    splash.start_download()
    
    sys.exit(app.exec())