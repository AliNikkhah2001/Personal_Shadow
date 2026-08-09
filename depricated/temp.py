import sys, sqlite3, json, os, requests, hashlib, cv2, markdown, urllib3, time, subprocess, random
from datetime import datetime, timedelta
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtMultimedia import QSoundEffect

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# [VIRTUAL MODULE] core/utils.py
# Helper functions for OS integrations and UI calculations.
# =====================================================================
def get_color(c_name): 
    if c_name == "Break": 
        return QColor(100,100,100,200)
    if not c_name or c_name == "None": 
        return QColor("#40c463")
    return QColor(f"#{hashlib.md5(c_name.encode()).hexdigest()[:6]}")

def render_latex(t, fs=14, c="white"):
    f = plt.figure(figsize=(0.01, 0.01))
    f.text(0,0, f"${t}$", fontsize=fs, color=c, ha='left', va='bottom')
    cvs = FigureCanvasAgg(f)
    cvs.draw()
    img = QImage(cvs.buffer_rgba(), cvs.get_width_height()[0], cvs.get_width_height()[1], QImage.Format.Format_RGBA8888)
    plt.close(f)
    return img

def get_active_app():
    try: 
        res = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'], capture_output=True, text=True)
        return res.stdout.strip()
    except: 
        return ""

def trigger_mac_notification(title, text):
    try:
        safe_text = text.replace("'", "").replace('"', '')
        subprocess.run(["osascript", "-e", f'display notification "{safe_text}" with title "{title}"'])
    except: 
        pass

def speak_text(text):
    try: 
        subprocess.Popen(["say", text])
    except: 
        pass

def max_volume():
    try: 
        subprocess.Popen(["osascript", "-e", "set volume output volume 100"])
    except: 
        pass


# =====================================================================
# [VIRTUAL MODULE] core/config.py
# Global state, defaults, and the config manager.
# =====================================================================
CS_QUOTES = [
    {"quote": "We can only see a short distance ahead, but we can see plenty there that needs to be done.", "author": "Alan Turing"},
    {"quote": "Sometimes it is the people no one can imagine anything of who do the things no one can imagine.", "author": "Alan Turing"},
    {"quote": "A distributed system is one in which the failure of a computer you didn't even know existed can render your own computer unusable.", "author": "Leslie Lamport"},
    {"quote": "Simplicity is prerequisite for reliability.", "author": "Edsger W. Dijkstra"},
    {"quote": "First, solve the problem. Then, write the code.", "author": "John Johnson"},
    {"quote": "Talk is cheap. Show me the code.", "author": "Linus Torvalds"},
    {"quote": "Premature optimization is the root of all evil.", "author": "Donald Knuth"},
    {"quote": "Complexity is the enemy of reliability.", "author": "Niklaus Wirth"}
]

class ConfigManager:
    def __init__(self, fn="config.json"):
        self.fn = fn
        self.defaults = {
            "font_family": "Helvetica Neue", "custom_font_path": "", "font_size": 16, 
            "clock_style": "Analog Classic", "clock_case": "Round", "clock_bezel": "Plain", 
            "clock_indices": "Baton", "clock_ticks": "Standard", "clock_hands": "Classic", "clock_comp": "None",
            "dist_delay": 3, "vision_mode": "Strict (Face & Eyes)", "bg_image_path": "", "quotes_path": "", 
            "panel_opacity": 180, "face_scale_factor": 1.2, "face_min_neighbors": 8, "face_min_size": 120, 
            "vision_sample_interval": 30, "force_close_apps_mins": 5, "sound_app_dist": "Ping", 
            "sound_cam_dist": "Basso", "sound_cam_err": "Hero", "beep_freq": 3,
            "loop_1m": 2, "loop_5m": 5, "loop_15m": 10, "loop_30m": 20, "loop_60m": 30,
            "speech_dist": "You have been distracted. Please return to work.",
            "speech_comp": "Fantastic job! Your deep work session is complete.",
            "deadline_name": "Goal",
            "deadline_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
        }
        try:
            with open(fn, 'r') as f:
                self.cfg = json.load(f)
        except:
            self.cfg = self.defaults.copy()
            
        for k, v in self.defaults.items():
            if self.cfg.get(k) is None:
                self.cfg[k] = v
                
    def get(self, k, d=None): 
        return self.cfg.get(k, d if d is not None else self.defaults.get(k))
        
    def set(self, k, v):
        self.cfg[k] = v
        with open(self.fn, 'w') as f:
            json.dump(self.cfg, f)

config = ConfigManager()


# =====================================================================
# [VIRTUAL MODULE] core/signals.py
# Global signal bus for decoupled component communication.
# =====================================================================
class SignalBus(QObject):
    db_updated = pyqtSignal()
    timer_tick = pyqtSignal(str, str, int)
    settings_changed = pyqtSignal()
    course_added = pyqtSignal()
    attention_alert = pyqtSignal(str)
    progress_update = pyqtSignal(float, float)
    active_color_changed = pyqtSignal(QColor)

bus = SignalBus()


# =====================================================================
# [VIRTUAL MODULE] core/database.py
# SQLite initialization and active migrations.
# =====================================================================
class DatabaseManager:
    def __init__(self, db_name="second_brain.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.c = self.conn.cursor()
        self.setup()
        
    def setup(self):
        self.c.executescript('''
            CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, task TEXT, is_done BOOLEAN, quadrant TEXT);
            CREATE TABLE IF NOT EXISTS pomodoro_sessions (id INTEGER PRIMARY KEY, course TEXT, duration INTEGER, actual_duration INTEGER, timestamp TEXT, type TEXT, distractions INTEGER DEFAULT 0, timelapse_path TEXT);
            CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT, timestamp TEXT);
            CREATE TABLE IF NOT EXISTS flashcards (id INTEGER PRIMARY KEY, course TEXT, front TEXT, back TEXT);
            CREATE TABLE IF NOT EXISTS saved_quizzes (id INTEGER PRIMARY KEY, title TEXT, course TEXT, filepath TEXT);
            CREATE TABLE IF NOT EXISTS exams (id INTEGER PRIMARY KEY, course TEXT, score INTEGER, total INTEGER, date TEXT);
            CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, course TEXT, duration INTEGER, type TEXT, list_order INTEGER, distractions TEXT, worked REAL, timelapse_path TEXT, start_time TEXT);
            CREATE TABLE IF NOT EXISTS starred_questions (id INTEGER PRIMARY KEY, course TEXT, question TEXT, data_json TEXT);
            CREATE TABLE IF NOT EXISTS course_targets (course TEXT PRIMARY KEY, target_hours REAL);
        ''')
        migrations = [
            "ALTER TABLE pomodoro_sessions ADD COLUMN actual_duration INTEGER", 
            "ALTER TABLE pomodoro_sessions ADD COLUMN distractions INTEGER DEFAULT 0", 
            "ALTER TABLE flashcards ADD COLUMN course TEXT", 
            "ALTER TABLE pomodoro_sessions ADD COLUMN timelapse_path TEXT", 
            "ALTER TABLE queue ADD COLUMN timelapse_path TEXT",
            "ALTER TABLE queue ADD COLUMN start_time TEXT",
            "ALTER TABLE courses ADD COLUMN target_hours REAL DEFAULT 0",
            "ALTER TABLE pomodoro_sessions ADD COLUMN distraction_data TEXT"
        ]
        for mig in migrations:
            try:
                self.c.execute(mig)
            except:
                pass
        self.conn.commit()

db = DatabaseManager()


# =====================================================================
# [VIRTUAL MODULE] workers/api_worker.py
# Background threads for fetching quotes and images.
# =====================================================================
class ApiWorker(QThread):
    quote_fetched = pyqtSignal(str)
    image_fetched = pyqtSignal(bytes)
    
    def run(self):
        qp = config.get("quotes_path", "")
        quotes = CS_QUOTES
        if qp and os.path.exists(qp):
            try:
                with open(qp, 'r') as f:
                    quotes = json.load(f)
            except:
                pass
                
        q = random.choice(quotes)
        self.quote_fetched.emit(f'"{q["quote"]}"\n— {q["author"]}')

        bp = config.get("bg_image_path", "")
        if bp and os.path.exists(bp):
            return
            
        try:
            ir = requests.get("https://picsum.photos/1920/1080?random=1", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5, allow_redirects=True)
            if ir.status_code == 200: 
                self.image_fetched.emit(ir.content)
        except: 
            pass


# =====================================================================
# [VIRTUAL MODULE] vision/tracker.py
# OpenCV Singleton for uninterrupted presence tracking & recording.
# =====================================================================
class VisionTracker(QObject):
    frame_ready = pyqtSignal(QImage)
    att_lost = pyqtSignal()
    att_restored = pyqtSignal()
    err_msg = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.tmr = QTimer()
        self.tmr.timeout.connect(self.process)
        self.lf = 0
        self.cap = None
        self.fc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml')
        self.ec = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        self.bg_sub = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=50, detectShadows=False)
        self.is_rec = False
        self.writer = None
        self.v_path = ""
        self.last_frame_time = 0

    def upd_settings(self):
        if self.tmr.isActive(): 
            self.tmr.setInterval(config.get("vision_sample_interval", 30))

    def start(self): 
        if self.cap is None or not self.cap.isOpened():
            for i in [0, 1]:
                tc = cv2.VideoCapture(i)
                if tc.isOpened(): 
                    self.cap = tc
                    break
        if self.cap and self.cap.isOpened():
            self.tmr.start(config.get("vision_sample_interval", 30))
        else:
            self.err_msg.emit("Camera Failed to Initialize")

    def stop(self):
        self.stop_rec()
        self.tmr.stop()
        if self.cap: 
            self.cap.release()
            self.cap = None
    
    def start_rec(self, path): 
        self.is_rec = True
        self.v_path = path
        self.last_frame_time = time.time()
        os.makedirs("timelapses", exist_ok=True)
        # 1 frame every 24 sec -> rendered at 15fps -> 1 hour = 10 sec video
        self.writer = cv2.VideoWriter(self.v_path, cv2.VideoWriter_fourcc(*'MJPG'), 15.0, (640, 480))
        
    def stop_rec(self): 
        self.is_rec = False
        if self.writer: 
            self.writer.release()
            self.writer = None

    def process(self):
        att = False
        mode = str(config.get("vision_mode", "Strict (Face & Eyes)"))
        scale = config.get("face_scale_factor", 1.2)
        min_n = config.get("face_min_neighbors", 8)
        min_s = config.get("face_min_size", 120)
        
        if not self.cap or not self.cap.isOpened():
            self.err_msg.emit("Camera Failed!")
            self.att_lost.emit()
            return
            
        ret, frm = self.cap.read()
        
        # Hardware drop or pitch-black privacy shutter detection
        if not ret or frm is None:
            self.err_msg.emit("Feed dropped!")
            self.att_lost.emit()
            return
            
        if np.mean(frm) < 2.0:
            self.err_msg.emit("Camera Feed Blank (Off/Covered)!")
            self.att_lost.emit()
            return
        
        gray = cv2.equalizeHist(cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY))
        
        if self.is_rec and self.writer:
            curr = time.time()
            if curr - self.last_frame_time >= 24.0:
                frm_resized = cv2.resize(frm, (640, 480))
                self.writer.write(frm_resized)
                self.last_frame_time = curr
            
        if "Presence" in mode:
            fg = self.bg_sub.apply(cv2.GaussianBlur(gray, (21, 21), 0))
            _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
            if cv2.countNonZero(fg) > 3000 or len(self.fc.detectMultiScale(gray, scale, min_n, minSize=(min_s,min_s))) > 0: 
                att = True
        else:
            faces = self.fc.detectMultiScale(gray, scale, min_n, minSize=(min_s,min_s))
            if len(faces) > 0:
                (x,y,w,h) = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)[0]
                cv2.rectangle(frm, (x,y), (x+w,y+h), (0,255,0), 2)
                if "Visible" in mode: 
                    att = True
                else:
                    eyes = self.ec.detectMultiScale(gray[y:y+int(h/2), x:x+w], 1.1, 10, minSize=(20,20))
                    if len(eyes) > 0: 
                        att = True
        
        rgb = cv2.cvtColor(frm, cv2.COLOR_BGR2RGB)
        self.frame_ready.emit(QImage(rgb.data, rgb.shape[1], rgb.shape[0], QImage.Format.Format_RGB888))

        fps = max(1, 1000 // config.get("vision_sample_interval", 30))
        delay_frames = int(config.get("dist_delay", 3)) * fps
        was_lost = self.lf >= delay_frames
        
        if not att: 
            self.lf = min(self.lf + 1, delay_frames)
        else: 
            self.lf = max(self.lf - max(1, fps // 2), 0)
            
        is_lost = self.lf >= delay_frames
        if is_lost and not was_lost: 
            self.att_lost.emit()
        elif not is_lost and was_lost: 
            self.att_restored.emit()


# =====================================================================
# [VIRTUAL MODULE] ui/horology.py
# The high-end clock rendering engine (Bezels, Cases, Dials, Hands).
# =====================================================================
def draw_horological_hands(p, style, length, w, is_hour=False):
    c = p.brush().color()
    length = int(length)
    w = int(w)
    
    if style == "Spade":
        p.setPen(QPen(c, 2))
        p.drawLine(0, 0, 0, -length + 15)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(-6, -length+3, 12, 12)
    elif style == "Breguet":
        p.setPen(QPen(c, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(0, 0, 0, -length + 12)
        p.drawEllipse(-4, -length+4, 8, 8)
        p.drawLine(0, -length+4, 0, -length)
        p.setBrush(QBrush(c))
        p.setPen(Qt.PenStyle.NoPen)
    elif style == "Dauphine":
        p.drawConvexPolygon([QPoint(-w*2, 0), QPoint(w*2, 0), QPoint(0, -length)])
    elif style == "Alpha":
        p.drawConvexPolygon([QPoint(-w*2, -10), QPoint(w*2, -10), QPoint(0, -length)])
        p.setPen(QPen(c, 2))
        p.drawLine(0, 0, 0, -10)
        p.setPen(Qt.PenStyle.NoPen)
    elif style == "Pencil":
        p.drawRect(-w, 0, w*2, -length+5)
        p.drawConvexPolygon([QPoint(-w, -length+5), QPoint(w, -length+5), QPoint(0, -length)])
    elif style == "Serpentine":
        p.setPen(QPen(c, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(0, 0)
        path.cubicTo(w*4, -length//3, -w*4, -length*2//3, 0, -length)
        p.strokePath(path, p.pen())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(c))
    elif style == "Mercedes":
        p.setPen(QPen(c, 2))
        p.drawLine(0, 0, 0, int(-length*0.5))
        if is_hour:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(int(-w*1.5), int(-length*0.7), int(w*3), int(w*3))
            p.drawLine(0, int(-length*0.55), 0, int(-length*0.7))
            p.drawLine(0, int(-length*0.55), int(-w*1.2), int(-length*0.6))
            p.drawLine(0, int(-length*0.55), int(w*1.2), int(-length*0.6))
            p.setBrush(QBrush(c))
        p.setPen(Qt.PenStyle.NoPen)
    elif style == "Sword":
        p.drawConvexPolygon([QPoint(int(-w//2), 0), QPoint(int(-w*2), int(-length*0.6)), QPoint(0, -length), QPoint(int(w*2), int(-length*0.6)), QPoint(int(w//2), 0)])
    elif style == "Arrow":
        p.setPen(QPen(c, max(1, w//2)))
        p.drawLine(0, 0, 0, int(-length*0.7))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawConvexPolygon([QPoint(int(-w*2.5), int(-length*0.7)), QPoint(int(w*2.5), int(-length*0.7)), QPoint(0, -length)])
    elif style == "Baton":
        p.drawRect(-w, 0, w*2, -length)
    else:
        p.drawConvexPolygon([QPoint(-w, 8), QPoint(w, 8), QPoint(0, -length)])

def draw_horological_face(p, radius, cfg):
    case = cfg.get("clock_case", "Round")
    bezel = cfg.get("clock_bezel", "Plain")
    ticks = cfg.get("clock_ticks", "Standard")
    indices = cfg.get("clock_indices", "Baton")
    comp = cfg.get("clock_comp", "None")
    
    if bezel == "Fluted":
        p.setPen(QPen(QColor(200,200,200,100), 2))
        for i in range(60): 
            p.drawLine(0, radius, 0, radius+5)
            p.rotate(6)
    elif bezel == "Diver":
        p.setPen(QPen(QColor(30,30,30,250), 10))
        p.drawEllipse(int(-radius-5), int(-radius-5), int(radius*2+10), int(radius*2+10))
        p.setPen(QColor("white"))
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        for i in range(0, 60, 10):
            if i == 0: 
                p.drawConvexPolygon([QPoint(-5, int(-radius-10)), QPoint(5, int(-radius-10)), QPoint(0, -radius)])
            else: 
                p.drawText(QRect(-10, int(-radius-15), 20, 20), Qt.AlignmentFlag.AlignCenter, str(i))
            p.rotate(60)
    elif bezel == "GMT":
        p.setPen(QPen(QColor(200, 0, 0, 200), 8))
        p.drawArc(int(-radius-4), int(-radius-4), int(radius*2+8), int(radius*2+8), 0, 180*16)
        p.setPen(QPen(QColor(0, 0, 200, 200), 8))
        p.drawArc(int(-radius-4), int(-radius-4), int(radius*2+8), int(radius*2+8), 180*16, 180*16)
    elif bezel == "Coin-Edge":
        p.setPen(QPen(QColor(150,150,150,150), 1))
        for i in range(120): 
            p.drawLine(0, radius, 0, radius+3)
            p.rotate(3)

    p.setPen(QPen(QColor(255,255,255,80), 2))
    p.setBrush(QBrush(QColor(15,15,17,200)))
    
    if case == "Square": 
        p.drawRect(int(-radius), int(-radius), int(radius*2), int(radius*2))
    elif case == "Cushion": 
        p.drawRoundedRect(int(-radius), int(-radius), int(radius*2), int(radius*2), 30, 30)
    elif case == "Tonneau": 
        p.drawRoundedRect(int(-radius*0.85), int(-radius), int(radius*1.7), int(radius*2), 20, 40)
    else: 
        p.drawEllipse(int(-radius), int(-radius), int(radius*2), int(radius*2))

    if ticks != "Clean":
        p.save()
        if ticks == "Railroad":
            p.setPen(QPen(QColor(255,255,255,100), 1))
            p.drawEllipse(int(-radius+5), int(-radius+5), int(radius*2-10), int(radius*2-10))
            p.drawEllipse(int(-radius+12), int(-radius+12), int(radius*2-24), int(radius*2-24))
        for i in range(60):
            if i % 5 == 0: 
                p.setPen(QPen(QColor(255,255,255,180), 2))
                p.drawLine(int(radius-12), 0, int(radius-5), 0)
            else: 
                p.setPen(QPen(QColor(255,255,255,60), 1))
                p.drawLine(int(radius-8), 0, int(radius-5), 0)
            p.rotate(6.0)
        p.restore()
        if ticks == "Crosshair":
            p.setPen(QPen(QColor(255,255,255,40), 1))
            p.drawLine(int(-radius+15), 0, int(radius-15), 0)
            p.drawLine(0, int(-radius+15), 0, int(radius-15))

    if indices != "None":
        p.save()
        p.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        p.setPen(QPen(QColor("white")))
        for i in range(1, 13):
            angle = (i * 30 - 90) * np.pi / 180
            r_ind = radius - 22
            x, y = r_ind * np.cos(angle), r_ind * np.sin(angle)
            if indices == "Baton": 
                p.save()
                p.translate(x, y)
                p.rotate(i*30)
                p.drawRect(-2, -5, 4, 10)
                p.restore()
            elif indices == "Dot":
                if i in [3,6,9]: 
                    p.save()
                    p.translate(x, y)
                    p.rotate(i*30)
                    p.drawRect(-2, -6, 4, 12)
                    p.restore()
                elif i == 12: 
                    p.drawConvexPolygon([QPoint(int(x), int(y-8)), QPoint(int(x-6), int(y+6)), QPoint(int(x+6), int(y+6))])
                else: 
                    p.drawEllipse(int(x-4), int(y-4), 8, 8)
            else:
                if indices == "California": 
                    text = ["I","II","III","4","5","6","7","8","9","X","XI","XII"][i-1]
                else: 
                    text = str(i) if indices == "Arabic" else ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"][i-1]
                p.drawText(QRect(int(x)-15, int(y)-15, 30, 30), Qt.AlignmentFlag.AlignCenter, text)
        p.restore()

    if comp == "Date Window":
        p.setBrush(QBrush(QColor("white")))
        p.setPen(QPen(QColor("black")))
        p.drawRect(int(radius-45), -10, 25, 20)
        p.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        p.drawText(QRect(int(radius-45), -10, 25, 20), Qt.AlignmentFlag.AlignCenter, str(datetime.now().day))
    elif comp == "Small Seconds":
        p.setPen(QPen(QColor(255,255,255,80), 1))
        p.drawEllipse(-20, int(radius-50), 40, 40)


# =====================================================================
# [VIRTUAL MODULE] ui/charts.py
# Smaller analytical widgets, calendars, and timelines.
# =====================================================================
class MiniTimeline(QWidget):
    def __init__(self, b):
        super().__init__()
        self.b = b
        self.setFixedHeight(30)
        
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        d = self.b['duration']
        
        if d <= 0: return
            
        col = get_color(self.b['course'])
        p.setBrush(QBrush(col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 4, 4)
        
        for item in self.b.get('distractions', []):
            ds = item[0]
            dd = item[1]
            dtype = item[2] if len(item) > 2 else "Manual"
            
            rx = int((ds/d)*w)
            rw = int((dd/d)*w)
            
            gap_col = QColor("#f1c40f")
            if dtype == "App": gap_col = QColor("#ff8c00")
            elif dtype == "Camera": gap_col = QColor("#e74c3c")
            elif dtype == "CameraError": gap_col = QColor("#800080")
            
            p.setBrush(gap_col)
            p.drawRoundedRect(rx, 0, max(rw, 2), h, 0, 0)

class GanttTimelineWidget(QWidget):
    def __init__(self): 
        super().__init__()
        self.setMinimumHeight(150)
        self.q = []
        self.cidx = -1
        self.hitboxes = []
        
    def update_t(self, q, idx): 
        self.q = q
        self.cidx = idx
        self.update()
        self.setMinimumHeight(max(150, len(set(x['course'] for x in q)) * 40 + 50))
        
    def paintEvent(self, e):
        self.hitboxes.clear()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.q: return
        
        past_mins = 0
        if self.cidx >= 0 and self.cidx < len(self.q):
            b_cur = self.q[self.cidx]
            past_mins = b_cur.get('worked', 0) + sum(d[1] for d in b_cur.get('distractions', []))
            
        future_mins = sum((b['duration'] - b.get('worked', 0)) for i, b in enumerate(self.q) if i >= self.cidx)
        t_mins = past_mins + future_mins
        if t_mins <= 0: return
        
        crs = list(set(x['course'] for x in self.q))
        rh, hw, w = 40, 90, self.width() - 110
        
        p.setPen(QPen(QColor(255, 255, 255, 40)))
        p.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        for i, c in enumerate(crs): 
            p.drawText(5, i*rh + 35, c[:10]+"..")
            p.drawLine(hw, i*rh + 40, hw + w, i*rh + 40)
            
        cx = hw
        scls = w / t_mins
        p.setPen(QPen(QColor(255, 255, 255, 20), 1, Qt.PenStyle.DashLine))
        now = datetime.now()
        start_time = now - timedelta(minutes=past_mins)
        mst = start_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        while mst < start_time + timedelta(minutes=t_mins):
            dx = hw + ((mst - start_time).total_seconds()/60.0) * scls
            p.drawLine(int(dx), 0, int(dx), len(crs)*rh + 20)
            p.setFont(QFont("Arial", 7))
            p.drawText(int(dx)-10, 15, mst.strftime('%H:00'))
            mst += timedelta(hours=1)
            
        for i in range(self.cidx, len(self.q)):
            b = self.q[i]
            if i == self.cidx:
                rem_dur = max(0, b['duration'] - b.get('worked', 0))
                start_cx = cx
                col = get_color(b['course'])
                col.setAlpha(255)
                ridx = crs.index(b['course'])
                cy = ridx * rh + 10
                
                p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                p.setPen(QPen(Qt.GlobalColor.white))
                p.drawText(int(cx), len(crs)*rh + 20, start_time.strftime('%H:%M'))
                
                w_drwn = 0
                for item in b.get('distractions', []):
                    ds, dd = item[0], item[1]
                    dtype = item[2] if len(item) > 2 else "Manual"
                    ww = (ds - w_drwn) * scls
                    
                    if ww > 0: 
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(QBrush(col))
                        p.drawRoundedRect(int(cx), int(cy), int(max(ww,2)), int(rh-15), 4, 4)
                        cx += ww
                        
                    gw = dd * scls
                    if gw > 0:
                        dd_secs = dd * 60
                        if dtype == "App":
                            if dd_secs < 30: gap_col = QColor(255, 204, 128)
                            elif dd_secs < 60: gap_col = QColor(255, 170, 0)
                            elif dd_secs < 300: gap_col = QColor(204, 102, 0)
                            else: gap_col = QColor(128, 51, 0)
                        elif dtype == "Camera":
                            if dd_secs < 30: gap_col = QColor(255, 153, 153)
                            elif dd_secs < 60: gap_col = QColor(255, 77, 77)
                            elif dd_secs < 300: gap_col = QColor(204, 0, 0)
                            else: gap_col = QColor(128, 0, 0)
                        elif dtype == "CameraError":
                            if dd_secs < 30: gap_col = QColor(216, 191, 216)
                            elif dd_secs < 60: gap_col = QColor(218, 112, 214)
                            elif dd_secs < 300: gap_col = QColor(128, 0, 128)
                            else: gap_col = QColor(75, 0, 130)
                        else:
                            if dd_secs < 30: gap_col = QColor(249, 231, 159)
                            elif dd_secs < 60: gap_col = QColor(241, 196, 15)
                            elif dd_secs < 300: gap_col = QColor(212, 172, 13)
                            else: gap_col = QColor(125, 102, 8)
                            
                        p.setPen(QPen(gap_col, 2))
                        p.drawLine(int(cx), int(cy + (rh-15)/2), int(cx + gw), int(cy + (rh-15)/2))
                        p.drawLine(int(cx), int(cy), int(cx), int(cy + rh - 15))
                        p.drawLine(int(cx + gw), int(cy), int(cx + gw), int(cy + rh - 15))
                        
                        if dd >= 5: 
                            p.setFont(QFont("Arial", 7, QFont.Weight.Bold))
                            p.drawText(QRect(int(cx), int(cy - 12), int(gw), 12), Qt.AlignmentFlag.AlignCenter, f"{dd:.1f}m")
                        cx += gw
                    w_drwn = ds
                    
                if rem_dur > 0: 
                    pw = rem_dur * scls
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QBrush(col))
                    p.drawRoundedRect(int(cx), int(cy), int(max(pw,2)), int(rh-15), 4, 4)
                    cx += pw
                    
                self.hitboxes.append((QRect(int(start_cx), int(cy), int(max(cx-start_cx, 2)), int(rh-15)), b))
            else:
                rem_dur = b['duration'] - b.get('worked', 0)
                if rem_dur <= 0: continue
                start_cx = cx
                col = get_color(b['course'])
                col.setAlpha(180)
                cy = crs.index(b['course']) * rh + 10
                pw = rem_dur * scls
                p.setBrush(QBrush(col))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(int(cx), int(cy), int(max(pw,2)), int(rh-15), 4, 4)
                cx += pw
                self.hitboxes.append((QRect(int(start_cx), int(cy), int(max(cx-start_cx, 2)), int(rh-15)), b))
                
        p.setPen(QPen(Qt.GlobalColor.white))
        p.drawText(int(cx)-35, len(crs)*rh + 20, (start_time + timedelta(minutes=t_mins)).strftime('%H:%M'))

class CircularProgress(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(140, 140)
        self.st = 0
        self.pl = 1
        self.ring_color = QColor("#0a84ff")
        bus.progress_update.connect(self.set_val)
        bus.active_color_changed.connect(self.set_color)
        
    def set_color(self, c): 
        self.ring_color = c
        self.update()
        
    def set_val(self, s, p): 
        self.st = s
        self.pl = max(p, 1)
        self.update()
        
    def paintEvent(self, e):
        pt = QPainter(self)
        pt.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRect(10, 10, 120, 120)
        pt.setPen(QPen(QColor(255,255,255,30), 10))
        pt.drawArc(r, 0, 360*16)
        pct = min(self.st / self.pl, 1.0)
        pt.setPen(QPen(self.ring_color, 10, cap=Qt.PenCapStyle.RoundCap))
        pt.drawArc(r, 90*16, int(-pct * 360 * 16))
        pt.setPen(QColor("white"))
        pt.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        pt.drawText(QRect(10, 30, 120, 40), Qt.AlignmentFlag.AlignCenter, f"{int(pct*100)}%")
        pt.setFont(QFont("Arial", 9))
        pt.setPen(QColor(200, 200, 200))
        pt.drawText(QRect(10, 70, 120, 40), Qt.AlignmentFlag.AlignCenter, f"{int(self.st)}/{int(self.pl)}m")

class AnalogClock(QWidget):
    def __init__(self): 
        super().__init__()
        self.setFixedSize(200, 200)
        self.ring_color = QColor("#0a84ff")
        bus.active_color_changed.connect(self.set_color)
        
    def set_color(self, c): 
        self.ring_color = c
        self.update()
        
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width()/2, self.height()/2)
        
        draw_horological_face(p, 95, config.cfg)
        
        t = QTime.currentTime()
        h_style = config.get("clock_hands", "Classic")
        comp = config.get("clock_comp", "None")
        
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("white")))
        
        p.save()
        p.rotate(30.0 * (t.hour() + t.minute()/60.0))
        draw_horological_hands(p, h_style, 50, 4, True)
        p.restore()
        
        p.save()
        p.rotate(6.0 * (t.minute() + t.second()/60.0))
        draw_horological_hands(p, h_style, 75, 3, False)
        p.restore()
        
        sec_col = self.ring_color
        if comp == "Small Seconds": 
            p.save()
            p.translate(0, 45)
            p.rotate(6.0 * t.second())
            p.setBrush(QBrush(sec_col))
            draw_horological_hands(p, "Baton", 18, 1, False)
            p.restore()
        else:
            p.setBrush(QBrush(sec_col))
            p.setPen(QPen(sec_col, 2))
            p.save()
            p.rotate(6.0 * t.second())
            if h_style in ["Serpentine", "Arrow", "Sword"]: 
                draw_horological_hands(p, h_style, 85, 1, False)
            else: 
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRect(-1, 0, 2, -85)
            p.restore()
            
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(-4, -4, 8, 8)

class DashboardGoalsWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("GlassPanel")
        self.setFixedSize(350, 320)
        self.lay = QVBoxLayout(self)
        self.lbl_tot = QLabel("Global Target: 0 / 0 hrs (0%)")
        self.lbl_tot.setStyleSheet("font-weight: bold; font-size: 16px; color: #0a84ff;")
        self.lay.addWidget(self.lbl_tot)
        
        self.bars_lay = QVBoxLayout()
        self.lay.addLayout(self.bars_lay)
        self.lay.addStretch()
        self.upd()
        bus.db_updated.connect(self.upd)
        
    def upd(self):
        for i in reversed(range(self.bars_lay.count())):
            w = self.bars_lay.itemAt(i).widget()
            if w:
                w.deleteLater()
                
        db.c.execute("SELECT name FROM courses")
        courses = [r[0] for r in db.c.fetchall()]
        
        db.c.execute("SELECT course, target_hours FROM course_targets")
        targets_db = {r[0]: r[1] for r in db.c.fetchall()}
        targets = {c: targets_db.get(c, 0.0) for c in courses}
        
        db.c.execute("SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY course")
        studied = {r[0]: (r[1] or 0)/60.0 for r in db.c.fetchall()}
        
        tot_tgt = sum(targets.values())
        tot_std = sum(studied.get(c, 0.0) for c in courses)
        pct = min(100, int((tot_std/tot_tgt)*100)) if tot_tgt > 0 else 0
        self.lbl_tot.setText(f"Global Target: {tot_std:.1f} / {tot_tgt:.1f} hrs ({pct}%)")
        
        rem_list = []
        for c, tgt in targets.items(): 
            rem_list.append((c, max(0, tgt - studied.get(c, 0.0)), studied.get(c, 0.0), tgt))
            
        rem_list.sort(key=lambda x: x[1], reverse=True)
        
        for c, rem, std, tgt in rem_list[:4]:
            lbl = QLabel(f"{c[:15]} - Rem: {rem:.1f}h")
            lbl.setFont(QFont("Arial", 10))
            pb = QProgressBar()
            pb.setMaximum(100)
            pb.setValue(min(100, int((std/tgt)*100)) if tgt > 0 else 0)
            pb.setFixedHeight(12)
            pb.setTextVisible(False)
            pb.setStyleSheet(f"QProgressBar {{ background-color: rgba(255,255,255,10); border-radius: 4px; }} QProgressBar::chunk {{ background-color: {get_color(c).name()}; border-radius: 4px; }}")
            self.bars_lay.addWidget(lbl)
            self.bars_lay.addWidget(pb)

class FocusCalendar(QCalendarWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("QCalendarWidget QWidget { alternate-background-color: rgba(255,255,255,10); } QCalendarWidget QAbstractItemView:enabled { color: white; background-color: rgba(10,10,15,160); selection-background-color: #0a84ff; }")
        self.fd = {}
        self.upd()
        bus.db_updated.connect(self.upd)
        
    def upd(self): 
        db.c.execute("SELECT date(timestamp), sum(duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY date(timestamp)")
        self.fd = {r[0]: r[1]/60.0 for r in db.c.fetchall()}
        
    def paintCell(self, p, r, d):
        super().paintCell(p, r, d)
        ds = d.toString("yyyy-MM-dd")
        if ds in self.fd:
            h = self.fd[ds]
            cg = QColor("#ebedf0")
            if h > 0: cg = QColor("#9be9a8")
            if h > 2: cg = QColor("#40c463")
            if h > 4: cg = QColor("#30a14e")
            if h > 6: cg = QColor("#216e39")
            p.fillRect(r, cg)
            p.setPen(QColor("black" if h < 6 else "white"))
            p.drawText(r, Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignRight, f"{h:.1f}h")

class ActivityHeatmap(FigureCanvas):
    def __init__(self):
        self.f, self.ax = plt.subplots(figsize=(6, 2.5), facecolor='none')
        super().__init__(self.f)
        self.setStyleSheet("background-color:transparent;")
        self.upd()
        bus.db_updated.connect(self.upd)
        
    def upd(self):
        self.ax.clear()
        td = datetime.now().date()
        dts = [(td - timedelta(days=i)).isoformat() for i in range(35)] 
        
        db.c.execute("SELECT date(timestamp), sum(duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY date(timestamp)")
        cnts = dict(db.c.fetchall())
        
        mat = np.zeros((5, 7))
        hmat = np.zeros((5, 7))
        
        for i, d in enumerate(dts): 
            h = cnts.get(d, 0)/60.0
            mat[i//7, i%7] = min(h, 8)
            hmat[i//7, i%7] = h
            
        self.ax.imshow(mat, cmap='Greens', aspect='auto', vmin=0, vmax=8)
        self.ax.axis('off')
        
        for i in range(5):
            for j in range(7):
                if hmat[i,j] > 0: 
                    self.ax.text(j, i, f"{hmat[i,j]:.1f}h", ha="center", va="center", color="white" if mat[i,j]>4 else "black", fontsize=8, fontweight='bold')
        self.draw()

class MomentumMap(FigureCanvas):
    def __init__(self):
        self.f, self.axs = plt.subplots(3, 2, figsize=(10, 9))
        self.f.patch.set_facecolor('#1e1e23')
        super().__init__(self.f)
        self.setStyleSheet("background-color:transparent;")
        self.upd()
        bus.db_updated.connect(self.upd)
        
    def upd(self):
        for ax in self.axs.flat: 
            ax.clear()
            ax.set_facecolor('#1e1e23')
            ax.tick_params(colors='white')
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            ax.spines['bottom'].set_color('#555')
            ax.spines['left'].set_color('#555')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
        ax1 = self.axs[0,0]
        ax1.set_title("35-Day Consistency", color="white")
        td = datetime.now().date()
        dts = [(td - timedelta(days=i)).isoformat() for i in range(35)] 
        db.c.execute("SELECT date(timestamp), sum(duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY date(timestamp)")
        cnts = dict(db.c.fetchall())
        mat = np.zeros((5, 7))
        hmat = np.zeros((5, 7))
        for i, d in enumerate(dts): 
            h = cnts.get(d, 0)/60.0
            mat[i//7, i%7] = min(h, 8)
            hmat[i//7, i%7] = h
        ax1.imshow(mat, cmap='Greens', aspect='auto', vmin=0, vmax=8)
        ax1.axis('off')
        for i in range(5):
            for j in range(7):
                if hmat[i,j] > 0: 
                    ax1.text(j, i, f"{hmat[i,j]:.1f}h", ha="center", va="center", color="white" if mat[i,j]>4 else "black", fontsize=8, fontweight='bold')
                    
        ax2 = self.axs[0,1]
        ax2.set_title("Study Volume by Hour", color="white")
        db.c.execute("SELECT strftime('%H', timestamp), sum(duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY strftime('%H', timestamp)")
        h_data = {int(r[0]): r[1] for r in db.c.fetchall()}
        hours = list(range(24))
        vols = [h_data.get(h,0) for h in hours]
        ax2.bar(hours, vols, color="#40c463")
        ax2.set_xlim(-1, 24)
        ax2.set_ylabel("Mins")
        
        ax3 = self.axs[1,0]
        ax3.set_title("Distraction Severity Breakdown", color="white")
        db.c.execute("SELECT distraction_data FROM pomodoro_sessions WHERE type='Work' AND distraction_data IS NOT NULL")
        bins = {"<30s": 0, "<1m": 0, "<5m": 0, "<15m": 0, ">=15m": 0}
        for row in db.c.fetchall():
            if row[0]:
                try:
                    darr = json.loads(row[0])
                    for d in darr:
                        dur_mins = d[1]
                        if dur_mins < 0.5: bins["<30s"] += 1
                        elif dur_mins < 1: bins["<1m"] += 1
                        elif dur_mins < 5: bins["<5m"] += 1
                        elif dur_mins < 15: bins["<15m"] += 1
                        else: bins[">=15m"] += 1
                except: pass
        
        labels = list(bins.keys())
        values = list(bins.values())
        if sum(values) > 0:
            ax3.bar(labels, values, color="#0a84ff")
        else:
            ax3.text(0.5, 0.5, "No Data", ha='center', va='center', color='gray')
            ax3.axis('off')
        
        ax4 = self.axs[1,1]
        ax4.set_title("Avg Distractions by Hour", color="white")
        db.c.execute("SELECT strftime('%H', timestamp), avg(distractions) FROM pomodoro_sessions WHERE type='Work' GROUP BY strftime('%H', timestamp)")
        dh_data = {int(r[0]): r[1] for r in db.c.fetchall()}
        d_vols = [dh_data.get(h,0) for h in hours]
        ax4.plot(hours, d_vols, color="#ff453a", marker='o')
        ax4.set_xlim(-1, 24)
        ax4.set_ylabel("Avg Distracts")
        
        ax5 = self.axs[2,0]
        ax5.set_title("Actual vs Planned Time (Last 10)", color="white")
        db.c.execute("SELECT id, duration, actual_duration, type FROM pomodoro_sessions ORDER BY id DESC LIMIT 10")
        recs = db.c.fetchall()[::-1]
        ids = [f"{r[3][0]}{r[0]}" for r in recs]
        plan = [r[1] for r in recs]
        act = [r[2] if r[2] else r[1] for r in recs]
        if ids:
            x_pos = np.arange(len(ids))
            w = 0.35
            ax5.bar(x_pos - w/2, plan, w, label='Planned', color='#0a84ff')
            ax5.bar(x_pos + w/2, act, w, label='Actual', color='#ff453a')
            ax5.set_xticks(x_pos)
            ax5.set_xticklabels(ids, rotation=45, fontsize=8)
            ax5.legend(loc="upper left", fontsize=8)
            
        ax6 = self.axs[2,1]
        ax6.set_title("Distraction Types Breakdown", color="white")
        db.c.execute("SELECT distraction_data FROM pomodoro_sessions WHERE type='Work' AND distraction_data IS NOT NULL")
        dtypes = {"App": 0, "Camera": 0, "CameraError": 0, "Manual": 0}
        for row in db.c.fetchall():
            if row[0]:
                try:
                    darr = json.loads(row[0])
                    for d in darr:
                        dt = d[2] if len(d) > 2 else "Manual"
                        dtypes[dt] = dtypes.get(dt, 0) + 1
                except: pass
                
        labels = [k for k, v in dtypes.items() if v > 0]
        sizes = [v for k, v in dtypes.items() if v > 0]
        colors_map = {"App": "#ffaa00", "Camera": "#ff4d4d", "CameraError": "#800080", "Manual": "#f1c40f"}
        cols = [colors_map.get(l, "#fff") for l in labels]
        
        if sizes:
            ax6.pie(sizes, labels=labels, colors=cols, autopct='%1.1f%%', textprops={'color':"w", 'fontsize':8})
            ax6.axis('equal')
        else:
            ax6.text(0.5, 0.5, "No Distraction Data", ha='center', va='center', color='gray')
            ax6.axis('off')
        
        self.f.tight_layout()
        self.draw()


# =====================================================================
# [VIRTUAL MODULE] ui/dialogs.py
# Workflow blockers, session start checks, and setting overlays.
# =====================================================================
class SessionStartDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Session Readiness")
        self.setFixedSize(400, 150)
        self.setStyleSheet("background-color: #0f0f11; color: white;")
        lay = QVBoxLayout(self)
        
        self.lbl = QLabel("Are you ready to begin focus? (30s)")
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #ff9f0a;")
        lay.addWidget(self.lbl)
        
        self.btn = QPushButton("Yes, I am positioned and ready.")
        self.btn.setStyleSheet("background-color: #0a84ff; font-size: 16px; padding: 10px; border-radius: 8px;")
        self.btn.clicked.connect(self.accept)
        lay.addWidget(self.btn)
        
        self.time_left = 30
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        
    def tick(self):
        self.time_left -= 1
        if self.time_left <= 0: 
            self.reject()
        else: 
            self.lbl.setText(f"Are you ready to begin focus? ({self.time_left}s)")
            
    def closeEvent(self, e): 
        self.timer.stop()
        self.reject()
        super().closeEvent(e)

class WebcamCheckDialog(QDialog):
    def __init__(self, vtr, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Webcam Alignment")
        self.setFixedSize(640, 560)
        self.setStyleSheet("background-color: #0f0f11; color: white;")
        self.vtr = vtr
        self.valid_frame = False
        
        lay = QVBoxLayout(self)
        self.lbl = QLabel("Initializing Camera...")
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl.setFixedSize(640, 480)
        lay.addWidget(self.lbl)
        
        self.btn = QPushButton("Waiting for feed...")
        self.btn.clicked.connect(self.manual_accept)
        self.btn.setStyleSheet("background-color: #0a84ff; font-weight: bold; padding: 10px; border-radius: 5px;")
        lay.addWidget(self.btn)
        
        self.time_left = 5
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.vtr.frame_ready.connect(self.update_frame)
        self.vtr.start()
        self.timer.start(1000)

    def manual_accept(self):
        if self.valid_frame:
            self.accept()
        else:
            self.lbl.setText("Waiting for valid camera feed to start...")
        
    def tick(self):
        self.time_left -= 1
        if self.time_left <= 0: 
            if self.valid_frame:
                self.accept()
            else:
                self.reject()
        else:
            if self.valid_frame:
                self.btn.setText(f"Accept ({self.time_left}s)")
            else:
                self.btn.setText(f"Waiting for feed ({self.time_left}s)")
            
    def update_frame(self, img): 
        self.valid_frame = True
        self.lbl.setPixmap(QPixmap.fromImage(img).scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio))
        
    def closeEvent(self, e): 
        self.timer.stop()
        self.vtr.frame_ready.disconnect(self.update_frame)
        self.reject()
        super().closeEvent(e)

class AutoPlanDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Weighted Auto-Plan Day")
        self.setMinimumWidth(500)
        self.setStyleSheet("background-color: #0f0f11; color: white;")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Select Courses and Assign Weights (0.1 to 10.0):"))
        
        self.sa = QScrollArea()
        self.sa.setWidgetResizable(True)
        self.cw = QWidget()
        self.grid = QVBoxLayout(self.cw)
        self.sa.setWidget(self.cw)
        lay.addWidget(self.sa)
        
        self.course_rows = []
        db.c.execute("SELECT name FROM courses")
        courses_db = [r[0] for r in db.c.fetchall()]
        
        db.c.execute("SELECT course, target_hours FROM course_targets")
        targets_db = {r[0]: r[1] for r in db.c.fetchall()}
        
        db.c.execute("SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY course")
        studied = {r[0]: (r[1] or 0)/60.0 for r in db.c.fetchall()}
        
        for name in courses_db:
            tgt = targets_db.get(name, 0.0)
            row = QHBoxLayout()
            cb = QCheckBox(name)
            cb.setChecked(True)
            row.addWidget(cb)
            
            done = studied.get(name, 0.0)
            rem = max(0, tgt - done)
            pct = min(100, int((done/tgt)*100)) if tgt > 0 else 0
            row.addWidget(QLabel(f"Rem: {rem:.1f}h ({pct}%)"))
            row.addStretch()
            
            row.addWidget(QLabel("Weight:"))
            sp = QDoubleSpinBox()
            sp.setRange(0.1, 10.0)
            sp.setValue(1.0)
            sp.setSingleStep(0.1)
            row.addWidget(sp)
            
            self.grid.addLayout(row)
            self.course_rows.append((cb, name, sp))
            
        hl1 = QHBoxLayout()
        hl1.addWidget(QLabel("Total Study Target (mins):"))
        self.tot_m = QSpinBox()
        self.tot_m.setRange(10, 1440)
        self.tot_m.setValue(120)
        hl1.addWidget(self.tot_m)
        lay.addLayout(hl1)
        
        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("Work Block (mins):"))
        self.wk_m = QSpinBox()
        self.wk_m.setRange(5, 240)
        self.wk_m.setValue(45)
        hl2.addWidget(self.wk_m)
        lay.addLayout(hl2)
        
        hl3 = QHBoxLayout()
        hl3.addWidget(QLabel("Break Block (mins):"))
        self.bk_m = QSpinBox()
        self.bk_m.setRange(1, 120)
        self.bk_m.setValue(15)
        hl3.addWidget(self.bk_m)
        lay.addLayout(hl3)
        
        btn = QPushButton("Generate Weighted Plan")
        btn.setStyleSheet("background-color: #0a84ff; padding: 10px; font-weight: bold; border-radius: 5px;")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)
        
    def get_plan(self):
        sel = [(name, sp.value()) for cb, name, sp in self.course_rows if cb.isChecked()]
        if not sel: return []
        
        tot = self.tot_m.value()
        wk = self.wk_m.value()
        bk = self.bk_m.value()
        plan = []
        
        scores = {name: 0.0 for name, _ in sel}
        weights = {name: w for name, w in sel}
        
        while tot > 0:
            for name in scores: 
                scores[name] += weights[name]
            best_c = max(scores, key=scores.get)
            scores[best_c] -= 1.0
            
            dur = min(tot, wk)
            plan.append({"course": best_c, "duration": dur, "type": "Work"})
            tot -= dur
            if tot > 0: 
                plan.append({"course": "Break", "duration": bk, "type": "Break"})
        return plan

class AppWhitelistDialog(QDialog):
    def __init__(self, apps, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Whitelist Work Apps")
        self.setMinimumWidth(350)
        self.setStyleSheet("background-color: #0f0f11; color: white;")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Select apps allowed during this session:", styleSheet="font-weight:bold;"))
        
        scr = QScrollArea()
        w = QWidget()
        vl = QVBoxLayout(w)
        self.bs = []
        
        for a in apps:
            if a.lower() in ["terminal", "python", "python3", "second brain os", "code", "vscode"]: continue
            cb = QCheckBox(a)
            cb.setStyleSheet("padding: 5px;")
            if a in ["Google Chrome", "Finder"]: 
                cb.setChecked(True)
            self.bs.append(cb)
            vl.addWidget(cb)
            
        w.setLayout(vl)
        scr.setWidget(w)
        scr.setWidgetResizable(True)
        lay.addWidget(scr)
        
        btn = QPushButton("Start Focus Session")
        btn.setStyleSheet("background-color: #0a84ff; padding: 10px; font-weight: bold; border-radius: 5px;")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)
        
    def get_allowed(self): 
        return [cb.text() for cb in self.bs if cb.isChecked()] + ["python", "python3", "Second Brain OS", "Terminal", "loginwindow", "WindowManager", "ControlCenter", "NotificationCenter", "Siri", "Spotlight", "Code", "Visual Studio Code"]

class TimelapseDialog(QDialog):
    def __init__(self, path, mins, dists, b_data):
        super().__init__()
        self.setWindowTitle("Session Debrief")
        self.setFixedSize(800, 600)
        self.setStyleSheet("background-color: #0f0f11; color: white;")
        
        lay = QVBoxLayout(self)
        self.lbl = QLabel()
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl)
        
        lay.addWidget(MiniTimeline(b_data))
        
        h = QHBoxLayout()
        h.addWidget(QLabel(f"<b>Session Stats:</b> {mins} Mins Studied | {dists} Distractions", styleSheet="font-size: 18px; color: #40c463;"))
        
        btn = QPushButton("Close")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.close)
        
        h.addStretch()
        h.addWidget(btn)
        lay.addLayout(h)
        
        self.cap = cv2.VideoCapture(path)
        self.tmr = QTimer()
        self.tmr.timeout.connect(self.nf)
        self.tmr.start(33)
        
    def nf(self):
        ret, frm = self.cap.read()
        if ret: 
            rgb = cv2.cvtColor(frm, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            self.lbl.setPixmap(QPixmap.fromImage(QImage(rgb.data, w, h, ch*w, QImage.Format.Format_RGB888)).scaled(760, 480, Qt.AspectRatioMode.KeepAspectRatio))
        else: 
            self.tmr.stop()
            
    def closeEvent(self, e): 
        self.tmr.stop()
        if self.cap:
            self.cap.release()
        super().closeEvent(e)

class QuickAddDialog(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 100)
        
        f = QFrame(self)
        f.setObjectName("GlassPanel")
        f.setFixedSize(500, 100)
        l = QHBoxLayout(f)
        self.i = QLineEdit()
        self.i.returnPressed.connect(self.s)
        l.addWidget(self.i)
        QVBoxLayout(self).addWidget(f)
        
    def s(self):
        if self.i.text().strip(): 
            db.c.execute("INSERT INTO todos (task, is_done, quadrant) VALUES (?, 0, 'Urgent & Important')", (self.i.text().strip(),))
            db.conn.commit()
            bus.db_updated.emit()
            self.i.clear()
            self.hide()


# =====================================================================
# [VIRTUAL MODULE] ui/overlay.py
# The floating desktop HUD displaying session progress.
# =====================================================================
class OverlayWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(200, 200)
        self.sp = 0
        self.dp = 0
        self.txt = "00:00"
        self.sm = 0
        self.pm = 1
        self.ring_color = QColor("#0a84ff")
        self.bg_override = None
        bus.timer_tick.connect(self.upd_tk)
        bus.progress_update.connect(self.upd_pr)
        bus.active_color_changed.connect(self.set_color)
        bus.attention_alert.connect(self.set_dist)
        sc = QApplication.primaryScreen().geometry()
        self.move(sc.width() // 2 - 100, 20)
        self.oldPos = None

    def set_color(self, c): 
        self.ring_color = c
        self.update()
        
    def set_dist(self, m):
        if m == "App": self.bg_override = QColor(255, 140, 0, 220)
        elif m == "Camera": self.bg_override = QColor(255, 50, 50, 220)
        elif m == "CameraError": self.bg_override = QColor(128, 0, 128, 220)
        else: self.bg_override = None
        self.update()

    def upd_tk(self, t, s, pc): 
        self.sp = pc / 100.0
        self.txt = t
        self.update()
        
    def upd_pr(self, st, pl): 
        self.sm = st
        self.pm = max(pl, 1)
        self.dp = min(st / self.pm, 1.0)
        self.update()
        
    def mousePressEvent(self, e): 
        if e.button() == Qt.MouseButton.LeftButton: 
            self.oldPos = e.globalPosition().toPoint()
            
    def mouseMoveEvent(self, e): 
        if self.oldPos is not None: 
            d = e.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + d.x(), self.y() + d.y())
            self.oldPos = e.globalPosition().toPoint()
            
    def mouseReleaseEvent(self, e): 
        self.oldPos = None
    
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(100, 100)
        draw_horological_face(p, 90, config.cfg)
        
        if self.bg_override: 
            p.setBrush(QBrush(self.bg_override))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(-90, -90, 180, 180)
        
        p.setPen(QPen(QColor(255,255,255,30), 6))
        p.drawArc(-60, -60, 120, 120, 0, 360*16)
        p.setPen(QPen(self.ring_color, 6, cap=Qt.PenCapStyle.RoundCap))
        p.drawArc(-60, -60, 120, 120, 90*16, int(-self.sp * 360 * 16))
        
        p.setPen(QPen(QColor(255,255,255,30), 4))
        p.drawArc(-45, -45, 90, 90, 0, 360*16)
        p.setPen(QPen(QColor("#40c463"), 4, cap=Qt.PenCapStyle.RoundCap))
        p.drawArc(-45, -45, 90, 90, 90*16, int(-self.dp * 360 * 16))
        
        p.setPen(QColor("white"))
        p.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        p.drawText(QRect(-90, 20, 180, 40), Qt.AlignmentFlag.AlignCenter, self.txt)
        
        t = QTime.currentTime()
        h_style = config.get("clock_hands", "Classic")
        comp = config.get("clock_comp", "None")
        
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("white")))
        
        p.save()
        p.rotate(30.0 * (t.hour() + t.minute()/60.0))
        draw_horological_hands(p, h_style, 45, 3, True)
        p.restore()
        
        p.save()
        p.rotate(6.0 * (t.minute() + t.second()/60.0))
        draw_horological_hands(p, h_style, 65, 2, False)
        p.restore()
        
        sec_col = self.ring_color
        if comp == "Small Seconds":
            p.save()
            p.translate(0, 40)
            p.rotate(6.0 * t.second())
            p.setBrush(QBrush(sec_col))
            draw_horological_hands(p, "Baton", 15, 1, False)
            p.restore()
        else:
            p.setBrush(QBrush(sec_col))
            p.setPen(QPen(sec_col, 2))
            p.save()
            p.rotate(6.0 * t.second())
            if h_style in ["Serpentine", "Arrow", "Sword"]: 
                draw_horological_hands(p, h_style, 75, 1, False)
            else: 
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRect(-1, 0, 2, -75)
            p.restore()
            
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(-3, -3, 6, 6)


# =====================================================================
# [VIRTUAL MODULE] ui/tabs/dashboard.py
# Main dashboard containing global statistics.
# =====================================================================
class DashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.dl_lbl = QLabel("")
        self.dl_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #ff9f0a; background-color: rgba(0,0,0,100); padding: 10px; border-radius: 8px;")
        self.dl_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.dl_lbl)
        
        tg = QGridLayout()
        
        self.gp = QFrame()
        self.gp.setObjectName("GlassPanel")
        self.gp.setFixedSize(350, 320)
        pl = QVBoxLayout(self.gp)
        pl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.cs = QStackedWidget()
        self.ac = AnalogClock()
        self.dc = QLabel("00:00:00")
        self.dc.setObjectName("RealDigitalClock")
        self.dc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cs.addWidget(self.ac)
        self.cs.addWidget(self.dc)
        
        self.ring = CircularProgress()
        self.plbl = QLabel("Session: Inactive")
        self.plbl.setStyleSheet("color:#0a84ff; font-weight:bold;")
        self.plbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        hz = QHBoxLayout()
        hz.addWidget(self.ring)
        hz.addWidget(self.cs)
        pl.addLayout(hz)
        pl.addWidget(self.plbl)
        
        self.dgw = DashboardGoalsWidget()
        
        self.cp = QFrame()
        self.cp.setObjectName("GlassPanel")
        self.cp.setFixedSize(450, 320)
        cl = QVBoxLayout(self.cp)
        cl.addWidget(QLabel("Deep Work Calendar"))
        self.cal = FocusCalendar()
        cl.addWidget(self.cal)
        
        self.hp = QFrame()
        self.hp.setObjectName("GlassPanel")
        self.hp.setFixedSize(600, 250)
        hl = QVBoxLayout(self.hp)
        hl.addWidget(QLabel("Deep Work Intensity"))
        self.hm = ActivityHeatmap()
        hl.addWidget(self.hm)
        
        tg.addWidget(self.gp, 0, 0)
        tg.addWidget(self.dgw, 0, 1)
        tg.addWidget(self.cp, 0, 2)
        tg.addWidget(self.hp, 1, 0, 1, 3, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.ql = QLabel("Fetching...")
        self.ql.setObjectName("QuoteText")
        self.ql.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lay.addStretch()
        lay.addLayout(tg)
        lay.addStretch()
        lay.addWidget(self.ql)
        lay.addSpacing(30)
        
        self.tmr = QTimer(self)
        self.tmr.timeout.connect(self.upd_clk)
        self.tmr.start(1000)
        
        bus.timer_tick.connect(self.upd_p)
        bus.settings_changed.connect(self.app_c)
        self.app_c()
        
    def app_c(self):
        s = config.get("clock_style")
        if "Digital" in s: 
            self.cs.setCurrentIndex(1)
            self.dc.setStyleSheet(f"font-size: 54px; font-weight:bold; color: {'#39ff14' if 'LED' in s else '#ff9f0a'};")
        else: 
            self.cs.setCurrentIndex(0)
            
    def upd_clk(self): 
        now = datetime.now()
        self.dc.setText(now.strftime("%H:%M:%S"))
        self.ac.update()
        
        try:
            dl_date = datetime.strptime(config.get("deadline_date"), "%Y-%m-%d %H:%M")
            rem = dl_date - now
            if rem.total_seconds() > 0:
                days = rem.days
                hours, rem_sec = divmod(rem.seconds, 3600)
                mins, secs = divmod(rem_sec, 60)
                self.dl_lbl.setText(f"⏳ {config.get('deadline_name')}: {days}d {hours}h {mins}m {secs}s")
            else:
                self.dl_lbl.setText(f"🚀 {config.get('deadline_name')} Deadline Reached!")
        except:
            self.dl_lbl.setText("⏳ Set a valid deadline in Settings.")
        
    def upd_p(self, t, s, pc): 
        self.plbl.setText("Inactive" if s == "Stopped" else f"[{s}] {t}")
        self.plbl.setStyleSheet("color: #ff453a; font-weight: bold;" if "Attention" in s or "Paused" in s else "color: #0a84ff; font-weight: bold;")
        
    def set_quote(self, txt): 
        self.ql.setText(txt)


# =====================================================================
# [VIRTUAL MODULE] ui/tabs/metrics.py
# Deep analytics, distraction tracking, and momentum visualization.
# =====================================================================
class MetricsWidget(QWidget):
    def __init__(self): 
        super().__init__()
        lay = QVBoxLayout(self)
        self.map = MomentumMap()
        lay.addWidget(self.map)


# =====================================================================
# [VIRTUAL MODULE] ui/tabs/course_progress.py
# Target setting and cumulative study completion percentages.
# =====================================================================
class CourseProgressWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        hl = QHBoxLayout()
        hl.addWidget(QLabel("Course Goals & Progress", objectName="AppTitle"))
        self.apply_btn = QPushButton("Apply Goals")
        self.apply_btn.setStyleSheet("background-color: #0a84ff; font-weight: bold; padding: 8px 16px; border-radius: 8px; color: white;")
        self.apply_btn.clicked.connect(self.save_all)
        hl.addStretch()
        hl.addWidget(self.apply_btn)
        self.lay.addLayout(hl)
        
        self.sa = QScrollArea()
        self.sa.setWidgetResizable(True)
        self.sa.setStyleSheet("background: transparent; border: none;")
        self.cw = QWidget()
        self.vl = QVBoxLayout(self.cw)
        self.sa.setWidget(self.cw)
        self.lay.addWidget(self.sa)
        
        self.spinboxes = {}
        self.upd()
        bus.db_updated.connect(self.upd)
        bus.course_added.connect(self.upd)

    def upd(self):
        for i in reversed(range(self.vl.count())):
            w = self.vl.itemAt(i).widget()
            if w:
                w.deleteLater()
            else:
                item = self.vl.itemAt(i)
                if item.layout():
                    for j in reversed(range(item.layout().count())):
                        ww = item.layout().itemAt(j).widget()
                        if ww:
                            ww.deleteLater()
        
        self.spinboxes.clear()
        db.c.execute("SELECT name FROM courses")
        courses = [r[0] for r in db.c.fetchall()]
        
        db.c.execute("SELECT course, target_hours FROM course_targets")
        targets = {r[0]: r[1] for r in db.c.fetchall()}
        
        db.c.execute("SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY course")
        studied = {r[0]: (r[1] or 0)/60.0 for r in db.c.fetchall()}
        
        for c in courses:
            f = QFrame()
            f.setObjectName("Panel")
            l = QVBoxLayout(f)
            
            t_hrs = targets.get(c, 0.0)
            s_hrs = studied.get(c, 0.0)
            
            hl = QHBoxLayout()
            hl.addWidget(QLabel(f"<b>{c}</b>", styleSheet="font-size: 18px;"))
            hl.addStretch()
            
            tgt_sp = QDoubleSpinBox()
            tgt_sp.setRange(0, 10000)
            tgt_sp.setValue(t_hrs)
            tgt_sp.setSuffix(" hrs target")
            
            self.spinboxes[c] = tgt_sp
            
            hl.addWidget(tgt_sp)
            l.addLayout(hl)
            
            rem = max(0, t_hrs - s_hrs)
            pb = QProgressBar()
            pb.setMaximum(100)
            pct = min(int((s_hrs / t_hrs) * 100), 100) if t_hrs > 0 else 0
            pb.setValue(pct)
            pb.setFormat(f"{s_hrs:.1f} / {t_hrs:.1f} hrs ({pct}%) | Rem: {rem:.1f} hrs")
            pb.setStyleSheet(f"QProgressBar {{ background-color: rgba(255,255,255,10); border-radius: 8px; text-align: center; color: white; font-weight: bold; border: 1px solid rgba(255,255,255,20); }} QProgressBar::chunk {{ background-color: {get_color(c).name()}; border-radius: 8px; }}")
            
            l.addWidget(pb)
            self.vl.addWidget(f)
            
        self.vl.addStretch()

    def save_all(self):
        for c, sp in self.spinboxes.items():
            db.c.execute("INSERT OR REPLACE INTO course_targets (course, target_hours) VALUES (?, ?)", (c, sp.value()))
        db.conn.commit()
        
        self.apply_btn.setText("Saved!")
        self.apply_btn.setStyleSheet("background-color: #30a14e; font-weight: bold; padding: 8px 16px; border-radius: 8px; color: white;")
        QTimer.singleShot(1500, self.reset_btn)
        self.upd()

    def reset_btn(self):
        self.apply_btn.setText("Apply Goals")
        self.apply_btn.setStyleSheet("background-color: #0a84ff; font-weight: bold; padding: 8px 16px; border-radius: 8px; color: white;")


# =====================================================================
# [VIRTUAL MODULE] ui/tabs/day_summary.py
# Immediate playback of today's timelapses.
# =====================================================================
class DaySummaryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.sa = QScrollArea()
        self.sa.setWidgetResizable(True)
        self.sa.setStyleSheet("background: transparent; border: none;")
        self.cw = QWidget()
        self.vl = QVBoxLayout(self.cw)
        self.sa.setWidget(self.cw)
        self.lay.addWidget(self.sa)
        
        self.upd()
        bus.db_updated.connect(self.upd)
        
    def upd(self):
        for i in reversed(range(self.vl.count())):
            w = self.vl.itemAt(i).widget()
            if w:
                w.deleteLater()
            
        db.c.execute("SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp) = date('now')")
        tdy_sec = db.c.fetchone()[0] or 0
        db.c.execute("SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp) = date('now', '-1 day')")
        ydy_sec = db.c.fetchone()[0] or 0
        
        f1 = QFrame()
        f1.setObjectName("Panel")
        l1 = QVBoxLayout(f1)
        l1.addWidget(QLabel(f"<h2>Time Studied Today: {tdy_sec/60.0:.1f} minutes</h2>"))
        comp = f"+{((tdy_sec-ydy_sec)/60.0):.1f}m compared to yesterday" if tdy_sec >= ydy_sec else f"{((tdy_sec-ydy_sec)/60.0):.1f}m compared to yesterday"
        l1.addWidget(QLabel(f"<span style='color: #40c463;'>{comp}</span>"))
        self.vl.addWidget(f1)
        
        db.c.execute("SELECT sum(distractions) FROM pomodoro_sessions WHERE date(timestamp) = date('now')")
        tdy_dist = db.c.fetchone()[0] or 0
        f2 = QFrame()
        f2.setObjectName("Panel")
        l2 = QVBoxLayout(f2)
        l2.addWidget(QLabel(f"<h3>Total Distractions Recorded Today: {tdy_dist}</h3>"))
        self.vl.addWidget(f2)
        
        f3 = QFrame()
        f3.setObjectName("Panel")
        l3 = QVBoxLayout(f3)
        l3.addWidget(QLabel("<h3>Today's Session Timelapses:</h3>"))
        db.c.execute("SELECT course, duration, distractions, timelapse_path FROM pomodoro_sessions WHERE date(timestamp) = date('now') AND timelapse_path != ''")
        sessions = db.c.fetchall()
        if not sessions:
            l3.addWidget(QLabel("No videos cataloged for today yet."))
        for crs, dur, d_cnt, path in sessions:
            if os.path.exists(path):
                btn = QPushButton(f"Play {crs} Block ({dur}m) - {d_cnt} Distracts")
                btn.clicked.connect(lambda _, p=path, d=dur, dc=d_cnt, c=crs: TimelapseDialog(p, d, dc, {"course":c,"duration":d}).exec())
                l3.addWidget(btn)
        self.vl.addWidget(f3)
        self.vl.addStretch()


# =====================================================================
# [VIRTUAL MODULE] ui/tabs/quiz.py
# Interactive JSON-powered quiz engine.
# =====================================================================
class QuizEngineWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        sp = QSplitter(Qt.Orientation.Horizontal)
        
        lf = QFrame()
        lf.setObjectName("Panel")
        ll = QVBoxLayout(lf)
        ll.addWidget(QLabel("Saved Quizzes"))
        self.ql = QListWidget()
        self.ql.itemDoubleClicked.connect(self.lsq)
        ll.addWidget(self.ql)
        
        bl = QPushButton("Import JSON")
        bl.clicked.connect(self.iq)
        br = QPushButton("Review Starred")
        br.clicked.connect(self.rs)
        ll.addWidget(bl)
        ll.addWidget(br)
        sp.addWidget(lf)
        
        rf = QFrame()
        rf.setObjectName("Panel")
        rl = QVBoxLayout(rf)
        tb = QHBoxLayout()
        self.cc = QComboBox()
        self.lc()
        bus.course_added.connect(self.lc)
        
        sb = QPushButton("⭐ Star")
        sb.clicked.connect(self.sp)
        tb.addWidget(self.cc)
        tb.addWidget(sb)
        tb.addStretch()
        
        self.qd = QTextEdit()
        self.qd.setReadOnly(True)
        self.qd.setText("Select quiz.")
        
        self.oc = QFrame()
        self.ol = QVBoxLayout(self.oc)
        self.bg = QButtonGroup(self)
        
        ft = QHBoxLayout()
        self.pl = QLabel("")
        self.skb = QPushButton("Skip")
        self.skb.clicked.connect(self.skq)
        self.nb = QPushButton("Next")
        self.nb.clicked.connect(self.nq)
        self.skb.setEnabled(False)
        self.nb.setEnabled(False)
        
        ft.addWidget(self.pl)
        ft.addStretch()
        ft.addWidget(self.skb)
        ft.addWidget(self.nb)
        
        rl.addLayout(tb)
        rl.addWidget(self.qd)
        rl.addWidget(self.oc)
        rl.addStretch()
        rl.addLayout(ft)
        
        sp.addWidget(rf)
        lay.addWidget(sp)
        
        self.dat = []
        self.org = []
        self.wrg = []
        self.skp = []
        self.idx = 0
        self.sc = 0
        self.rql()
        
    def lc(self): 
        self.cc.clear()
        self.cc.addItem("Course...")
        db.c.execute("SELECT name FROM courses")
        for r in db.c.fetchall():
            self.cc.addItem(r[0])
            
    def rql(self): 
        self.ql.clear()
        db.c.execute("SELECT id, title FROM saved_quizzes")
        for i, t in db.c.fetchall():
            it = QListWidgetItem(t)
            it.setData(Qt.ItemDataRole.UserRole, i)
            self.ql.addItem(it)
            
    def iq(self):
        f, _ = QFileDialog.getOpenFileName(self, "Open JSON", "", "JSON Files (*.json)")
        if f: 
            db.c.execute("INSERT INTO saved_quizzes (title, course, filepath) VALUES (?,?,?)", (os.path.basename(f), self.cc.currentText(), f))
            db.conn.commit()
            self.rql()
            
    def lsq(self, item):
        db.c.execute("SELECT filepath FROM saved_quizzes WHERE id=?", (item.data(Qt.ItemDataRole.UserRole),))
        p = db.c.fetchone()[0]
        try: 
            self.org = json.load(open(p, 'r', encoding='utf-8'))
            self.sq_i(self.org)
        except: 
            pass
            
    def rs(self):
        c = self.cc.currentText()
        if c != "Course...":
            db.c.execute("SELECT data_json FROM starred_questions WHERE course=?", (c,))
            rows = db.c.fetchall()
            if rows: 
                sq = [json.loads(r[0]) for r in rows]
                self.org = sq
                self.sq_i(sq)
                
    def sq_i(self, d): 
        self.dat = d
        self.idx = 0
        self.sc = 0
        self.wrg = []
        self.skp = []
        self.nb.setEnabled(True)
        self.skb.setEnabled(True)
        self.shq()
        
    def shq(self):
        for i in reversed(range(self.ol.count())):
            w = self.ol.itemAt(i).widget()
            self.bg.removeButton(w)
            if w:
                w.deleteLater()
            
        q = self.dat[self.idx]
        self.pl.setText(f"Q {self.idx+1}/{len(self.dat)}")
        self.qd.clear()
        c = self.qd.textCursor()
        
        for i, p in enumerate(q.get("q", "").split('$')):
            if i%2==1: 
                self.qd.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl(f"l_{i}"), render_latex(p, config.get("font_size")))
                c.insertImage(f"l_{i}")
            else: 
                c.insertText(p)
                
        for i, o in enumerate(q.get("options", [])): 
            rb = QRadioButton(o)
            self.bg.addButton(rb, i)
            self.ol.addWidget(rb)
            
    def nq(self):
        b = self.bg.checkedButton()
        if not b: return 
        if b.text() == self.dat[self.idx].get("answer"): 
            self.sc += 1
        else: 
            self.wrg.append(self.dat[self.idx])
        self.adv()
        
    def skq(self): 
        self.skp.append(self.dat[self.idx])
        self.adv()
        
    def adv(self): 
        self.idx += 1
        if self.idx < len(self.dat): 
            self.shq()
        else: 
            self.fin()
            
    def fin(self):
        for i in reversed(range(self.ol.count())):
            w = self.ol.itemAt(i).widget()
            if w:
                w.deleteLater()
            
        self.qd.setText(f"Done!\nScore: {self.sc}/{len(self.dat)}\nMissed: {len(self.wrg)}\nSkipped: {len(self.skp)}")
        self.pl.setText("Ended")
        self.nb.setEnabled(False)
        self.skb.setEnabled(False)
        db.c.execute("INSERT INTO exams (course, score, total, date) VALUES (?,?,?,?)", (self.cc.currentText(), self.sc, len(self.dat), datetime.now().isoformat()))
        db.conn.commit()
        
        b1 = QPushButton("Redo All")
        b1.clicked.connect(lambda: self.sq_i(self.org))
        self.ol.addWidget(b1)
        if self.wrg or self.skp: 
            b2 = QPushButton("Redo Wrong/Skipped")
            b2.clicked.connect(lambda: self.sq_i(self.wrg + self.skp))
            self.ol.addWidget(b2)
            
    def sp(self):
        if self.dat and self.idx < len(self.dat): 
            db.c.execute("INSERT INTO starred_questions (course, question, data_json) VALUES (?,?,?)", (self.cc.currentText(), self.dat[self.idx].get("q"), json.dumps(self.dat[self.idx])))
            db.conn.commit()


# =====================================================================
# [VIRTUAL MODULE] ui/tabs/flashcards.py
# Simple Q&A memorization mechanism.
# =====================================================================
class FlashcardWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        
        af = QFrame()
        af.setObjectName("Panel")
        al = QHBoxLayout(af)
        self.fi = QLineEdit()
        self.fi.setPlaceholderText("Front...")
        self.bi = QLineEdit()
        self.bi.setPlaceholderText("Back...")
        
        self.cc = QComboBox()
        bus.course_added.connect(self.lc)
        self.lc()
        
        ab = QPushButton("Add")
        ab.clicked.connect(self.ac)
        
        al.addWidget(self.cc)
        al.addWidget(self.fi)
        al.addWidget(self.bi)
        al.addWidget(ab)
        
        self.cf = QFrame()
        self.cf.setObjectName("GlassPanel")
        self.cf.setFixedSize(600, 300)
        cl = QVBoxLayout(self.cf)
        self.ft = QLabel("Next...")
        self.ft.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.ft)
        
        self.fa = QPropertyAnimation(self.cf, b"maximumWidth")
        self.fa.setDuration(150)
        self.fa.finished.connect(self.mf)
        
        self.cd = None
        self.sf = True
        
        ct = QHBoxLayout()
        fb = QPushButton("Flip")
        fb.clicked.connect(self.fl)
        nb = QPushButton("Next")
        nb.clicked.connect(self.ln)
        
        ct.addStretch()
        ct.addWidget(fb)
        ct.addWidget(nb)
        ct.addStretch()
        
        lay.addWidget(af)
        lay.addStretch()
        lay.addWidget(self.cf, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addLayout(ct)
        lay.addStretch()
        
    def lc(self): 
        self.cc.clear()
        self.cc.addItem("General")
        db.c.execute("SELECT name FROM courses")
        for r in db.c.fetchall():
            self.cc.addItem(r[0])
            
    def ac(self):
        if self.fi.text() and self.bi.text():
            try: 
                db.c.execute("INSERT INTO flashcards (course, front, back) VALUES (?, ?, ?)", (self.cc.currentText(), self.fi.text().strip(), self.bi.text().strip()))
            except sqlite3.OperationalError: 
                db.c.execute("INSERT INTO flashcards (front, back) VALUES (?, ?)", (self.fi.text().strip(), self.bi.text().strip()))
            db.conn.commit()
            self.fi.clear()
            self.bi.clear()
            bus.db_updated.emit()
            
    def fl(self):
        if not self.cd: return
        self.fa.setStartValue(600)
        self.fa.setEndValue(0)
        self.fa.start()
        
    def mf(self):
        self.sf = not self.sf
        self.ft.setText(self.cd["front"] if self.sf else self.cd["back"])
        self.fa.disconnect()
        self.fa.finished.connect(lambda: None)
        self.fa.setStartValue(0)
        self.fa.setEndValue(600)
        self.fa.start()
        self.fa.finished.connect(self.ra)
        
    def ra(self): 
        self.fa.disconnect()
        self.fa.finished.connect(self.mf)
        
    def ln(self):
        db.c.execute("SELECT front, back FROM flashcards ORDER BY RANDOM() LIMIT 1")
        r = db.c.fetchone()
        if r: 
            self.cd = {"front": r[0], "back": r[1]}
            self.sf = True
            self.ft.setText(self.cd["front"])
        else: 
            self.ft.setText("Empty.")


# =====================================================================
# [VIRTUAL MODULE] ui/tabs/notes.py
# Markdown-enabled rich text scratchpad.
# =====================================================================
class MarkdownEditorWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        sp = QSplitter(Qt.Orientation.Horizontal)
        
        self.ed = QTextEdit()
        self.ed.setObjectName("Panel")
        self.ed.textChanged.connect(self.up)
        
        self.pr = QTextEdit()
        self.pr.setObjectName("Panel")
        self.pr.setReadOnly(True)
        
        sp.addWidget(self.ed)
        sp.addWidget(self.pr)
        
        tb = QHBoxLayout()
        self.ti = QLineEdit()
        sb = QPushButton("Save")
        sb.clicked.connect(self.sn)
        
        tb.addWidget(self.ti)
        tb.addWidget(sb)
        
        lay.addLayout(tb)
        lay.addWidget(sp)
        
    def up(self): 
        self.pr.setHtml(f"<div style='color: white; font-family: {config.get('font_family')};'>{markdown.markdown(self.ed.toPlainText(), extensions=['fenced_code', 'tables'])}</div>")
        
    def sn(self):
        if self.ti.text() and self.ed.toPlainText(): 
            db.c.execute("INSERT INTO notes (title, content, timestamp) VALUES (?, ?, ?)", (self.ti.text(), self.ed.toPlainText(), datetime.now().isoformat()))
            db.conn.commit()


# =====================================================================
# [VIRTUAL MODULE] ui/tabs/settings.py
# Global application configuration manager interface.
# =====================================================================
class SettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Settings", objectName="AppTitle"))
        
        scr = QScrollArea()
        scr.setWidgetResizable(True)
        scr.setStyleSheet("border: none; background: transparent;")
        cw = QWidget()
        ul = QGridLayout(cw)
        
        r = 0
        ul.addWidget(QLabel("Clock Theme:"), r, 0)
        self.cc = QComboBox()
        self.cc.addItems(["Analog Classic", "Analog Minimal", "Analog Neon", "Digital LED", "Digital Retro"])
        self.cc.setCurrentText(config.get("clock_style", "Analog Classic"))
        ul.addWidget(self.cc, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Case Shape:"), r, 0)
        self.c_case = QComboBox()
        self.c_case.addItems(["Round", "Square", "Cushion", "Tonneau"])
        self.c_case.setCurrentText(config.get("clock_case", "Round"))
        ul.addWidget(self.c_case, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Bezel:"), r, 0)
        self.c_bezel = QComboBox()
        self.c_bezel.addItems(["Plain", "Fluted", "Diver", "GMT", "Coin-Edge"])
        self.c_bezel.setCurrentText(config.get("clock_bezel", "Plain"))
        ul.addWidget(self.c_bezel, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Indices:"), r, 0)
        self.c_ind = QComboBox()
        self.c_ind.addItems(["None", "Arabic", "Roman", "Baton", "Dot", "California"])
        self.c_ind.setCurrentText(config.get("clock_indices", "Baton"))
        ul.addWidget(self.c_ind, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Ticks:"), r, 0)
        self.c_ticks = QComboBox()
        self.c_ticks.addItems(["Standard", "Clean", "Railroad", "Crosshair"])
        self.c_ticks.setCurrentText(config.get("clock_ticks", "Standard"))
        ul.addWidget(self.c_ticks, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Hands:"), r, 0)
        self.ch = QComboBox()
        self.ch.addItems(["Classic", "Spade", "Breguet", "Dauphine", "Alpha", "Pencil", "Serpentine", "Mercedes", "Sword", "Arrow", "Baton"])
        self.ch.setCurrentText(config.get("clock_hands", "Classic"))
        ul.addWidget(self.ch, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Complication:"), r, 0)
        self.c_comp = QComboBox()
        self.c_comp.addItems(["None", "Date Window", "Small Seconds"])
        self.c_comp.setCurrentText(config.get("clock_comp", "None"))
        ul.addWidget(self.c_comp, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Clock Numbers:"), r, 0)
        self.cn = QComboBox()
        self.cn.addItems(["None", "Arabic (1, 2, 3)", "Roman (I, II, III)"])
        self.cn.setCurrentText(config.get("clock_numbers", "None"))
        ul.addWidget(self.cn, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Font Family:"), r, 0)
        self.fc = QComboBox()
        self.fc.addItems(["Helvetica Neue", "Georgia", "Arial"])
        self.fc.setCurrentText(config.get("font_family", "Helvetica Neue"))
        ul.addWidget(self.fc, r, 1)
        r+=1

        ul.addWidget(QLabel("Custom Font (.ttf/.otf):"), r, 0)
        self.cf_lbl = QLabel(os.path.basename(config.get("custom_font_path", "")) or "None")
        self.cf_lbl.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        ul.addWidget(self.cf_lbl, r, 1)
        cf_btn = QPushButton("Select Custom Font")
        cf_btn.clicked.connect(self.select_font)
        r+=1
        ul.addWidget(cf_btn, r, 0, 1, 2)
        r+=1
        
        ul.addWidget(QLabel("Size:"), r, 0)
        self.ss = QSpinBox()
        self.ss.setRange(10,36)
        self.ss.setValue(int(config.get("font_size", 16)))
        ul.addWidget(self.ss, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Deadline Name:"), r, 0)
        self.dl_name = QLineEdit()
        self.dl_name.setText(config.get("deadline_name", "Goal"))
        ul.addWidget(self.dl_name, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Deadline Date/Time:"), r, 0)
        self.dl_date = QDateTimeEdit()
        self.dl_date.setDisplayFormat("yyyy-MM-dd HH:mm")
        try:
            self.dl_date.setDateTime(QDateTime.fromString(config.get("deadline_date", (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")), "yyyy-MM-dd HH:mm"))
        except: 
            pass
        ul.addWidget(self.dl_date, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Force Close Apps After (min):"), r, 0)
        self.fc_mins = QSpinBox()
        self.fc_mins.setValue(config.get("force_close_apps_mins", 5))
        ul.addWidget(self.fc_mins, r, 1)
        r+=1
        
        system_sounds = ["Basso", "Blow", "Bottle", "Frog", "Funk", "Glass", "Hero", "Morse", "Ping", "Pop", "Purr", "Sosumi", "Submarine", "Tink"]
        ul.addWidget(QLabel("App Distraction Sound:"), r, 0)
        self.snd_app_combo = QComboBox()
        self.snd_app_combo.addItems(system_sounds)
        self.snd_app_combo.setCurrentText(config.get("sound_app_dist", "Ping"))
        ul.addWidget(self.snd_app_combo, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Camera Distraction Sound:"), r, 0)
        self.snd_cam_combo = QComboBox()
        self.snd_cam_combo.addItems(system_sounds)
        self.snd_cam_combo.setCurrentText(config.get("sound_cam_dist", "Basso"))
        ul.addWidget(self.snd_cam_combo, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Camera Error Sound:"), r, 0)
        self.snd_cam_err = QComboBox()
        self.snd_cam_err.addItems(system_sounds)
        self.snd_cam_err.setCurrentText(config.get("sound_cam_err", "Hero"))
        ul.addWidget(self.snd_cam_err, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Beep Frequency (sec):"), r, 0)
        self.beep_freq_spin = QSpinBox()
        self.beep_freq_spin.setRange(1, 60)
        self.beep_freq_spin.setValue(config.get("beep_freq", 3))
        ul.addWidget(self.beep_freq_spin, r, 1)
        r+=1
        
        ul.addWidget(QLabel("1m Distraction Loops:"), r, 0)
        self.l1m = QSpinBox()
        self.l1m.setRange(1, 100)
        self.l1m.setValue(config.get("loop_1m", 2))
        ul.addWidget(self.l1m, r, 1)
        r+=1
        
        ul.addWidget(QLabel("5m Distraction Loops:"), r, 0)
        self.l5m = QSpinBox()
        self.l5m.setRange(1, 100)
        self.l5m.setValue(config.get("loop_5m", 5))
        ul.addWidget(self.l5m, r, 1)
        r+=1
        
        ul.addWidget(QLabel("15m Distraction Loops:"), r, 0)
        self.l15m = QSpinBox()
        self.l15m.setRange(1, 100)
        self.l15m.setValue(config.get("loop_15m", 10))
        ul.addWidget(self.l15m, r, 1)
        r+=1
        
        ul.addWidget(QLabel("30m Distraction Loops:"), r, 0)
        self.l30m = QSpinBox()
        self.l30m.setRange(1, 100)
        self.l30m.setValue(config.get("loop_30m", 20))
        ul.addWidget(self.l30m, r, 1)
        r+=1
        
        ul.addWidget(QLabel("60m Distraction Loops:"), r, 0)
        self.l60m = QSpinBox()
        self.l60m.setRange(1, 100)
        self.l60m.setValue(config.get("loop_60m", 30))
        ul.addWidget(self.l60m, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Distraction Phrase:"), r, 0)
        self.speech_dist_edit = QLineEdit()
        self.speech_dist_edit.setText(config.get("speech_dist", "You have been distracted. Please return to work."))
        ul.addWidget(self.speech_dist_edit, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Completion Phrase:"), r, 0)
        self.speech_comp_edit = QLineEdit()
        self.speech_comp_edit.setText(config.get("speech_comp", "Fantastic job! Your deep work session is complete."))
        ul.addWidget(self.speech_comp_edit, r, 1)
        r+=1

        ul.addWidget(QLabel("Face Scale Factor:"), r, 0)
        self.fsf = QDoubleSpinBox()
        self.fsf.setRange(1.01, 2.0)
        self.fsf.setSingleStep(0.05)
        self.fsf.setValue(config.get("face_scale_factor", 1.2))
        ul.addWidget(self.fsf, r, 1)
        r+=1

        ul.addWidget(QLabel("Face Min Neighbors:"), r, 0)
        self.fmn = QSpinBox()
        self.fmn.setRange(1, 30)
        self.fmn.setValue(config.get("face_min_neighbors", 8))
        ul.addWidget(self.fmn, r, 1)
        r+=1

        ul.addWidget(QLabel("Face Min Size:"), r, 0)
        self.fms = QSpinBox()
        self.fms.setRange(20, 500)
        self.fms.setValue(config.get("face_min_size", 120))
        ul.addWidget(self.fms, r, 1)
        r+=1

        ul.addWidget(QLabel("Vision Sample Rate (ms):"), r, 0)
        self.vsi = QSpinBox()
        self.vsi.setRange(10, 5000)
        self.vsi.setSingleStep(10)
        self.vsi.setValue(config.get("vision_sample_interval", 30))
        ul.addWidget(self.vsi, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Distraction Delay (s):"), r, 0)
        self.dds = QSpinBox()
        self.dds.setRange(1,60)
        self.dds.setValue(int(config.get("dist_delay", 3)))
        ul.addWidget(self.dds, r, 1)
        r+=1
        
        ul.addWidget(QLabel("Vision Mode:"), r, 0)
        self.vm = QComboBox()
        self.vm.addItems(["Strict (Face & Eyes)", "Visible (Face Only)", "Presence (Motion/Whiteboard)"])
        self.vm.setCurrentText(config.get("vision_mode", "Strict (Face & Eyes)"))
        ul.addWidget(self.vm, r, 1)
        r+=1

        ul.addWidget(QLabel("Panel Opacity:"), r, 0)
        self.po = QSlider(Qt.Orientation.Horizontal)
        self.po.setRange(50, 255)
        self.po.setValue(int(config.get("panel_opacity", 180)))
        ul.addWidget(self.po, r, 1)
        r+=1

        ul.addWidget(QLabel("Background Image:"), r, 0)
        self.bg_lbl = QLabel(config.get("bg_image_path", "Default (Online/None)"))
        self.bg_lbl.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        ul.addWidget(self.bg_lbl, r, 1)
        r+=1
        
        bg_btn = QPushButton("Select Background")
        bg_btn.clicked.connect(self.select_bg)
        ul.addWidget(bg_btn, r, 0, 1, 2)
        r+=1

        ul.addWidget(QLabel("Quotes JSON:"), r, 0)
        self.qt_lbl = QLabel(config.get("quotes_path", "Default (Turing/CS)"))
        self.qt_lbl.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        ul.addWidget(self.qt_lbl, r, 1)
        r+=1
        
        qt_btn = QPushButton("Select Quotes")
        qt_btn.clicked.connect(self.select_quotes)
        ul.addWidget(qt_btn, r, 0, 1, 2)
        r+=1
        
        sb = QPushButton("Apply All Settings")
        sb.clicked.connect(self.sf)
        ul.addWidget(sb, r, 0, 1, 2)
        
        scr.setWidget(cw)
        lay.addWidget(scr)
        
        cf = QFrame()
        cf.setObjectName("Panel")
        cl = QVBoxLayout(cf)
        cl.addWidget(QLabel("Add Course"))
        self.ci = QLineEdit()
        cb = QPushButton("Save")
        cb.clicked.connect(self.ac)
        cl.addWidget(self.ci)
        cl.addWidget(cb)
        lay.addWidget(cf)

    def select_font(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Font", "", "Font Files (*.ttf *.otf)")
        if f:
            self.cf_lbl.setText(os.path.basename(f))
            config.set("custom_font_path", f)

    def select_bg(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Background Image", "", "Image Files (*.png *.jpg *.jpeg)")
        if f:
            self.bg_lbl.setText(f)
            config.set("bg_image_path", f)

    def select_quotes(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Quotes JSON", "", "JSON Files (*.json)")
        if f:
            self.qt_lbl.setText(f)
            config.set("quotes_path", f)

    def sf(self): 
        config.set("clock_style", self.cc.currentText())
        config.set("clock_case", self.c_case.currentText())
        config.set("clock_bezel", self.c_bezel.currentText())
        config.set("clock_indices", self.c_ind.currentText())
        config.set("clock_ticks", self.c_ticks.currentText())
        config.set("clock_hands", self.ch.currentText())
        config.set("clock_comp", self.c_comp.currentText())
        config.set("clock_numbers", self.cn.currentText())
        config.set("deadline_name", self.dl_name.text())
        config.set("deadline_date", self.dl_date.dateTime().toString("yyyy-MM-dd HH:mm"))
        config.set("force_close_apps_mins", self.fc_mins.value())
        config.set("sound_app_dist", self.snd_app_combo.currentText())
        config.set("sound_cam_dist", self.snd_cam_combo.currentText())
        config.set("sound_cam_err", self.snd_cam_err.currentText())
        config.set("beep_freq", self.beep_freq_spin.value())
        config.set("loop_1m", self.l1m.value())
        config.set("loop_5m", self.l5m.value())
        config.set("loop_15m", self.l15m.value())
        config.set("loop_30m", self.l30m.value())
        config.set("loop_60m", self.l60m.value())
        config.set("speech_dist", self.speech_dist_edit.text())
        config.set("speech_comp", self.speech_comp_edit.text())
        config.set("face_scale_factor", self.fsf.value())
        config.set("face_min_neighbors", self.fmn.value())
        config.set("face_min_size", self.fms.value())
        config.set("vision_sample_interval", self.vsi.value())
        config.set("dist_delay", self.dds.value())
        config.set("vision_mode", self.vm.currentText())
        config.set("panel_opacity", self.po.value())
        
        bus.settings_changed.emit()
        
    def ac(self):
        if self.ci.text().strip():
            try: 
                db.c.execute("INSERT INTO courses (name) VALUES (?)", (self.ci.text().strip(),))
                db.conn.commit()
                self.ci.clear()
                bus.course_added.emit()
            except sqlite3.IntegrityError: 
                pass


# =====================================================================
# [VIRTUAL MODULE] ui/tabs/productivity.py
# Deep Work Controller, Eisenhower Matrix, Gantt Charts.
# =====================================================================
class ProductivityWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        
        self.snd_app = QSoundEffect()
        self.snd_vis = QSoundEffect()
        self.snd_cam_err = QSoundEffect()
        
        self.sw = QSoundEffect()
        self.sw.setSource(QUrl.fromLocalFile("/System/Library/Sounds/Glass.aiff"))
        self.sw.setVolume(1.0)
        
        self.sb = QSoundEffect()
        self.sb.setSource(QUrl.fromLocalFile("/System/Library/Sounds/Tink.aiff"))
        self.sb.setVolume(1.0)
        
        self.upd_audio_files()
        
        self.tbs = QTabWidget()
        self.pt = QWidget()
        sl = QVBoxLayout(self.pt)
        
        al = QHBoxLayout()
        self.qc = QComboBox()
        self.ld_c()
        bus.course_added.connect(self.ld_c)
        
        self.qd = QSpinBox()
        self.qd.setSuffix(" m")
        self.qd.setValue(25)
        
        self.qt = QComboBox()
        self.qt.addItems(["Work", "Break"])
        self.qt.currentTextChanged.connect(self.t_chg)
        
        ba = QPushButton("+ Add")
        ba.clicked.connect(self.a_q)
        b_ap = QPushButton("Auto-Plan Day")
        b_ap.clicked.connect(self.auto_plan)
        be = QPushButton("Edit")
        be.clicked.connect(self.e_q)
        br = QPushButton("- Remove")
        br.clicked.connect(self.r_q)
        bc = QPushButton("Clear All")
        bc.clicked.connect(self.c_q)
        
        al.addWidget(self.qc)
        al.addWidget(self.qd)
        al.addWidget(self.qt)
        al.addWidget(ba)
        al.addWidget(b_ap)
        al.addWidget(be)
        al.addWidget(br)
        al.addWidget(bc)
        sl.addLayout(al)
        
        self.ql = QListWidget()
        self.ql.setStyleSheet("background: transparent; border: 1px solid rgba(255,255,255,20); border-radius: 6px;")
        self.ql.itemClicked.connect(self.pop_edit)
        sl.addWidget(self.ql)
        
        self.tl = GanttTimelineWidget()
        sl.addWidget(self.tl)
        
        pc = QHBoxLayout()
        self.lbl = QLabel("00:00")
        self.lbl.setObjectName("DigitalTimeText")
        bs = QPushButton("Start/Resume")
        bs.clicked.connect(self.sts)
        bp = QPushButton("Pause")
        bp.clicked.connect(self.pas)
        bx = QPushButton("Stop")
        bx.setObjectName("DangerButton")
        bx.clicked.connect(self.sps)
        
        pc.addWidget(self.lbl)
        pc.addStretch()
        pc.addWidget(bs)
        pc.addWidget(bp)
        pc.addWidget(bx)
        sl.addLayout(pc)
        self.tbs.addTab(self.pt, "Timeline")
        
        self.vt = QWidget()
        cl = QVBoxLayout(self.vt)
        self.cd = QLabel("Offline")
        self.cd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cd.setStyleSheet("background:#000; border:1px solid #fff; border-radius:8px;")
        self.cd.setFixedSize(640, 480)
        self.tcb = QCheckBox("Enable Vision Tracker & Timelapse")
        self.tcb.stateChanged.connect(self.tgt)
        cl.addWidget(self.cd, alignment=Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.tcb, alignment=Qt.AlignmentFlag.AlignCenter)
        self.tbs.addTab(self.vt, "Vision")
        
        self.mt = QWidget()
        ml = QVBoxLayout(self.mt)
        adl = QHBoxLayout()
        self.ti = QLineEdit()
        self.ti.setPlaceholderText("Enter task...")
        self.qcb = QComboBox()
        self.qcb.addItems(["Urgent & Important", "Not Urgent & Important", "Urgent & Not Important", "Not Urgent & Not Important"])
        bt = QPushButton("Add Task")
        bt.clicked.connect(self.add_t)
        adl.addWidget(self.ti)
        adl.addWidget(self.qcb)
        adl.addWidget(bt)
        ml.addLayout(adl)
        
        self.g = QGridLayout()
        self.qs = {}
        for t,r,c in [("Urgent & Important",0,0), ("Not Urgent & Important",0,1), ("Urgent & Not Important",1,0), ("Not Urgent & Not Important",1,1)]:
            bx_f = QFrame()
            bx_f.setStyleSheet("border: 1px solid rgba(255,255,255,20); border-radius: 8px;")
            qll = QVBoxLayout(bx_f)
            qll.addWidget(QLabel(t))
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            cw = QWidget()
            vl = QVBoxLayout(cw)
            vl.setAlignment(Qt.AlignmentFlag.AlignTop)
            sa.setWidget(cw)
            qll.addWidget(sa)
            self.qs[t] = vl
            self.g.addWidget(bx_f, r, c)
            
        ml.addLayout(self.g)
        self.tbs.addTab(self.mt, "Matrix")
        lay.addWidget(self.tbs)
        
        self.sq = []
        self.cidx = -1
        self.tt = 0
        self.tr = 0
        self.st = "Stopped"
        self.s_dist = 0
        self.ps = None
        self.cur_vid = ""
        self.alw_apps = []
        self.app_ok = True
        self.vis_ok = True
        
        self.dist_type = "Manual"
        self.al_1 = False
        self.al_5 = False
        self.al_15 = False
        self.al_30 = False
        self.al_60 = False
        self.beep_ctr = 0
        
        self.tmr = QTimer(self)
        self.tmr.timeout.connect(self.tk)
        self.f_tmr = QTimer(self)
        self.f_tmr.timeout.connect(self.chk_fcs)
        
        self.vtr = VisionTracker()
        bus.settings_changed.connect(self.vtr.upd_settings)
        bus.settings_changed.connect(self.upd_audio_files)
        self.vtr.err_msg.connect(self.err)
        self.vtr.frame_ready.connect(self.upc)
        self.vtr.att_lost.connect(self.al)
        self.vtr.att_restored.connect(self.ar)
        
        self.ovl = OverlayWidget()
        self.ld_db_q()
        self.ld_t()
        bus.db_updated.connect(self.upq)
        bus.db_updated.connect(self.ld_t)

    def upd_audio_files(self):
        self.snd_app.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_app_dist', 'Ping')}.aiff"))
        self.snd_vis.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_cam_dist', 'Basso')}.aiff"))
        self.snd_cam_err.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_cam_err', 'Hero')}.aiff"))
        self.snd_app.setVolume(1.0)
        self.snd_vis.setVolume(1.0)
        self.snd_cam_err.setVolume(1.0)

    def ld_c(self): 
        self.qc.clear()
        self.qc.addItem("General")
        db.c.execute("SELECT name FROM courses")
        for r in db.c.fetchall(): 
            self.qc.addItem(r[0])
        
    def t_chg(self, t): 
        if t == "Break":
            self.qc.setDisabled(True)
        else:
            self.qc.setDisabled(False)

    def auto_plan(self):
        dlg = AutoPlanDialog(self)
        if dlg.exec():
            for p in dlg.get_plan(): 
                self.sq.append({"course": p["course"], "duration": p["duration"], "type": p["type"], "distractions": [], "worked": 0, "start_time": None})
            self.sv_db_q()
            self.upq()
            
    def ld_db_q(self):
        db.c.execute("SELECT course, duration, type, distractions, worked, timelapse_path, start_time FROM queue ORDER BY list_order")
        self.sq = [{"course": r[0], "duration": r[1], "type": r[2], "distractions": json.loads(r[3] if r[3] else "[]"), "worked": r[4] or 0, "timelapse_path": r[5] or "", "start_time": r[6] if len(r)>6 else None} for r in db.c.fetchall()]
        self.upq()
        
    def sv_db_q(self):
        db.c.execute("DELETE FROM queue")
        for i, b in enumerate(self.sq): 
            db.c.execute("INSERT INTO queue (course, duration, type, list_order, distractions, worked, timelapse_path, start_time) VALUES (?,?,?,?,?,?,?,?)", (b['course'], b['duration'], b['type'], i, json.dumps(b.get('distractions',[])), b.get('worked', 0), b.get('timelapse_path', ''), b.get('start_time', None)))
        db.conn.commit()
        
    def a_q(self): 
        self.sq.append({"course": "Break" if self.qt.currentText()=="Break" else self.qc.currentText(), "duration": self.qd.value(), "type": self.qt.currentText(), "distractions": [], "worked": 0, "start_time": None})
        self.sv_db_q()
        self.upq()
        
    def pop_edit(self, item): 
        idx = self.ql.row(item)
        b = self.sq[idx]
        self.qc.setCurrentText("General" if b['course']=="Break" else b['course'])
        self.qd.setValue(b['duration'])
        self.qt.setCurrentText(b['type'])
        
    def e_q(self):
        r = self.ql.currentRow()
        if r >= 0: 
            self.sq[r]['course'] = "Break" if self.qt.currentText()=="Break" else self.qc.currentText()
            self.sq[r]['duration'] = self.qd.value()
            self.sq[r]['type'] = self.qt.currentText()
            self.sv_db_q()
            self.upq()
            
    def r_q(self): 
        if self.ql.currentRow() >= 0: 
            self.sq.pop(self.ql.currentRow())
            self.sv_db_q()
            self.upq()
            
    def c_q(self): 
        self.sq.clear()
        self.sv_db_q()
        self.upq()
        
    def upq(self):
        self.ql.clear()
        pl_mins = 0
        st_proj = datetime.now()
        
        for i, b in enumerate(self.sq):
            rem = max(0, b['duration'] - b.get('worked', 0))
            if i < self.cidx: 
                it = QListWidgetItem(f"[Done] [{b['type']}] {b['course']}")
                it.setForeground(QColor("gray"))
            elif i == self.cidx: 
                et = st_proj + timedelta(minutes=rem)
                ds = f" (+{sum(d[1] for d in b.get('distractions',[])):.1f}m delay)" if b.get('distractions') else ""
                it = QListWidgetItem(f"[Active] [{b['type']}] {b['course']} ({rem:.1f}m left) [Ends: {et.strftime('%H:%M')}]{ds}")
                it.setBackground(QColor(10, 132, 255, 80))
                st_proj = et
            else: 
                et = st_proj + timedelta(minutes=rem)
                it = QListWidgetItem(f"[{st_proj.strftime('%H:%M')} - {et.strftime('%H:%M')}] [{b['type']}] {b['course']}")
                st_proj = et
                
            self.ql.addItem(it)
            if b['type'] == 'Work' and i >= self.cidx: 
                pl_mins += rem
                
        self.tl.update_t(self.sq, self.cidx)
        db.c.execute("SELECT sum(duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp) = date('now')")
        tdy_studied = db.c.fetchone()[0] or 0
        bus.progress_update.emit(tdy_studied, tdy_studied + pl_mins)
        
        if 0 <= self.cidx < len(self.sq):
            bus.active_color_changed.emit(get_color(self.sq[self.cidx]['course']))
        else:
            bus.active_color_changed.emit(QColor("#0a84ff"))

    def kill_unauthorized_apps(self):
        try:
            res = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of every application process whose background only is false'], capture_output=True, text=True)
            running = [x.strip() for x in res.stdout.split(',')]
            safe_list = ["finder", "terminal", "python", "python3", "second brain os", "loginwindow", "windowmanager", "controlcenter", "notificationcenter", "siri", "spotlight", "code", "vscode"]
            for app in running:
                is_safe = False
                app_lower = app.lower()
                for s in safe_list:
                    if s in app_lower:
                        is_safe = True
                        break
                if not is_safe and app not in self.alw_apps:
                    subprocess.Popen(f"osascript -e 'tell application \"{app}\" to quit'", shell=True, stderr=subprocess.DEVNULL)
                elif "terminal" in app_lower or "python" in app_lower:
                    subprocess.Popen(f"osascript -e 'tell application \"System Events\" to set visible of process \"{app}\" to false'", shell=True, stderr=subprocess.DEVNULL)
        except: 
            pass

    def chk_fcs(self):
        if self.st in ["Paused", "Attention Lost - Paused"] and self.ps is not None:
            abs_mins = (datetime.now() - self.ps).total_seconds() / 60.0
            
            if abs_mins >= config.get("force_close_apps_mins", 5):
                p_win = self.window()
                if p_win: 
                    p_win.showNormal()
                    p_win.setWindowState(p_win.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
                    p_win.raise_()
                    p_win.activateWindow()
                self.kill_unauthorized_apps()

            self.beep_ctr += 1
            freq = max(1, config.get("beep_freq", 3))
            
            if self.beep_ctr % freq == 0:
                msg = config.get("speech_dist", "You are distracted.")
                loops = 1
                if abs_mins >= 60.0: 
                    loops = config.get("loop_60m", 30)
                    self.al_60 = True
                elif abs_mins >= 30.0: 
                    loops = config.get("loop_30m", 20)
                    self.al_30 = True
                elif abs_mins >= 15.0: 
                    loops = config.get("loop_15m", 10)
                    self.al_15 = True
                elif abs_mins >= 5.0: 
                    loops = config.get("loop_5m", 5)
                    self.al_5 = True
                elif abs_mins >= 1.0: 
                    loops = config.get("loop_1m", 2)
                    self.al_1 = True
                
                max_volume()
                if self.dist_type == "Camera": 
                    self.snd_vis.setLoopCount(loops)
                    self.snd_vis.play()
                elif self.dist_type == "CameraError": 
                    self.snd_cam_err.setLoopCount(loops)
                    self.snd_cam_err.play()
                else: 
                    self.snd_app.setLoopCount(loops)
                    self.snd_app.play()
                
                if self.beep_ctr % (freq * 4) == 0: 
                    speak_text(msg)
                    trigger_mac_notification("Distraction Alert", f"Sustained alert level active: {int(abs_mins)}m off task!")

        if self.st not in ["Focus", "Attention Lost - Paused"]: 
            return
            
        act = get_active_app()
        if act in ["", "loginwindow", "WindowManager", "ControlCenter", "NotificationCenter", "Spotlight", "Siri"]: 
            self.app_ok = True
        else: 
            self.app_ok = (not self.alw_apps) or (act in self.alw_apps)
            
        # STRICT CAMERA ENFORCEMENT
        if not self.tcb.isChecked() or not self.vtr.has_valid_feed:
            self.vis_ok = False
            if self.dist_type != "Camera":
                self.dist_type = "CameraError"
            
        all_good = self.vis_ok and self.app_ok
        
        if self.st == "Focus" and not all_good:
            self.s_dist += 1
            self.ps = datetime.now()
            self.tmr.stop()
            self.al_1 = False
            self.al_5 = False
            self.al_15 = False
            self.al_30 = False
            self.al_60 = False
            self.beep_ctr = 0
            
            if not self.vis_ok: 
                bus.attention_alert.emit(self.dist_type)
                max_volume()
                if self.dist_type == "Camera":
                    self.snd_vis.setLoopCount(2)
                    self.snd_vis.play()
                else:
                    self.snd_cam_err.setLoopCount(2)
                    self.snd_cam_err.play()
            else: 
                self.dist_type = "App"
                bus.attention_alert.emit("App")
                max_volume()
                self.snd_app.setLoopCount(2)
                self.snd_app.play()
                
            self.st = "Attention Lost - Paused"
            bus.timer_tick.emit("PAUSED", self.st, 0)
            
        elif self.st == "Attention Lost - Paused" and all_good:
            bus.attention_alert.emit("None")
            self.sts()

    def initiate_work_sequence(self):
        sdlg = SessionStartDialog(self)
        if not sdlg.exec():
            self.s_dist += 1
            self.ps = datetime.now()
            self.st = "Attention Lost - Paused"
            self.dist_type = "Manual"
            self.ovl.show()
            max_volume()
            self.snd_vis.setLoopCount(3)
            self.snd_vis.play()
            bus.timer_tick.emit("PAUSED", self.st, 0)
            bus.attention_alert.emit("CameraError")
            return
            
        try: 
            out = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of every application process whose background only is false'], capture_output=True, text=True)
            apps = [x.strip() for x in out.stdout.split(",") if x.strip()]
        except: 
            apps = []
            
        dlg = AppWhitelistDialog(apps, self)
        if dlg.exec(): 
            self.alw_apps = dlg.get_allowed()
        else: 
            self.alw_apps = []
            
        if not self.tcb.isChecked():
            self.tcb.setChecked(True)
            
        wdlg = WebcamCheckDialog(self.vtr, self)
        if not wdlg.exec():
            self.s_dist += 1
            self.ps = datetime.now()
            self.st = "Attention Lost - Paused"
            self.dist_type = "CameraError"
            self.ovl.show()
            max_volume()
            self.snd_cam_err.setLoopCount(3)
            self.snd_cam_err.play()
            bus.timer_tick.emit("PAUSED", self.st, 0)
            bus.attention_alert.emit("CameraError")
            return
            
        self.vtr.start()
        self.vtr.start_rec(self.cur_vid)
            
        self.tmr.start(1000)
        self.ovl.show()

    def sts(self):
        if not self.sq: return
        self.al_1 = False
        self.al_5 = False
        self.al_15 = False
        self.al_30 = False
        self.al_60 = False
        
        if self.st in ["Paused", "Attention Lost - Paused"]:
            if self.ps and self.cidx >= 0:
                d_secs = (datetime.now() - self.ps).total_seconds()
                # Treat under 10 seconds as a glitch, don't record it
                if d_secs >= 10: 
                    self.sq[self.cidx]['distractions'].append((self.sq[self.cidx]['worked'], d_secs/60.0, self.dist_type))
                    self.sv_db_q()
                    
            self.st = "Focus" if self.sq[self.cidx]['type'] == "Work" else "Break"
            self.dist_type = "Manual"
            bus.attention_alert.emit("None")
            self.upq()
            
            if self.st == "Focus" and self.sq[self.cidx].get('worked', 0) == 0: 
                self.initiate_work_sequence()
            else: 
                if not self.tcb.isChecked():
                    self.tcb.setChecked(True)
                if not self.vtr.has_valid_feed:
                    self.vis_ok = False
                    self.dist_type = "CameraError"
                    self.chk_fcs()
                else:
                    self.tmr.start(1000)
                    self.ovl.show()
            return
            
        if self.cidx == -1 or self.st == "Stopped":
            self.cidx = 0
            for i, b in enumerate(self.sq):
                if b.get('worked',0) < b['duration']: 
                    self.cidx = i
                    break
            self.f_tmr.start(1000)
            self.plc()

    def pas(self):
        if self.tmr.isActive(): 
            self.tmr.stop()
            self.st = "Paused"
            self.dist_type = "Manual"
            self.ps = datetime.now()
            self.al_1 = False
            self.al_5 = False
            self.al_15 = False
            self.al_30 = False
            self.al_60 = False
            self.lbl.setText(self.lbl.text() + " [PAUSED]")

    def plc(self):
        if self.cidx >= len(self.sq): 
            self.sps()
            QMessageBox.information(self, "Done", "Sequence Complete!")
            return
            
        b = self.sq[self.cidx]
        if not b.get('start_time'):
            b['start_time'] = datetime.now().isoformat()
        
        self.st = "Focus" if b['type'] == "Work" else "Break"
        self.tt = b['duration'] * 60
        self.tr = self.tt - int(b.get('worked', 0) * 60)
        self.ps = None
        self.s_dist = 0
        self.vis_ok = True
        self.app_ok = True
        self.dist_type = "Manual"
        self.upq()
        
        course_safe = b['course'].replace(' ', '_').replace('/', '')
        self.cur_vid = f"timelapses/Work_{course_safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
        b['timelapse_path'] = self.cur_vid
        
        if self.st == "Focus": 
            self.initiate_work_sequence()
        else: 
            self.tmr.start(1000)
            self.ovl.show()

    def sps(self):
        self.f_tmr.stop()
        self.tmr.stop()
        bus.attention_alert.emit("None")
        self.st = "Stopped"
        self.lbl.setText("00:00")
        bus.timer_tick.emit("00:00", self.st, 0)
        self.cidx = -1
        self.upq()
        self.vtr.stop_rec()
        self.ovl.hide()

    def tk(self):
        if self.tr > 0:
            self.tr -= 1
            m, s = divmod(self.tr, 60)
            self.lbl.setText(f"{m:02d}:{s:02d}")
            self.sq[self.cidx]['worked'] = (self.tt - self.tr) / 60.0
            bus.timer_tick.emit(f"{m:02d}:{s:02d}", self.st, 100 - int((self.tr/self.tt)*100) if self.tt > 0 else 0)
            if self.tr % 10 == 0: 
                self.sv_db_q()
        elif self.tr <= 0 and self.tt > 0 and self.sq[self.cidx].get('worked', 0) >= self.sq[self.cidx]['duration']:
            b = self.sq[self.cidx]
            if b['type'] == 'Work': 
                self.sw.play()
                speak_text(config.get("speech_comp", "Fantastic job! Your deep work session is complete."))
            else: 
                self.sb.play()
                
            self.vtr.stop_rec()
            dist_json = json.dumps(b.get('distractions', []))
            
            try: 
                db.c.execute("INSERT INTO pomodoro_sessions (course, duration, actual_duration, timestamp, type, distractions, timelapse_path, distraction_data) VALUES (?,?,?,?,?,?,?,?)", (b['course'], b['duration'], b['duration']+sum(d[1] for d in b.get('distractions',[])), datetime.now().isoformat(), b['type'], self.s_dist, self.cur_vid if b['type']=='Work' else "", dist_json))
            except: 
                db.c.execute("INSERT INTO pomodoro_sessions (course, duration, actual_duration, timestamp, type, distractions, timelapse_path) VALUES (?,?,?,?,?,?,?)", (b['course'], b['duration'], b['duration']+sum(d[1] for d in b.get('distractions',[])), datetime.now().isoformat(), b['type'], self.s_dist, self.cur_vid if b['type']=='Work' else ""))
                
            b['worked'] = b['duration']
            db.conn.commit()
            bus.db_updated.emit()
            
            if b['type'] == 'Work':
                if os.path.exists(self.cur_vid): 
                    TimelapseDialog(self.cur_vid, b['duration'], self.s_dist, b).exec()
            self.cidx += 1
            self.plc()

    def add_t(self):
        if self.ti.text().strip(): 
            db.c.execute("INSERT INTO todos (task, is_done, quadrant) VALUES (?, 0, ?)", (self.ti.text().strip(), self.qcb.currentText()))
            db.conn.commit()
            self.ti.clear()
            bus.db_updated.emit()
            
    def ld_t(self):
        for l in self.qs.values():
            for i in reversed(range(l.count())):
                w = l.itemAt(i).widget()
                if w:
                    w.deleteLater()
                    
        db.c.execute("SELECT id, task, quadrant FROM todos WHERE is_done=0")
        for tid, txt, q in db.c.fetchall():
            cb = QCheckBox(txt)
            cb.stateChanged.connect(lambda s, t=tid: self.c_t(t, s))
            if q in self.qs: 
                self.qs[q].addWidget(cb)
                
    def c_t(self, tid, s):
        if s == 2: 
            self.sw.play()
            db.c.execute("UPDATE todos SET is_done=1 WHERE id=?", (tid,))
            db.conn.commit()
            QTimer.singleShot(400, lambda: bus.db_updated.emit())
            
    def tgt(self, s):
        if s==2: 
            self.cd.setText("Initializing...")
            self.vtr.start()
        else: 
            self.vtr.stop()
            self.cd.clear()
            self.cd.setText("Offline")
            
    def err(self, m): 
        self.tcb.blockSignals(True)
        self.tcb.setChecked(False)
        self.tcb.blockSignals(False)
        self.cd.setText(m)
        self.vis_ok = False
        self.dist_type = "CameraError"
        bus.attention_alert.emit("CameraError")
        
    def upc(self, img): 
        self.cd.setPixmap(QPixmap.fromImage(img).scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio))
        
    def al(self): 
        self.vis_ok = False
        
    def ar(self): 
        self.vis_ok = True


# =====================================================================
# [VIRTUAL MODULE] main.py
# Bootstrapping and Master Window (MindPalaceOS)
# =====================================================================
class MindPalaceOS(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kourosh's Mind Palace")
        self.resize(1400, 900)
        
        self.bg_img = None
        self.is_distracted = False
        
        self.setCentralWidget(QLabel("Loading System OS Core Modules...", alignment=Qt.AlignmentFlag.AlignCenter, styleSheet="color: white; font-size: 24px;"))
        self.setStyleSheet("background-color: #0f0f11;")
        
        QTimer.singleShot(200, self.delayed_init)

    def delayed_init(self):
        try: 
            self._do_init()
        except Exception as e:
            import traceback
            msg = traceback.format_exc()
            QMessageBox.critical(self, "Init Error", f"Failed to load OS modules:\n{msg}")
            self.setCentralWidget(QTextEdit(msg))

    def _do_init(self):
        cw = QWidget(self)
        cw.setObjectName("CentralWidget")
        self.setCentralWidget(cw)
        
        ml = QHBoxLayout(cw)
        ml.setContentsMargins(0,0,0,0)
        ml.setSpacing(0)
        
        sf = QFrame()
        sf.setObjectName("Sidebar")
        sf.setFixedWidth(250)
        sl = QVBoxLayout(sf)
        sl.addWidget(QLabel("Kourosh's Mind Palace", objectName="AppTitle"))
        sl.addSpacing(30)
        
        self.csw = QStackedWidget()
        self.csw.setStyleSheet("background: transparent;")
        
        self.dsh = DashboardWidget()
        self.met = MetricsWidget()
        self.prd = ProductivityWidget()
        self.crg = CourseProgressWidget()
        self.ds_sum = DaySummaryWidget()
        self.qz = QuizEngineWidget()
        self.fl = FlashcardWidget()
        self.nt = MarkdownEditorWidget()
        self.set = SettingsWidget()
        
        for w in [self.dsh, self.met, self.prd, self.crg, self.ds_sum, self.qz, self.fl, self.nt, self.set]: 
            self.csw.addWidget(w)
            
        tabs = ["Dashboard", "Momentum Map", "Productivity Hub", "Course Goals", "Day Summary", "Quiz Engine", "Flashcards", "Notes", "Settings"]
        for i, t in enumerate(tabs):
            b = QPushButton(t)
            b.setObjectName("NavButton")
            b.clicked.connect(lambda c, idx=i: self.csw.setCurrentIndex(idx))
            sl.addWidget(b)
            
        sl.addStretch()
        ml.addWidget(sf)
        ml.addWidget(self.csw)
        
        self.qa = QuickAddDialog()
        self.qs_hk = QShortcut(QKeySequence("Cmd+Shift+Space"), self)
        self.qs_hk.activated.connect(lambda: (self.qa.show(), self.qa.activateWindow(), self.qa.i.setFocus()))
        
        self.csw.setCurrentIndex(0)
        
        bus.attention_alert.connect(self.trs)
        bus.settings_changed.connect(self.ast)
        
        self.sth()
        self.ast()

    def trs(self, mode):
        self.is_distracted = (mode != "None")
        self.update()

    def apply_downloaded_bg(self, data):
        if not config.get("bg_image_path", ""):
            self.apply_bg(data)

    def sth(self):
        self.aw = ApiWorker()
        self.aw.quote_fetched.connect(self.dsh.set_quote)
        self.aw.image_fetched.connect(self.apply_downloaded_bg)
        self.aw.start()
        
        self.update_background()

    def apply_bg(self, source):
        try:
            img = QImage()
            if isinstance(source, bytes):
                img.loadFromData(source)
            elif isinstance(source, str) and os.path.exists(source):
                img.load(source)
            else:
                self.bg_img = None
                self.update()
                return

            if not img.isNull():
                self.bg_img = img.copy()
            else:
                self.bg_img = None
        except:
            self.bg_img = None
            
        self.update()

    def update_background(self):
        bg_path = config.get("bg_image_path", "")
        if bg_path and os.path.exists(bg_path):
            self.apply_bg(bg_path)
        else:
            self.bg_img = None
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if getattr(self, 'bg_img', None) and not self.bg_img.isNull():
            target_size = self.size()
            scaled_img = self.bg_img.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            
            dx = (scaled_img.width() - target_size.width()) // 2
            dy = (scaled_img.height() - target_size.height()) // 2
            
            p.drawImage(0, 0, scaled_img, dx, dy, target_size.width(), target_size.height())
        else:
            grad = QLinearGradient(0, 0, self.width(), self.height())
            grad.setColorAt(0.0, QColor("#1a1a2e"))
            grad.setColorAt(1.0, QColor("#16213e"))
            p.fillRect(self.rect(), grad)
            
        p.fillRect(self.rect(), QColor(0, 0, 0, 150))
        
        if getattr(self, 'is_distracted', False):
            p.fillRect(self.rect(), QColor(255, 0, 0, 80))

    def ast(self):
        f = config.get("font_family", "Helvetica Neue")
        cfp = config.get("custom_font_path", "")
        
        if cfp and os.path.exists(cfp):
            fid = QFontDatabase.addApplicationFont(cfp)
            if fid != -1:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    f = fams[0]

        s = config.get("font_size", 16)
        cs = config.get("clock_style", "Analog Classic")
        opac = config.get("panel_opacity", 180)
        df = "'Courier New', monospace" if "LED" in cs else "'Menlo', monospace"
        
        self.update_background()
        
        self.setStyleSheet(f"""
            QMainWindow, #CentralWidget {{ background: transparent; }}
            QLabel, QCheckBox, QRadioButton {{ color: #f0f0f5; font-family: '{f}'; font-size: {s}px; }}
            #Sidebar {{ background-color: rgba(15,15,18,200); border-right: 1px solid rgba(255,255,255,15); }}
            #AppTitle {{ font-size: 22px; font-weight: 800; padding: 15px 10px; letter-spacing: 1px; }}
            #NavButton {{ font-size: 16px; color: #9ca3af; text-align: left; padding: 12px 20px; border: none; background: transparent; font-weight: 500; font-family: '{f}'; }}
            #NavButton:hover {{ background-color: rgba(255,255,255,20); color: #ffffff; border-radius: 8px; }}
            #GlassPanel, #Panel {{ background-color: rgba(30,30,35,{opac}); border-top: 1px solid rgba(255,255,255,45); border-left: 1px solid rgba(255,255,255,25); border-bottom: 1px solid rgba(255,255,255,10); border-right: 1px solid rgba(255,255,255,10); border-radius: 16px; }}
            #DigitalTimeText, #TimeText, #RealDigitalClock {{ font-family: {df}; }}
            #QuoteText {{ font-family: 'Georgia'; font-style: italic; color: #cccccc; }}
            QPushButton {{ background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,40), stop:1 rgba(255,255,255,10)); color: white; border-top: 1px solid rgba(255,255,255,60); border-left: 1px solid rgba(255,255,255,40); border-bottom: 1px solid rgba(255,255,255,15); border-right: 1px solid rgba(255,255,255,15); border-radius: 10px; padding: 10px 18px; font-weight: 700; font-family: '{f}'; }}
            QPushButton:hover {{ background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,60), stop:1 rgba(255,255,255,20)); border-top: 1px solid rgba(255,255,255,90); }}
            #DangerButton {{ background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,69,58,150), stop:1 rgba(255,69,58,80)); }}
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget, QCalendarWidget {{ background-color: rgba(10,10,15,160); color: #e5e7eb; border-top: 1px solid rgba(0,0,0,80); border-radius: 8px; padding: 10px; font-family: '{f}'; font-size: {s}px; }}
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MindPalaceOS()
    w.show()
    sys.exit(app.exec())