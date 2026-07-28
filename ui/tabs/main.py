import sys, sqlite3, json, os, subprocess, random, base64
from datetime import datetime, timedelta
import cv2
import numpy as np

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QTimer, Qt, QTime, QRectF, QUrl, QByteArray, QBuffer, QIODevice, QPoint
from PyQt6.QtGui import QImage, QPainter, QPainterPath, QColor, QPen, QBrush, QFont, QRadialGradient
from PyQt6.QtMultimedia import QSoundEffect

class ConfigManager:
    def __init__(self, fn="config.json"):
        self.fn = fn
        self.defaults = {
            "clock_style": "Minimal", "clock_hands": "Classic", "clock_dial_color": "Deep Blue",
            "dist_delay": 3, "vision_mode": "Strict (Face & Eyes)", "panel_opacity": 180, 
            "force_close_apps_mins": 5, "sound_app_dist": "Ping", "sound_cam_dist": "Basso", 
            "beep_freq": 3, "speech_dist": "Distracted.", "speech_comp": "Session complete."
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
            CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY, name TEXT UNIQUE, target_hours REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS pomodoro_sessions (id INTEGER PRIMARY KEY, course TEXT, duration INTEGER, actual_duration INTEGER, timestamp TEXT, type TEXT, distractions INTEGER DEFAULT 0, timelapse_path TEXT, distraction_data TEXT);
            CREATE TABLE IF NOT EXISTS cascading_goals (id INTEGER PRIMARY KEY, parent_id INTEGER, level TEXT, title TEXT, category TEXT, target_hours REAL DEFAULT 0, logged_hours REAL DEFAULT 0, deadline TEXT);
            CREATE TABLE IF NOT EXISTS habits (id INTEGER PRIMARY KEY, name TEXT, type TEXT, metric TEXT);
            CREATE TABLE IF NOT EXISTS habit_logs (id INTEGER PRIMARY KEY, habit_id INTEGER, date TEXT, value TEXT);
            CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT, timestamp TEXT);
            CREATE TABLE IF NOT EXISTS flashcards (id INTEGER PRIMARY KEY, course TEXT, front TEXT, back TEXT);
            CREATE TABLE IF NOT EXISTS saved_quizzes (id INTEGER PRIMARY KEY, title TEXT, course TEXT, filepath TEXT);
        ''')
        self.conn.commit()

db = DatabaseManager()

def get_color(c_name): 
    if c_name == "Break": return QColor(100,100,100,200)
    if not c_name or c_name == "None": return QColor("#40c463")
    return QColor(f"#{hashlib.md5(c_name.encode()).hexdigest()[:6]}")

def get_active_app():
    try: 
        res = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'], capture_output=True, text=True)
        return res.stdout.strip()
    except: return ""

def draw_minimal_clock(p, radius, cfg):
    dial_color_name = cfg.get("clock_dial_color", "Deep Blue")
    colors = {"Deep Blue": QColor(15, 25, 40), "Onyx Black": QColor(10, 10, 12), "Panda": QColor(240, 240, 245), "Emerald Green": QColor(15, 40, 25)}
    base_dial = colors.get(dial_color_name, QColor(15, 25, 40))
    is_light = dial_color_name == "Panda"
    
    # Clean Dial
    p.setPen(QPen(QColor(255,255,255,40) if not is_light else QColor(0,0,0,40), 2))
    dial_grad = QRadialGradient(0, 0, radius)
    dial_grad.setColorAt(0, base_dial.lighter(110))
    dial_grad.setColorAt(1, base_dial.darker(120))
    p.setBrush(QBrush(dial_grad))
    p.drawEllipse(int(-radius), int(-radius), int(radius*2), int(radius*2))

    # Clean Minimalist Ticks
    p.save()
    tick_col = QColor(0,0,0,150) if is_light else QColor(255,255,255,150)
    for i in range(60):
        if i % 5 == 0: 
            p.setPen(QPen(tick_col, 2))
            p.drawLine(int(radius-12), 0, int(radius-4), 0)
        else: 
            p.setPen(QPen(tick_col.darker(150), 1))
            p.drawLine(int(radius-8), 0, int(radius-4), 0)
        p.rotate(6.0)
    p.restore()

def draw_minimal_hand(p, style, length, w, is_light_dial=False):
    c = p.brush().color()
    length, w = int(length), int(w)
    
    # Subtle drop shadow
    p.save()
    p.translate(2, 2)
    p.setBrush(QColor(0,0,0,50))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawConvexPolygon([QPoint(-w, 4), QPoint(w, 4), QPoint(0, -length)])
    p.restore()
    
    p.setPen(QPen(QColor(0,0,0,100) if not is_light_dial else QColor(255,255,255,100), 1))
    p.setBrush(QBrush(c))
    
    if style == "Sword": 
        p.drawConvexPolygon([QPoint(int(-w//2), 0), QPoint(int(-w*1.5), int(-length*0.6)), QPoint(0, -length), QPoint(int(w*1.5), int(-length*0.6)), QPoint(int(w//2), 0)])
    elif style == "Baton": 
        p.drawRect(-w, 0, w*2, -length)
    else: # Classic thin
        p.drawConvexPolygon([QPoint(-w, 4), QPoint(w, 4), QPoint(0, -length)])

class OverlayWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(240, 240)
        self.sp = 0; self.dp = 0; self.txt = "00:00"; self.sm = 0; self.pm = 1
        self.ring_color = QColor("#0a84ff"); self.bg_override_color = None
        sc = QApplication.primaryScreen().geometry()
        self.move(sc.width() // 2 - 120, 20); self.oldPos = None

    def update_state(self, time_str, progress_pct, worked_mins, total_mins, active_course, distraction_mode):
        self.txt = time_str; self.sp = progress_pct / 100.0; self.sm = worked_mins; self.pm = total_mins; self.dp = min(self.sm / max(self.pm, 1), 1.0)
        self.ring_color = get_color(active_course)
        if distraction_mode == "App": self.bg_override_color = QColor(255, 140, 0, 220)
        elif distraction_mode == "Camera": self.bg_override_color = QColor(255, 50, 50, 220)
        else: self.bg_override_color = None
        self.update()

    def mousePressEvent(self, e): 
        if e.button() == Qt.MouseButton.LeftButton: self.oldPos = e.globalPosition().toPoint()
    def mouseMoveEvent(self, e): 
        if self.oldPos is not None: d = e.globalPosition().toPoint() - self.oldPos; self.move(self.x() + d.x(), self.y() + d.y()); self.oldPos = e.globalPosition().toPoint()
    def mouseReleaseEvent(self, e): self.oldPos = None
    
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); radius = 100; p.translate(120, 120)
        if self.bg_override_color:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(self.bg_override_color)); p.drawEllipse(-radius, -radius, radius*2, radius*2)
        else:
            draw_minimal_clock(p, radius, config.cfg)
        
        # Progress Rings
        p.setPen(QPen(QColor(255,255,255,30), 6)); p.drawArc(-80, -80, 160, 160, 0, 360*16)
        p.setPen(QPen(self.ring_color, 6, cap=Qt.PenCapStyle.RoundCap)); p.drawArc(-80, -80, 160, 160, 90*16, int(-self.sp * 360 * 16))
        
        # Time Text
        is_light = config.get("clock_dial_color") == "Panda" and not self.bg_override_color
        p.setPen(QColor("black" if is_light else "white")); p.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        p.drawText(QRectF(-100, 25, 200, 40), Qt.AlignmentFlag.AlignCenter, self.txt)
        
        # Hands
        t = QTime.currentTime(); h_style = config.get("clock_hands", "Classic")
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("black" if is_light else "white")))
        p.save(); p.rotate(30.0 * (t.hour() + t.minute()/60.0)); draw_minimal_hand(p, h_style, 55, 3, is_light); p.restore()
        p.save(); p.rotate(6.0 * (t.minute() + t.second()/60.0)); draw_minimal_hand(p, h_style, 75, 2, is_light); p.restore()
        
        # Seconds
        sec_col = self.ring_color
        p.setBrush(QBrush(sec_col)); p.setPen(Qt.PenStyle.NoPen)
        p.save(); p.rotate(6.0 * t.second()); p.drawRect(-1, 0, 2, -85); p.restore()
        p.drawEllipse(-3, -3, 6, 6)

        # Glass glare (drawn last, highly transparent)
        p.setBrush(QColor(255, 255, 255, 10))
        p.drawChord(QRectF(-radius, -radius, radius*2, radius*2), 45*16, 90*16)

class VisionTracker(QObject):
    def __init__(self):
        super().__init__()
        self.cap = None
        self.fc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml')
        self.has_valid_feed = False
    def start(self):
        if not self.cap or not self.cap.isOpened():
            for i in [0, 1]:
                tc = cv2.VideoCapture(i)
                if tc.isOpened(): self.cap = tc; self.has_valid_feed = True; break
    def stop(self):
        if self.cap: self.cap.release(); self.cap = None
        self.has_valid_feed = False
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
        _, buffer = cv2.imencode('.jpg', cv2.resize(frm, (320, 240)), [cv2.IMWRITE_JPEG_QUALITY, 60])
        return att, base64.b64encode(buffer).decode('utf-8')

class SystemBridge(QObject):
    state_update = pyqtSignal(str)
    video_feed = pyqtSignal(str)
    clock_feed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ovl = OverlayWidget()
        self.vision = VisionTracker()
        
        self.timer = QTimer(); self.timer.timeout.connect(self.tick)
        self.clock_timer = QTimer(); self.clock_timer.timeout.connect(self.emit_clock); self.clock_timer.start(1000)
        
        self.is_running = False
        self.time_left = 0; self.total_time = 0
        self.queue = []; self.cidx = -1
        self.distractions = 0; self.ps = None; self.dist_type = "None"
        
        self.snd_app = QSoundEffect(); self.snd_app.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_app_dist', 'Ping')}.aiff")); self.snd_app.setVolume(1.0)
        self.snd_vis = QSoundEffect(); self.snd_vis.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_cam_dist', 'Basso')}.aiff")); self.snd_vis.setVolume(1.0)

    @pyqtSlot(str, result=str)
    def request(self, payload):
        req = json.loads(payload)
        action = req.get("action")

        if action == "init":
            return json.dumps({
                "courses": [r[0] for r in db.c.execute("SELECT name FROM courses").fetchall()],
                "goals": self.get_goals_tree(),
                "habits": self.get_habits(),
                "notes": self.get_notes(),
                "flashcards": self.get_flashcards(),
                "heatmap": self.get_heatmap_data(),
                "settings": config.cfg,
                "queue": self.queue,
                "cidx": self.cidx,
                "timer_state": {"is_running": self.is_running, "time_left": self.time_left, "total_time": self.total_time}
            })
            
        elif action == "save_settings":
            for k, v in req.get("data", {}).items(): config.set(k, v)
            self.snd_app.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_app_dist', 'Ping')}.aiff"))
            self.snd_vis.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_cam_dist', 'Basso')}.aiff"))
            return json.dumps({"status": "saved"})
            
        elif action == "add_queue":
            self.queue.append(req.get("task"))
            self.push_state()
            return json.dumps({"status": "added"})
            
        elif action == "remove_queue":
            idx = req.get("index")
            if 0 <= idx < len(self.queue):
                self.queue.pop(idx)
                if self.cidx >= idx: self.cidx = max(-1, self.cidx - 1)
                self.push_state()
            return json.dumps({"status": "removed"})
            
        elif action == "clear_queue":
            self.queue = []; self.cidx = -1; self.push_state()
            return json.dumps({"status": "cleared"})
            
        elif action == "start_timer":
            if not self.queue: return json.dumps({"error": "Empty queue"})
            if self.cidx == -1: self.cidx = 0
            if self.cidx < len(self.queue):
                if self.total_time == 0 or not self.is_running:
                    self.total_time = int(self.queue[self.cidx]["duration"]) * 60
                    self.time_left = self.total_time
                    if "distractions" not in self.queue[self.cidx]: self.queue[self.cidx]["distractions"] = []
                    self.queue[self.cidx]["worked"] = 0
                self.is_running = True
                self.ovl.show(); self.vision.start(); self.timer.start(1000)
            self.push_state()
            return json.dumps({"status": "started"})
            
        elif action == "stop_timer":
            self.is_running = False; self.timer.stop(); self.ovl.hide(); self.vision.stop()
            if self.cidx >= 0 and self.cidx < len(self.queue):
                db.c.execute("INSERT INTO pomodoro_sessions (course, duration, actual_duration, timestamp, type, distractions) VALUES (?,?,?,?,?,?)",
                             (self.queue[self.cidx]["course"], self.total_time//60, (self.total_time-self.time_left)//60, datetime.now().isoformat(), self.queue[self.cidx]["type"], self.distractions))
                db.conn.commit()
            self.cidx = -1; self.total_time = 0; self.time_left = 0
            self.push_state()
            return json.dumps({"status": "stopped"})

        elif action == "add_goal":
            db.c.execute("INSERT INTO cascading_goals (title, category, target_hours, deadline) VALUES (?,?,?,?)", (req.get("title"), req.get("category"), req.get("target"), req.get("deadline")))
            db.conn.commit()
            return json.dumps({"status": "added", "goals": self.get_goals_tree()})
            
        elif action == "add_habit":
            db.c.execute("INSERT INTO habits (name, type, metric) VALUES (?, 'Positive', 'Boolean')", (req.get("name"),))
            db.conn.commit()
            return json.dumps({"status": "added", "habits": self.get_habits()})
            
        elif action == "toggle_habit":
            db.c.execute("SELECT id FROM habit_logs WHERE habit_id=? AND date=?", (req.get("id"), req.get("date")))
            if db.c.fetchone(): db.c.execute("DELETE FROM habit_logs WHERE habit_id=? AND date=?", (req.get("id"), req.get("date")))
            else: db.c.execute("INSERT INTO habit_logs (habit_id, date, value) VALUES (?,?,?)", (req.get("id"), req.get("date"), "1"))
            db.conn.commit()
            return json.dumps({"status": "toggled", "habits": self.get_habits()})
            
        elif action == "save_note":
            db.c.execute("INSERT OR REPLACE INTO notes (id, title, content, timestamp) VALUES (?,?,?,?)", (req.get("id"), req.get("title"), req.get("content"), datetime.now().isoformat()))
            db.conn.commit()
            return json.dumps({"status": "saved", "notes": self.get_notes()})

        elif action == "add_flashcard":
            db.c.execute("INSERT INTO flashcards (course, front, back) VALUES (?,?,?)", (req.get("course"), req.get("front"), req.get("back")))
            db.conn.commit()
            return json.dumps({"status": "added", "flashcards": self.get_flashcards()})

        return json.dumps({"error": "Unknown action"})

    def emit_clock(self):
        img = QImage(240, 240, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.translate(120, 120)
        draw_minimal_clock(p, 110, config.cfg)
        
        t = QTime.currentTime(); h_style = config.get("clock_hands", "Classic"); is_light = config.get("clock_dial_color") == "Panda"
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("black" if is_light else "white")))
        p.save(); p.rotate(30.0 * (t.hour() + t.minute()/60.0)); draw_minimal_hand(p, h_style, 60, 4, is_light); p.restore()
        p.save(); p.rotate(6.0 * (t.minute() + t.second()/60.0)); draw_minimal_hand(p, h_style, 85, 3, is_light); p.restore()
        
        sec_col = QColor("#0a84ff")
        p.setBrush(QBrush(sec_col)); p.setPen(Qt.PenStyle.NoPen); p.save(); p.rotate(6.0 * t.second()); p.drawRect(-1, 0, 2, -95); p.restore()
        p.setBrush(QBrush(QColor("white"))); p.drawEllipse(-4, -4, 8, 8)
        
        p.setBrush(QColor(255, 255, 255, 10)); p.drawChord(QRectF(-110, -110, 220, 220), 45*16, 90*16)
        p.end()
        
        buf = QByteArray(); buffer = QBuffer(buf); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buffer, "PNG")
        self.clock_feed.emit(f"data:image/png;base64,{base64.b64encode(buf.data()).decode('utf-8')}")

    def tick(self):
        if not self.is_running: return
        
        att, b64_frame = self.vision.process_frame()
        if b64_frame: self.video_feed.emit(b64_frame)
            
        act = get_active_app()
        app_dist = act not in ["", "loginwindow", "WindowManager", "ControlCenter", "NotificationCenter", "Spotlight", "Siri", "python", "Terminal"]
        
        if not att or app_dist:
            self.distractions += 1
            self.dist_type = "App" if app_dist else "Camera"
            if self.distractions == 1: self.ps = datetime.now()
            
            if self.distractions % max(1, config.get("beep_freq", 3)) == 0:
                subprocess.Popen(["osascript", "-e", "set volume output volume 100"])
                if self.dist_type == "Camera": self.snd_vis.play()
                else: self.snd_app.play()
        else:
            if self.distractions > 0 and self.ps:
                d_mins = (datetime.now() - self.ps).total_seconds() / 60.0
                if d_mins > 0.1: self.queue[self.cidx]["distractions"].append([self.queue[self.cidx].get("worked", 0), d_mins, self.dist_type])
            self.distractions = 0; self.dist_type = "None"

        if self.time_left > 0:
            self.time_left -= 1
            if self.cidx >= 0: self.queue[self.cidx]["worked"] = (self.total_time - self.time_left) / 60.0
        else:
            self.is_running = False; self.timer.stop(); self.ovl.hide(); self.vision.stop()
            db.c.execute("INSERT INTO pomodoro_sessions (course, duration, actual_duration, timestamp, type, distractions) VALUES (?,?,?,?,?,?)",
                         (self.queue[self.cidx]["course"], self.total_time//60, (self.total_time-self.time_left)//60, datetime.now().isoformat(), self.queue[self.cidx]["type"], self.distractions))
            db.conn.commit()
            subprocess.Popen(["say", config.get("speech_comp", "Session Complete.")])
            self.cidx += 1
            if self.cidx < len(self.queue): self.request(json.dumps({"action": "start_timer"})) 
            else: self.cidx = -1
            
        self.push_state()

    def push_state(self):
        mins, secs = divmod(self.time_left, 60); time_str = f"{mins:02d}:{secs:02d}"
        pct = 100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0
        crs = self.queue[self.cidx]["course"] if self.cidx >= 0 and self.cidx < len(self.queue) else "General"
        self.ovl.update_state(time_str, pct, (self.total_time-self.time_left)//60, self.total_time//60, crs, self.dist_type)
        self.state_update.emit(json.dumps({ "is_running": self.is_running, "time_str": time_str, "progress": pct, "distractions": self.distractions, "course": crs, "queue": self.queue, "cidx": self.cidx }))

    def get_goals_tree(self):
        db.c.execute("SELECT id, title, target_hours, logged_hours, deadline FROM cascading_goals")
        return [{"id": r[0], "title": r[1], "target": r[2], "logged": r[3], "deadline": r[4], "children": []} for r in db.c.fetchall()]
        
    def get_habits(self):
        db.c.execute("SELECT id, name FROM habits")
        habits = [{"id": r[0], "name": r[1]} for r in db.c.fetchall()]
        db.c.execute("SELECT habit_id, date FROM habit_logs")
        logs = [f"{r[0]}_{r[1]}" for r in db.c.fetchall()]
        return {"list": habits, "logs": logs}
        
    def get_notes(self):
        db.c.execute("SELECT id, title, content FROM notes ORDER BY timestamp DESC")
        return [{"id": r[0], "title": r[1], "content": r[2]} for r in db.c.fetchall()]
        
    def get_flashcards(self):
        db.c.execute("SELECT id, course, front, back FROM flashcards")
        return [{"id": r[0], "course": r[1], "front": r[2], "back": r[3]} for r in db.c.fetchall()]

    def get_heatmap_data(self):
        weeks = 28; matrix = [[0]*7 for _ in range(weeks)]; td = datetime.now().date()
        db.c.execute("SELECT date(timestamp), sum(duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY date(timestamp)")
        history = {r[0]: r[1]/60.0 for r in db.c.fetchall()}
        for w in range(weeks):
            for d in range(7):
                target_date = (td - timedelta(days=(weeks-w-1)*7 + (6-d))).isoformat()
                hrs = history.get(target_date, 0)
                matrix[w][d] = 1 if hrs > 0 else (2 if hrs > 2 else (3 if hrs > 4 else (4 if hrs > 6 else 0)))
        return matrix

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kourosh's Mind Palace - Shadow OS</title>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>

    <style>
        body { background-color: #050505; background-image: url('https://images.unsplash.com/photo-1518531933037-91b2f5f229cc?q=80&w=2000&auto=format&fit=crop'); background-repeat: no-repeat; background-position: center center; background-attachment: fixed; background-size: cover; margin: 0; padding: 0; color: #e2e8f0; overflow: hidden; font-family: 'Inter', sans-serif; }
        .glass-panel { background: rgba(15, 20, 25, 0.45); backdrop-filter: blur(20px); border-top: 1px solid rgba(255, 255, 255, 0.15); border-left: 1px solid rgba(255, 255, 255, 0.1); border-right: 1px solid rgba(255, 255, 255, 0.05); border-bottom: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255,255,255,0.05); }
        .glass-panel-darker { background: rgba(5, 8, 12, 0.7); backdrop-filter: blur(25px); border: 1px solid rgba(255, 255, 255, 0.05); }
        .glass-input { background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255, 255, 255, 0.1); color: white; transition: all 0.2s; }
        .glass-input:focus { background: rgba(10, 15, 25, 0.5); border-color: rgba(59, 130, 246, 0.5); outline: none; }
        .glass-button { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); transition: all 0.2s; }
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

        const NativeGitHubMatrix = ({ heatmap }) => {
            const matrix = heatmap && heatmap.length > 0 ? heatmap : Array.from({ length: 28 }, () => Array(7).fill(0));
            const getColor = (val) => {
                if (val === 0) return 'bg-white/5 border border-white/5'; 
                if (val === 1) return 'bg-[#0e4429]';
                if (val === 2) return 'bg-[#006d32]';
                if (val === 3) return 'bg-[#26a641]';
                return 'bg-[#39d353] shadow-[0_0_8px_rgba(57,211,83,0.4)]';
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
                                        <div key={`${wIdx}-${dIdx}`} className={`w-3.5 h-3.5 rounded-[3px] ${getColor(day)} cursor-pointer`}></div>
                                    ))}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            );
        };

        const DualCalendar = ({ goals }) => {
            const [currentDate, setCurrentDate] = useState(new Date());
            const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
            const year = currentDate.getFullYear(); const month = currentDate.getMonth();
            const daysInMonth = new Date(year, month + 1, 0).getDate();
            const firstDayOfMonth = new Date(year, month, 1).getDay();

            return (
                <div className="p-4 h-full flex flex-col w-full">
                    <div className="flex justify-between items-center mb-4 bg-black/40 p-2 rounded-xl border border-white/10 backdrop-blur-md">
                        <button onClick={() => setCurrentDate(new Date(year, month - 1, 1))} className="w-6 h-6 hover:bg-white/10 rounded-full text-gray-300"><i className="fas fa-chevron-left text-xs"></i></button>
                        <h2 className="text-sm font-bold text-white tracking-widest uppercase">{monthNames[month]} {year}</h2>
                        <button onClick={() => setCurrentDate(new Date(year, month + 1, 1))} className="w-6 h-6 hover:bg-white/10 rounded-full text-gray-300"><i className="fas fa-chevron-right text-xs"></i></button>
                    </div>
                    <div className="calendar-grid mb-1">
                        {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((day, i) => (
                            <div key={day} className={`text-center text-[10px] font-bold uppercase ${(i===0||i===6)?'text-red-400':'text-gray-400'}`}>{day}</div>
                        ))}
                    </div>
                    <div className="calendar-grid flex-grow overflow-y-auto pr-1">
                        {Array.from({length: firstDayOfMonth}).map((_, i) => <div key={`empty-${i}`} className="min-h-[70px]"></div>)}
                        {Array.from({length: daysInMonth}).map((_, i) => {
                            const dateObj = new Date(year, month, i + 1);
                            const dateString = `${dateObj.getFullYear()}-${String(dateObj.getMonth() + 1).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`;
                            const isToday = new Date().toDateString() === dateObj.toDateString();
                            const dayDeadlines = (goals || []).filter(g => g.deadline && g.deadline.startsWith(dateString));
                            
                            return (
                                <div key={i} className={`relative p-1.5 flex flex-col min-h-[70px] border border-white/5 rounded-lg ${isToday ? 'bg-blue-600/30 border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.5)]' : 'bg-black/20 hover:bg-white/10'}`}>
                                    <span className={`text-sm font-bold ${isToday ? 'text-white' : 'text-gray-200'}`}>{i + 1}</span>
                                    <div className="mt-auto pt-1 flex flex-col gap-0.5 w-full">
                                        {dayDeadlines.map((dl, idx) => (
                                            <div key={idx} className="w-full text-[9px] font-bold truncate bg-red-600 text-white px-1 rounded shadow-sm">{dl.title}</div>
                                        ))}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            );
        };

        const DashboardView = ({ layout, setLayout, goals, isEditingLayout, setIsEditingLayout, clockFeed, heatmap }) => {
            const toggleWidgetVisibility = (id) => setLayout(prev => prev.map(w => w.id === id ? { ...w, visible: !w.visible } : w));
            const toggleWidgetSize = (id) => setLayout(prev => prev.map(w => w.id === id ? { ...w, size: w.size === 'full' ? 'half' : 'full' } : w));
            
            return (
                <div className="h-full flex flex-col fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase">Dashboard</h2>
                        <button onClick={() => setIsEditingLayout(!isEditingLayout)} className={`px-4 py-2 rounded text-xs font-bold shadow-lg border ${isEditingLayout ? 'bg-blue-600 text-white border-blue-400' : 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/15'}`}>
                            <i className={`fas ${isEditingLayout ? 'fa-check' : 'fa-sliders-h'} mr-2`}></i> {isEditingLayout ? 'Save Layout' : 'Configure Layout'}
                        </button>
                    </div>
                    <div className="flex flex-wrap -mx-3 items-stretch overflow-y-auto pb-10 flex-grow content-start">
                        {[...layout].sort((a,b)=>a.order-b.order).filter(w => isEditingLayout || w.visible).map(widget => (
                            <div key={widget.id} className={`${widget.size === 'full' ? 'w-full' : 'w-full md:w-1/2'} px-3 mb-6 transition-all duration-300`}>
                                <div className={`glass-panel overflow-hidden h-full flex flex-col relative ${!widget.visible ? 'opacity-30' : ''}`} style={{ minHeight: '320px' }}>
                                    {isEditingLayout && (
                                        <div className="absolute inset-0 bg-black/80 z-50 flex flex-col items-center justify-center gap-3 border-2 border-blue-500 border-dashed rounded-xl">
                                            <div className="text-white font-bold">{widget.type}</div>
                                            <div className="flex gap-2">
                                                <button onClick={() => toggleWidgetVisibility(widget.id)} className="px-4 py-2 rounded text-xs font-bold bg-green-600 text-white">Toggle</button>
                                                <button onClick={() => toggleWidgetSize(widget.id)} className="px-4 py-2 rounded text-xs font-bold bg-blue-600 text-white">Resize</button>
                                            </div>
                                        </div>
                                    )}
                                    {widget.type === 'Clock' && <div className="flex items-center justify-center h-full p-4">{clockFeed ? <img src={clockFeed} className="w-64 h-64 drop-shadow-2xl object-contain" /> : <div className="text-gray-500">Loading Native Horology...</div>}</div>}
                                    {widget.type === 'Calendar' && <DualCalendar goals={goals} />}
                                    {widget.type === 'GitHubMatrix' && <NativeGitHubMatrix heatmap={heatmap} />}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            );
        };

        const ProductivityHubView = ({ backend, timerState, camFeed, courses }) => {
            const [dur, setDur] = useState(25);
            const [crs, setCrs] = useState("General");
            const [selIdx, setSelIdx] = useState(null);

            const toggleTimer = () => {
                if (!backend) return;
                if (timerState.is_running) backend.request(JSON.stringify({action: 'stop_timer'}));
                else backend.request(JSON.stringify({action: 'start_timer'}));
            };

            const addQueue = () => {
                if (!backend) return;
                backend.request(JSON.stringify({action: 'add_queue', task: {course: crs, duration: dur, type: 'Work', distractions: [], worked: 0}}));
            };

            return (
                <div className="h-full flex flex-col fade-in">
                    <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase mb-6 shrink-0">Productivity Hub</h2>
                    
                    <div className="flex flex-wrap gap-2 mb-4 w-full glass-panel p-2 items-center">
                        <select className="glass-input px-3 py-1.5 rounded text-xs font-bold uppercase w-32" value={crs} onChange={e => setCrs(e.target.value)}>
                            <option>General</option>
                            {courses && courses.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                        <input type="number" className="glass-input px-3 py-1.5 rounded text-xs font-bold uppercase w-20" value={dur} onChange={e => setDur(e.target.value)} />
                        <button onClick={addQueue} className="glass-button px-4 py-1.5 rounded text-[11px] font-bold text-gray-200 uppercase">+ Add</button>
                        <div className="h-4 w-px bg-white/20 mx-2"></div>
                        <button onClick={() => selIdx !== null && backend.request(JSON.stringify({action: 'remove_queue', index: selIdx}))} className="glass-button px-4 py-1.5 rounded text-[11px] font-bold text-red-300 uppercase">- Remove</button>
                        <button onClick={() => backend.request(JSON.stringify({action: 'clear_queue'}))} className="glass-button px-4 py-1.5 rounded text-[11px] font-bold text-red-500 uppercase">Clear All</button>
                    </div>

                    <div className="glass-panel flex-grow rounded-xl relative p-6 flex flex-col overflow-hidden">
                        
                        <div className="h-1/3 bg-black/20 rounded-lg border border-white/5 p-4 mb-4 overflow-y-auto">
                            {timerState.queue && timerState.queue.map((q, idx) => (
                                <div key={idx} onClick={() => setSelIdx(idx)} className={`flex items-center gap-3 mb-2 p-2 rounded cursor-pointer transition-all ${selIdx === idx ? 'ring-2 ring-white/50' : ''} ${idx === timerState.cidx ? 'bg-blue-600/30 border border-blue-500/50 text-white shadow-lg' : 'bg-white/5 text-gray-400'}`}>
                                    <span className="text-xs font-bold">{idx === timerState.cidx ? '[ACTIVE]' : idx < timerState.cidx ? '[DONE]' : '[WAITING]'} {q.course} ({q.duration}m)</span>
                                    {q.distractions && q.distractions.length > 0 && <span className="text-xs text-red-400">({q.distractions.length} Distractions)</span>}
                                </div>
                            ))}
                        </div>

                        {/* Gantt Timeline Map */}
                        <div className="h-16 border border-white/10 rounded-lg relative flex items-center mb-auto overflow-hidden bg-black/40">
                            {timerState.queue && timerState.queue.map((q, idx) => {
                                const totalDur = timerState.queue.reduce((acc, val) => acc + val.duration, 0) || 1;
                                const leftPct = (timerState.queue.slice(0, idx).reduce((acc, val) => acc + val.duration, 0) / totalDur) * 100;
                                const widthPct = (q.duration / totalDur) * 100;
                                const workedPct = ((q.worked || 0) / q.duration) * 100;
                                
                                return (
                                    <div key={idx} className={`absolute h-full border-r border-black/50 ${idx === timerState.cidx ? 'bg-blue-500/80' : idx < timerState.cidx ? 'bg-gray-500/50' : 'bg-white/10'}`} style={{left: `${leftPct}%`, width: `${widthPct}%`}}>
                                        <div className="h-full bg-green-500/50" style={{width: `${workedPct}%`}}></div>
                                        {q.distractions && q.distractions.map((d, didx) => (
                                            <div key={didx} className={`absolute top-0 h-full ${d[2] === 'Camera' ? 'bg-red-500' : 'bg-yellow-500'}`} style={{left: `${(d[0]/q.duration)*100}%`, width: '4px'}}></div>
                                        ))}
                                    </div>
                                );
                            })}
                        </div>

                        <div className="flex justify-between items-end mt-4">
                            <div className={`text-6xl font-mono font-bold tracking-widest drop-shadow-lg ${timerState.is_running ? 'text-blue-400' : 'text-white'}`}>
                                {timerState.time_str || "00:00"}
                            </div>
                            <div className="flex gap-4">
                                <button onClick={toggleTimer} className={`glass-button px-6 py-3 rounded-lg text-xs font-bold text-white uppercase shadow-lg ${timerState.is_running ? 'bg-red-600/40 border-red-500/50 hover:bg-red-600' : 'bg-green-600/40 border-green-500/50 hover:bg-green-600'}`}>
                                    {timerState.is_running ? 'STOP' : 'START SYSTEM'}
                                </button>
                            </div>
                        </div>
                        
                        {/* Floating Small Webcam */}
                        <div className="absolute bottom-4 right-4 w-48 h-36 bg-black border border-white/20 rounded-lg overflow-hidden shadow-2xl z-50">
                            {camFeed ? <img src={camFeed} className="w-full h-full object-cover" /> : <div className="flex h-full items-center justify-center text-gray-500 text-xs">Webcam Offline</div>}
                        </div>
                    </div>
                </div>
            );
        };

        const LifeArchitectureView = ({ backend, goals }) => {
            const [title, setTitle] = useState(""); const [target, setTarget] = useState(10); const [deadline, setDeadline] = useState("");
            
            const addGoal = () => {
                if(backend && title) backend.request(JSON.stringify({action: 'add_goal', title, target, category: 'General', deadline}));
            };

            return (
                <div className="h-full flex flex-col fade-in">
                    <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase mb-6 drop-shadow-md">Life Architecture</h2>
                    <div className="flex gap-2 mb-4 glass-panel p-2">
                        <input type="text" className="glass-input px-3 py-2 rounded text-xs flex-grow" placeholder="Goal Title..." value={title} onChange={e => setTitle(e.target.value)} />
                        <input type="number" className="glass-input px-3 py-2 rounded text-xs w-24" placeholder="Target Hrs" value={target} onChange={e => setTarget(e.target.value)} />
                        <input type="date" className="glass-input px-3 py-2 rounded text-xs" value={deadline} onChange={e => setDeadline(e.target.value)} />
                        <button onClick={addGoal} className="glass-button px-6 py-2 rounded text-xs font-bold bg-green-600/50 hover:bg-green-600 text-white">+ Save</button>
                    </div>
                    <div className="glass-panel rounded-xl p-6 flex-grow overflow-y-auto">
                        {goals && goals.map(g => (
                            <div key={g.id} className="flex justify-between items-center p-4 mb-2 bg-black/30 border border-white/10 rounded-lg">
                                <span className="font-bold text-white text-lg">{g.title}</span>
                                <div className="flex gap-4 items-center">
                                    <span className="text-xs bg-blue-900/40 text-blue-300 px-2 py-1 rounded">Target: {g.target}h (Logged: {g.logged}h)</span>
                                    {g.deadline && <span className="text-xs bg-red-900/40 text-red-300 px-2 py-1 rounded">Due: {g.deadline}</span>}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            );
        };

        const HabitMatrixView = ({ backend, habits }) => {
            const [newHabit, setNewHabit] = useState("");
            const days = Array.from({length: 7}, (_, i) => {
                const d = new Date(); d.setDate(d.getDate() - i); return d.toISOString().split('T')[0];
            }).reverse();

            const toggle = (id, date) => {
                if(backend) backend.request(JSON.stringify({action: 'toggle_habit', id, date}));
            };

            const addHabit = () => {
                if(backend && newHabit) {
                    backend.request(JSON.stringify({action: 'add_habit', name: newHabit}));
                    setNewHabit("");
                }
            };

            return (
                <div className="h-full flex flex-col fade-in">
                    <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase mb-6 drop-shadow-md">Habit Matrix</h2>
                    
                    <div className="flex gap-2 mb-4 glass-panel p-2">
                        <input type="text" className="glass-input px-3 py-2 rounded text-xs flex-grow" placeholder="New Habit..." value={newHabit} onChange={e => setNewHabit(e.target.value)} />
                        <button onClick={addHabit} className="glass-button px-6 py-2 rounded text-xs font-bold bg-blue-600/50 hover:bg-blue-600 text-white">+ Add Habit</button>
                    </div>

                    <div className="glass-panel p-1 rounded-xl overflow-x-auto flex-grow">
                        <table className="w-full text-left border-collapse min-w-[600px]">
                            <thead>
                                <tr className="border-b border-white/10 bg-black/40">
                                    <th className="p-4 text-xs font-bold text-gray-400 uppercase">Habit</th>
                                    {days.map(d => <th key={d} className="p-4 text-[10px] font-bold text-gray-400 uppercase text-center">{d.slice(5)}</th>)}
                                </tr>
                            </thead>
                            <tbody>
                                {habits && habits.list.map(h => (
                                    <tr key={h.id} className="border-b border-white/5 hover:bg-white/5">
                                        <td className="p-4 text-sm font-semibold text-gray-200">{h.name}</td>
                                        {days.map(d => (
                                            <td key={d} className="p-4 text-center">
                                                <input type="checkbox" className="w-5 h-5 cursor-pointer accent-blue-500" 
                                                    checked={habits.logs.includes(`${h.id}_${d}`)} 
                                                    onChange={() => toggle(h.id, d)} />
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            );
        };

        const FlashcardsView = ({ backend, flashcards, courses }) => {
            const [isFlipped, setIsFlipped] = useState(false);
            const [front, setFront] = useState("");
            const [back, setBack] = useState("");
            const [crs, setCrs] = useState("General");
            const [currentCard, setCurrentCard] = useState(null);

            const addCard = () => {
                if(backend && front && back) {
                    backend.request(JSON.stringify({action: 'add_flashcard', course: crs, front, back}));
                    setFront(""); setBack("");
                }
            };

            const nextCard = () => {
                if (flashcards && flashcards.length > 0) {
                    setIsFlipped(false);
                    setCurrentCard(flashcards[Math.floor(Math.random() * flashcards.length)]);
                }
            };

            return (
                <div className="flex flex-col h-full fade-in">
                    <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase mb-6 drop-shadow-md">Flashcards</h2>
                    <div className="glass-panel p-2 rounded-xl flex flex-wrap gap-2 mb-8 shrink-0">
                        <select className="glass-input px-3 py-2 rounded text-xs" value={crs} onChange={e=>setCrs(e.target.value)}>
                            <option>General</option>
                            {courses && courses.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                        <input type="text" placeholder="FRONT..." className="glass-input flex-grow px-4 py-2 rounded text-sm" value={front} onChange={e=>setFront(e.target.value)}/>
                        <input type="text" placeholder="BACK..." className="glass-input flex-grow px-4 py-2 rounded text-sm" value={back} onChange={e=>setBack(e.target.value)}/>
                        <button onClick={addCard} className="glass-button px-6 py-2 rounded text-xs font-bold text-white uppercase bg-blue-600/30 hover:bg-blue-600">ADD</button>
                    </div>
                    
                    <div className="flex-grow flex flex-col items-center justify-center perspective-1000 p-4">
                        <div className={`relative w-full max-w-2xl h-64 cursor-pointer transition-all duration-700 transform-style-3d ${isFlipped ? 'rotate-y-180' : ''}`}
                             onClick={() => setIsFlipped(!isFlipped)}>
                            <div className="absolute inset-0 glass-panel rounded-2xl flex flex-col justify-center items-center p-8 backface-hidden border-t-2 border-t-blue-500/30">
                                <span className="absolute top-4 left-4 text-xs font-mono text-gray-500">FRONT</span>
                                <h2 className="text-xl sm:text-2xl font-serif text-white text-center">{currentCard ? currentCard.front : "Click 'Next' to start"}</h2>
                            </div>
                            <div className="absolute inset-0 glass-panel-darker rounded-2xl flex flex-col justify-center items-center p-8 backface-hidden rotate-y-180 border-b-2 border-b-green-500/30">
                                <span className="absolute top-4 right-4 text-xs font-mono text-gray-500">BACK</span>
                                <p className="text-sm sm:text-lg text-gray-200 text-center">{currentCard ? currentCard.back : ""}</p>
                            </div>
                        </div>
                        <div className="flex gap-4 mt-8 shrink-0">
                            <button onClick={() => setIsFlipped(!isFlipped)} className="glass-button px-8 py-3 rounded-lg text-xs font-bold text-gray-300 uppercase">FLIP</button>
                            <button onClick={nextCard} className="glass-button px-8 py-3 rounded-lg text-xs font-bold text-white uppercase bg-blue-600/30 hover:bg-blue-600">NEXT</button>
                        </div>
                    </div>
                </div>
            );
        };

        const NotesView = ({ backend, notes }) => {
            const [selected, setSelected] = useState(null);
            const [title, setTitle] = useState("");
            const [content, setContent] = useState("");
            
            const loadNote = (n) => { setSelected(n); setTitle(n.title); setContent(n.content); };
            const save = () => { if(backend && title) backend.request(JSON.stringify({action: 'save_note', id: selected?.id, title, content})); };
            const insertText = (str) => setContent(prev => prev + str);

            return (
                <div className="h-full flex flex-col fade-in">
                    <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase mb-6 drop-shadow-md">Markdown Notes</h2>
                    <div className="flex gap-4 h-full overflow-hidden">
                        <div className="w-1/4 glass-panel p-2 overflow-y-auto flex flex-col gap-2">
                            <button onClick={() => {setSelected(null); setTitle(""); setContent("");}} className="glass-button w-full py-2 rounded text-xs font-bold bg-green-600/30">+ New Note</button>
                            {notes && notes.map(n => (
                                <button key={n.id} onClick={() => loadNote(n)} className="glass-button w-full p-3 rounded text-left text-sm text-gray-300 truncate hover:text-white border-none">{n.title}</button>
                            ))}
                        </div>
                        <div className="flex-1 glass-panel flex flex-col overflow-hidden">
                            <div className="flex gap-2 p-2 border-b border-white/10 bg-black/40">
                                <input type="text" className="glass-input px-3 py-1.5 rounded text-sm font-bold w-1/2" placeholder="Note Title..." value={title} onChange={e => setTitle(e.target.value)} />
                                <button onClick={() => insertText('**Bold** ')} className="glass-button px-3 rounded text-xs font-mono">B</button>
                                <button onClick={() => insertText('*Italic* ')} className="glass-button px-3 rounded text-xs font-mono">I</button>
                                <button onClick={() => insertText('```\nCode\n```\n')} className="glass-button px-3 rounded text-xs font-mono">&lt;/&gt;</button>
                                <button onClick={save} className="glass-button px-6 rounded text-xs font-bold bg-blue-600/50 hover:bg-blue-600 ml-auto">Save</button>
                            </div>
                            <div className="flex-1 flex overflow-hidden">
                                <textarea className="w-1/2 h-full bg-black/20 text-gray-300 p-4 outline-none resize-none font-mono text-sm border-r border-white/10" value={content} onChange={e => setContent(e.target.value)} placeholder="Type markdown..."></textarea>
                                <div className="w-1/2 h-full bg-black/40 p-6 overflow-y-auto prose prose-invert text-sm max-w-none text-gray-300 whitespace-pre-wrap">{content}</div>
                            </div>
                        </div>
                    </div>
                </div>
            );
        };

        const MomentumMapView = ({ heatmap }) => {
            return (
                <div className="flex flex-col h-full fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Momentum Map</h2>
                    </div>
                    <div className="flex flex-col gap-6 overflow-y-auto pb-6">
                        <div className="glass-panel p-2">
                            <NativeGitHubMatrix heatmap={heatmap} />
                        </div>
                        <div className="flex flex-col md:flex-row gap-6">
                            <div className="w-full md:w-1/2 glass-panel p-6 h-64 flex flex-col">
                                <h3 className="text-gray-300 text-sm font-semibold tracking-wide border-b border-white/10 pb-2 mb-4">Study Volume by Hour (Demo)</h3>
                                <div className="flex-grow flex items-end justify-between gap-1 mt-auto">
                                    {[10, 20, 5, 40, 80, 60, 30, 90, 100, 50, 20, 10].map((h, i) => (
                                        <div key={i} className="w-full bg-blue-500/60 hover:bg-blue-400 rounded-t-sm transition-all" style={{height: `${h}%`}}></div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            );
        };

        const DaySummaryView = () => {
            return (
                <div className="flex flex-col h-full fade-in">
                    <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase mb-6">Day Summary</h2>
                    <div className="flex flex-col gap-4 overflow-y-auto">
                        <div className="glass-panel p-8 text-center border-t-2 border-t-blue-500/50">
                            <h3 className="text-gray-400 font-bold uppercase tracking-widest text-xs mb-2">Time Studied Today</h3>
                            <div className="text-5xl font-mono text-white mb-2">Live sync pending...</div>
                        </div>
                    </div>
                </div>
            );
        };
        
        const QuizEngineView = () => {
            return (
                <div className="flex flex-col h-full fade-in">
                    <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase mb-6">Quiz Engine</h2>
                    <div className="glass-panel p-8 text-center text-gray-400">
                        Quiz JSON Import Module loaded. Select a JSON to begin.
                    </div>
                </div>
            );
        };

        const SettingsView = ({ settings, setSettings, backend }) => {
            const handleChange = (k, v) => setSettings(prev => ({...prev, [k]: v}));
            const saveSettings = () => { if(backend) backend.request(JSON.stringify({action: 'save_settings', data: settings})); };

            return (
                <div className="flex flex-col h-full fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Master Configuration</h2>
                        <button onClick={saveSettings} className="glass-button px-8 py-3 rounded text-xs font-bold text-white uppercase bg-blue-600 shadow-lg">Apply Settings</button>
                    </div>
                    <div className="glass-panel p-8 flex-grow overflow-y-auto">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-6 max-w-5xl">
                            <div className="md:col-span-2 text-blue-500 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2">Minimalist Horology</div>
                            {[
                                ['clock_style', 'Clock Theme', ['Minimal', 'Classic']],
                                ['clock_dial_color', 'Dial Color', ['Deep Blue', 'Onyx Black', 'Panda', 'Emerald Green']],
                                ['clock_hands', 'Hand Design', ['Classic', 'Sword', 'Baton']],
                            ].map(([k, label, opts]) => (
                                <div key={k} className="flex flex-col gap-1.5">
                                    <label className="text-xs font-bold text-gray-400 uppercase">{label}</label>
                                    <select className="glass-input p-3 rounded text-sm" value={settings[k] || opts[0]} onChange={e => handleChange(k, e.target.value)}>
                                        {opts.map(o => <option key={o}>{o}</option>)}
                                    </select>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            );
        };

        const App = () => {
            const [backend, setBackend] = useState(null);
            const [currentView, setCurrentView] = useState('hub');
            const [layout, setLayout] = useState([{ id: 'clock', type: 'Clock', size: 'half', visible: true, order: 0 }, { id: 'calendar', type: 'Calendar', size: 'half', visible: true, order: 1 }, { id: 'matrix', type: 'GitHubMatrix', size: 'full', visible: true, order: 2 }]);
            const [isEditingLayout, setIsEditingLayout] = useState(false);
            
            const [courses, setCourses] = useState([]);
            const [goals, setGoals] = useState([]);
            const [habits, setHabits] = useState({list: [], logs: []});
            const [notes, setNotes] = useState([]);
            const [flashcards, setFlashcards] = useState([]);
            const [settings, setSettings] = useState({});
            const [heatmap, setHeatmap] = useState([]);
            const [timerState, setTimerState] = useState({ is_running: false, time_str: "00:00", progress: 0, distractions: 0, course: "General", queue: [], cidx: -1 });
            
            const [camFeed, setCamFeed] = useState(null);
            const [clockFeed, setClockFeed] = useState(null);

            useEffect(() => {
                if (typeof qt !== 'undefined') {
                    new QWebChannel(qt.webChannelTransport, (channel) => {
                        const py = channel.objects.backend;
                        setBackend(py);
                        py.state_update.connect((state_json) => setTimerState(JSON.parse(state_json)));
                        py.video_feed.connect((b64) => setCamFeed(`data:image/jpeg;base64,${b64}`));
                        py.clock_feed.connect((b64) => setClockFeed(b64));
                        py.request(JSON.stringify({action: 'init'})).then(res => {
                            const data = JSON.parse(res);
                            setCourses(data.courses || []);
                            setGoals(data.goals || []);
                            setHabits(data.habits || {list:[], logs:[]});
                            setNotes(data.notes || []);
                            setFlashcards(data.flashcards || []);
                            setSettings(data.settings || {});
                            setHeatmap(data.heatmap || []);
                            if(data.queue) setTimerState(prev => ({...prev, queue: data.queue, cidx: data.cidx}));
                        });
                    });
                }
            }, []);

            const renderContent = () => {
                switch(currentView) {
                    case 'dashboard': return <DashboardView layout={layout} setLayout={setLayout} goals={goals} isEditingLayout={isEditingLayout} setIsEditingLayout={setIsEditingLayout} clockFeed={clockFeed} heatmap={heatmap} />;
                    case 'hub': return <ProductivityHubView backend={backend} timerState={timerState} camFeed={camFeed} courses={courses} />;
                    case 'architecture': return <LifeArchitectureView backend={backend} goals={goals} />;
                    case 'habits': return <HabitMatrixView backend={backend} habits={habits} />;
                    case 'notes': return <NotesView backend={backend} notes={notes} />;
                    case 'flashcards': return <FlashcardsView backend={backend} flashcards={flashcards} courses={courses} />;
                    case 'momentum': return <MomentumMapView heatmap={heatmap} />;
                    case 'summary': return <DaySummaryView />;
                    case 'quiz': return <QuizEngineView />;
                    case 'settings': return <SettingsView settings={settings} setSettings={setSettings} backend={backend} />;
                    default: return <div className="text-white text-center mt-20 font-bold">Under Development</div>;
                }
            };

            return (
                <div className="h-screen w-screen flex overflow-hidden">
                    <div className="w-20 md:w-64 glass-panel-darker border-r border-white/10 flex flex-col py-6 z-50 shrink-0 rounded-none border-y-0 border-l-0 shadow-2xl">
                        <div className="px-4 md:px-8 mb-8 flex items-center justify-center md:justify-start gap-3">
                            <i className="fas fa-layer-group text-2xl text-blue-500"></i>
                            <h1 className="text-xl font-serif font-bold tracking-widest text-white uppercase hidden md:block">Mind Palace OS</h1>
                        </div>
                        <nav className="flex flex-col gap-1 px-2 md:px-4 overflow-y-auto flex-grow custom-scrollbar">
                            {[
                                { id: 'dashboard', icon: 'fa-th-large', label: 'Dashboard' },
                                { id: 'hub', icon: 'fa-bolt', label: 'Productivity Hub' },
                                { id: 'architecture', icon: 'fa-sitemap', label: 'Life Architecture' },
                                { id: 'habits', icon: 'fa-check-square', label: 'Habit Matrix' },
                                { id: 'notes', icon: 'fa-edit', label: 'Notes' },
                                { id: 'flashcards', icon: 'fa-clone', label: 'Flashcards' },
                                { id: 'quiz', icon: 'fa-question-circle', label: 'Quiz Engine' },
                                { id: 'momentum', icon: 'fa-chart-line', label: 'Momentum Map' },
                                { id: 'summary', icon: 'fa-calendar-day', label: 'Day Summary' },
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
        self.setWindowTitle("Shadow OS - React Minimalist Build")
        self.resize(1400, 900)
        self.browser = QWebEngineView()
        self.channel = QWebChannel()
        self.bridge = SystemBridge()
        self.channel.registerObject("backend", self.bridge)
        self.browser.page().setWebChannel(self.channel)
        self.browser.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.browser.setHtml(HTML_CONTENT, QUrl("qrc:/"))
        self.setCentralWidget(self.browser)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MindPalaceWebOS()
    window.show()
    sys.exit(app.exec())