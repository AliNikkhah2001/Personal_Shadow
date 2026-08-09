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
import logging
from datetime import datetime, timedelta

# --- AUTOMATIC GLOBAL AUDIT LOGGING ---
logging.basicConfig(
    filename='mindpalace_audit.log',
    filemode='a',
    level=logging.DEBUG,
    format='%(asctime)s [%(threadName)s] %(levelname)s - %(message)s'
)

def global_audit_tracer(frame, event, arg):
    if event == 'call':
        filename = frame.f_code.co_filename
        if 'main.py' in filename or 'system_bridge.py' in filename:
            func_name = frame.f_code.co_name
            if not func_name.startswith('<') and func_name not in ['tick', 'process_frame', 'push_state']:
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

from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QTimer, Qt, QTime, QByteArray, QBuffer, QIODevice, QRectF
from PyQt6.QtGui import QImage, QPainter, QColor, QBrush, QPen, QFont, QPixmap
from PyQt6.QtWidgets import QWidget, QApplication, QFileDialog, QMainWindow, QToolBar, QScrollArea, QLabel, QInputDialog, QMessageBox, QVBoxLayout, QDialog, QHBoxLayout, QPushButton

from core_sys import config, db, get_color, GITHUB_TOKEN
from vision_tracker import VisionTracker
from sync_manager import SyncManager
from horology import draw_clock_face, draw_clock_ticks_and_indices, draw_clock_complications, draw_horological_hand
from core_logger import audit_log, logger

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

class AdvancedPDFCanvas(QLabel):
    action_completed = pyqtSignal(str, object, int)
    def __init__(self, page_num):
        super().__init__()
        self.page_num = page_num
        self.mode = "View"
        self.start_pt = None
        self.cur_pt = None
        self.setCursor(Qt.CursorShape.CrossCursor)
    def mousePressEvent(self, e):
        if self.mode != "View" and e.button() == Qt.MouseButton.LeftButton:
            self.start_pt = e.pos()
            self.cur_pt = e.pos()
    def mouseMoveEvent(self, e):
        if self.start_pt:
            self.cur_pt = e.pos()
            self.update()
    def mouseReleaseEvent(self, e):
        if self.start_pt and self.cur_pt and e.button() == Qt.MouseButton.LeftButton:
            if self.mode == "Line": self.action_completed.emit(self.mode, (self.start_pt, self.cur_pt), self.page_num)
            else:
                x0, y0 = self.start_pt.x(), self.start_pt.y()
                x1, y1 = self.cur_pt.x(), self.cur_pt.y()
                r = QRectF(float(min(x0, x1)), float(min(y0, y1)), float(abs(x1-x0)), float(abs(y1-y0)))
                if r.width() > 5 and r.height() > 5:
                    self.action_completed.emit(self.mode, r, self.page_num)
        self.start_pt = None
        self.cur_pt = None
        self.update()
    def paintEvent(self, e):
        super().paintEvent(e)
        if self.start_pt and self.cur_pt:
            p = QPainter(self)
            p.setPen(QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine))
            if self.mode == "Line": p.drawLine(self.start_pt, self.cur_pt)
            else: 
                p.setBrush(QColor(0, 150, 255, 50))
                p.drawRect(QRectF(float(self.start_pt.x()), float(self.start_pt.y()), float(self.cur_pt.x() - self.start_pt.x()), float(self.cur_pt.y() - self.start_pt.y())).normalized())

class AdvancedPDFWindow(QMainWindow):
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.doc = pymupdf.open(filepath)
        self.zoom = 2.0
        self.mode = "View"
        self.resize(1200, 900)
        self.setWindowTitle(f"Native Pro Editor - {os.path.basename(self.filepath)}")
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        
        self.canvas_container = QWidget()
        self.canvas_container.setStyleSheet("background-color: #0f0f11;")
        self.layout = QVBoxLayout(self.canvas_container)
        self.layout.setSpacing(20)
        self.layout.setContentsMargins(40, 40, 40, 40)
        
        self.pages = []
        for i in range(len(self.doc)):
            canvas = AdvancedPDFCanvas(i)
            canvas.action_completed.connect(self.handle_action)
            self.layout.addWidget(canvas)
            self.pages.append(canvas)
            
        self.scroll_area.setWidget(self.canvas_container)
        self.setCentralWidget(self.scroll_area)
        
        tb = QToolBar("Tools")
        self.addToolBar(tb)
        for act in ["View", "Highlight", "Note", "Box", "Line"]:
            a = tb.addAction(act)
            a.triggered.connect(lambda ch, m=act: self.set_mode(m))
        tb.addSeparator()
        tb.addAction("Zoom In").triggered.connect(lambda: self.set_zoom(self.zoom + 0.5))
        tb.addAction("Zoom Out").triggered.connect(lambda: self.set_zoom(self.zoom - 0.5))
        tb.addSeparator()
        tb.addAction("Screenshot").triggered.connect(self.screenshot)
        tb.addAction("Bookmark").triggered.connect(self.bookmark)
        
        self.render_all_pages()
        self.setStyleSheet("QMainWindow { background-color: #1e1e2b; } QToolBar { background-color: #282a36; color: white; border: none; padding: 5px; }")

        from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Down"), self, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() + 100))
        QShortcut(QKeySequence("Up"), self, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() - 100))
        QShortcut(QKeySequence("Right"), self, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() + 600))
        QShortcut(QKeySequence("Left"), self, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() - 600))

    def set_mode(self, m): 
        self.mode = m
        for canvas in self.pages: canvas.mode = m
        self.statusBar().showMessage(f"Mode: {m}")

    def set_zoom(self, z): 
        self.zoom = max(0.5, z)
        self.render_all_pages()

    def render_all_pages(self):
        for i, canvas in enumerate(self.pages):
            self.render_single_page(i)
            
    def render_single_page(self, page_num):
        page = self.doc[page_num]
        mat = pymupdf.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)
        fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        self.pages[page_num].setPixmap(QPixmap.fromImage(img))
        self.pages[page_num].setFixedSize(pix.width, pix.height)

    def handle_action(self, mode, geom, page_num):
        page = self.doc[page_num]
        if mode == "Line":
            p1, p2 = geom
            annot = page.add_line_annot(pymupdf.Point(p1.x()/self.zoom, p1.y()/self.zoom), pymupdf.Point(p2.x()/self.zoom, p2.y()/self.zoom))
            annot.set_colors(stroke=(1,0,0)); annot.update()
        else:
            rect = pymupdf.Rect(geom.x()/self.zoom, geom.y()/self.zoom, (geom.x()+geom.width())/self.zoom, (geom.y()+geom.height())/self.zoom)
            if mode == "Highlight":
                words = page.get_text("words")
                quads = [pymupdf.Rect(w[:4]) for w in words if pymupdf.Rect(w[:4]).intersects(rect)]
                if quads:
                    annot = page.add_highlight_annot(quads)
                    annot.set_colors(stroke=(1,1,0)); annot.update()
            elif mode == "Box":
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=(0,0,1)); annot.update()
            elif mode == "Note":
                text, ok = QInputDialog.getMultiLineText(self, "Note", "Enter note text:")
                if ok and text:
                    annot = page.add_text_annot(rect.tl, text)
                    annot.update()
        self.doc.save(self.doc.name, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        self.render_single_page(page_num)

    def screenshot(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Screenshot", "screenshot.png", "PNG (*.png)")
        if path: 
            pix = self.scroll_area.widget().grab()
            pix.save(path)

    def bookmark(self):
        db.c.execute("INSERT INTO notes (title, content, course, folder, color, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                     (f"Bookmark: {os.path.basename(self.filepath)}", f"Bookmarked {os.path.basename(self.filepath)}", "General", "Bookmarks", "#facc15", datetime.now().isoformat()))
        db.conn.commit()
        QMessageBox.information(self, "Bookmark", "Bookmark successfully added to Notes database!")

import cv2
class TimelapseDialog(QDialog):
    def __init__(self, path, mins, dists, b_data=None):
        super().__init__()
        self.setWindowTitle("Session Debrief")
        self.setFixedSize(800, 600)
        self.setStyleSheet("background-color: #0f0f11; color: white;")
        
        lay = QVBoxLayout(self)
        self.lbl = QLabel()
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl)
        
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

class SystemBridge(QObject):
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
        
        self.timer = QTimer(); self.timer.timeout.connect(self.tick)
        self.clock_timer = QTimer(); self.clock_timer.timeout.connect(self.emit_clock); self.clock_timer.start(1000)
        
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
        
        try:
            db.c.execute("ALTER TABLE pomodoro_sessions ADD COLUMN note TEXT")
            db.conn.commit()
        except Exception:
            pass
            
        try:
            db.c.executescript('''
                CREATE TABLE IF NOT EXISTS ingredients (id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT, name TEXT UNIQUE, kcal REAL, protein REAL, fat REAL, carbs REAL, image_path TEXT, is_iranian BOOLEAN DEFAULT 0);
                CREATE TABLE IF NOT EXISTS composite_foods (id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT, name TEXT UNIQUE, image_path TEXT);
                CREATE TABLE IF NOT EXISTS recipe_ingredients (id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, modified_at TEXT, composite_food_id INTEGER, ingredient_id INTEGER, amount_grams REAL);
            ''')
            db.conn.commit()
        except Exception as e:
            print("Nutrition DB Migration Error:", e)
            
        self.quiet_mode = config.get("quiet_mode", False)
        
        self.sync_manager = SyncManager()
        self.sync_manager.sync_progress.connect(lambda msg: self.sync_progress.emit(msg))
        # No config.set() here
        self.sync_manager.sync_completed.connect(lambda success, msg: config.set("git_status", "connected" if success else "error"))

        self.sync_timer = QTimer(); self.sync_timer.timeout.connect(self.auto_sync)
        if config.get("sync_enabled", False): self.sync_timer.start(config.get("sync_interval", 3600) * 1000)
        
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

    def log_activity(self, module, desc):
        try:
            now = datetime.now().isoformat()
            db.c.execute("INSERT INTO activity_logs (timestamp, module, description, uuid, modified_at) VALUES (?, ?, ?, ?, ?)",
                         (now, module, desc, uuid.uuid4().hex, now))
            db.conn.commit()
        except: pass

    def handle_sync_progress(self, msg):
        print(f"[SyncManager] 🔄 {msg}")
        self.sync_progress.emit(msg)
    def handle_sync_completed(self, success, msg):
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"[SyncManager] {status}: {msg}")
        
        # === ADD THESE TWO LINES ===
        config.set("git_status", "connected" if success else "error")
        config.set("git_last_sync", datetime.now().isoformat())
        # ============================
        
        self.sync_completed.emit(success, msg)
        if success:
            self.log_activity("Sync", f"Successfully synced with Git cluster. {msg}")
        else:
            self.log_activity("Sync Error", f"Sync failed: {msg}")
    def handle_attention(self, att):
        self.current_att = att

    def emit_video_frame(self, b64):
        if getattr(self, 'feed_active', False):
            self.video_feed.emit(b64)

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
                        self.log_activity("Scanner", f"Auto-parsed body scan: {f}")
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
        if not hasattr(self, 'last_speak_time') or (datetime.now() - self.last_speak_time).total_seconds() > 10:
            self.last_speak_time = datetime.now()
            if sys.platform == "darwin": subprocess.Popen(["say", text])
            elif sys.platform == "win32":
                try:
                    import pyttsx3
                    engine = pyttsx3.init(); engine.say(text); engine.runAndWait()
                except ImportError: pass
            else: subprocess.Popen(["espeak", text], stderr=subprocess.DEVNULL)

    def set_max_volume(self):
        if sys.platform == "darwin":
            if not hasattr(self, 'last_vol_time') or (datetime.now() - self.last_vol_time).total_seconds() > 10:
                self.last_vol_time = datetime.now()
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
        if config.get("sync_enabled", False): 
            threading.Thread(target=self.sync_manager.sync, daemon=True).start()

    def backup_data(self):
        backup_dir = os.path.join(os.path.expanduser("~"), "MindPalaceBackups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"auto_backup_{timestamp}.zip")
        settings = config.cfg.copy(); settings.pop("sync_github_token", None)
        data = {"settings": settings, "tables": {}}
        tables = ["courses", "pomodoro_sessions", "cascading_goals", "habits", "habit_logs", "flashcards", "quizzes", "focus_queue", "notes", "health_profile", "health_logs", "custom_foods", "custom_activities", "health_plans"]
        for table in tables:
            try:
                db.c.execute(f"SELECT * FROM {table}"); columns = [desc[0] for desc in db.c.description]
                data["tables"][table] = [dict(zip(columns, row)) for row in db.c.fetchall()]
            except: pass
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("data.json", json.dumps(data, indent=2))
        with open(backup_path, 'wb') as f: f.write(zip_buffer.getvalue())

    def get_goals_tree(self):
        try:
            db.c.execute("SELECT id, parent_id, title, target_hours, deadline FROM cascading_goals")
            return [{"id": r[0], "parent_id": r[1], "title": r[2], "target_hours": r[3], "deadline": r[4]} for r in db.c.fetchall()]
        except: return []

    def get_flat_goals(self):
        try:
            db.c.execute("SELECT id, parent_id, title FROM cascading_goals")
            tree = {r[0]: {"parent": r[1], "title": r[2]} for r in db.c.fetchall()}
            paths = []
            for gid, data in tree.items():
                path = [data["title"]]; curr = data["parent"]
                while curr in tree: path.insert(0, tree[curr]["title"]); curr = tree[curr]["parent"]
                paths.append(" > ".join(path))
            return sorted(paths)
        except: return []
        
    def get_heatmap_data(self):
        weeks = 28; matrix = [[0]*7 for _ in range(weeks)]; td = datetime.now().date()
        try:
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
        except: return matrix

    # --- CLUSTER MASTER TAG HELPER ---
    def get_cluster_master(self):
        cluster_file = os.path.join(self.sync_manager.repo_path, "cluster_state.json")
        if os.path.exists(cluster_file):
            try:
                with open(cluster_file, "r") as f:
                    return json.load(f).get("master_id")
            except: pass
        return None

    @pyqtSlot(str, result=str)
    @audit_log 
    def request(self, payload):
        req = json.loads(payload)
        action = req.get("action")
        
        if action == "init":
            today_str = datetime.now().date().isoformat()
            ydy_str = (datetime.now().date() - timedelta(days=1)).isoformat()
            
            try:
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
                
                db.c.execute("SELECT id, log_type, date, data_json FROM health_logs")
                h_logs = [{"id": r[0], "type": r[1], "date": r[2], "data": json.loads(r[3])} for r in db.c.fetchall()]

                try:
                    db.c.execute("SELECT timestamp, module, description FROM activity_logs ORDER BY timestamp DESC LIMIT 50")
                    act_logs = [{"timestamp": r[0], "module": r[1], "description": r[2]} for r in db.c.fetchall()]
                except:
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

                return json.dumps({
                    "course_colors": ccolors,
                    "flat_goals": flat_goals,
                    "goals": self.get_goals_tree(),
                    "heatmap": self.get_heatmap_data(),
                    "settings": config.cfg,
                    "activity_logs": act_logs,
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
            except Exception as e:
                return json.dumps({"error": str(e)})
        

        elif action == "get_today_data":
            try:
                today_str = datetime.now().strftime("%Y-%m-%d")
                db.c.execute("SELECT id, course, duration, actual_duration, timestamp, type, distractions, timelapse_path, distraction_data, note FROM pomodoro_sessions WHERE timestamp LIKE ? ORDER BY timestamp ASC", (today_str + '%',))
                today_sessions = [{"id": r[0], "course": r[1], "duration": r[2], "actual_duration": r[3], "timestamp": r[4], "type": r[5], "distractions": r[6], "timelapse_path": r[7], "distraction_data": json.loads(r[8] if r[8] else "[]"), "note": r[9] or ""} for r in db.c.fetchall()]
                
                db.c.execute("SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND timestamp LIKE ?", (today_str + '%',))
                studied = {r[0]: (r[1] or 0)/60.0 for r in db.c.fetchall()}
                
                return json.dumps({"today_sessions": today_sessions, "studied_hours": studied})
            except: return json.dumps({"today_sessions": [], "studied_hours": {}})
        elif action == "force_reset_all_data":
            try:
                # 1. Clear all tables (including deleted_uuids)
                tables_to_clear = [
                    "courses", "pomodoro_sessions", "cascading_goals", "habits", 
                    "habit_logs", "flashcards", "quizzes", "focus_queue", "notes", 
                    "health_profile", "health_logs", "custom_foods", "custom_activities", 
                    "health_plans", "activity_logs", "ingredients", "composite_foods", 
                    "recipe_ingredients", "deleted_uuids"
                ]
                for table in tables_to_clear:
                    try:
                        db.c.execute(f"DELETE FROM {table}")
                    except Exception as e:
                        print(f"Clear table {table} error: {e}")
                db.conn.commit()

                # 2. Reset config to defaults, but preserve sync settings
                repo_url = config.get("sync_repo_url", "")
                token = config.get("sync_github_token", "")
                sync_enabled = config.get("sync_enabled", False)
                sync_interval = config.get("sync_interval", 3600)

                new_config = config.defaults.copy()
                new_config["sync_repo_url"] = repo_url
                new_config["sync_github_token"] = token
                new_config["sync_enabled"] = sync_enabled
                new_config["sync_interval"] = sync_interval
                # Reset sync status
                new_config["git_status"] = "unknown"
                new_config["git_last_sync"] = None
                new_config["sync_msg"] = ""
                new_config["sync_progress_pct"] = 0

                config.cfg = new_config
                with open(config.fn, 'w') as f:
                    json.dump(config.cfg, f)

                # 3. Delete the local Git sync repository
                import shutil
                repo_path = os.path.expanduser("~/.mindpalace_sync_repo")
                if os.path.exists(repo_path):
                    shutil.rmtree(repo_path)

                self.log_activity("System", "Force reset all data performed")

                return json.dumps({"status": "success", "message": "All local data wiped."})
            except Exception as e:
                self.log_activity("System Error", f"Force reset failed: {str(e)}")
                return json.dumps({"status": "error", "message": str(e)})

        elif action == "get_history_data":
            try:
                db.c.execute("SELECT id, course, duration, actual_duration, timestamp, type, distractions, timelapse_path, distraction_data, note FROM pomodoro_sessions ORDER BY timestamp DESC")
                history = [{"id": r[0], "course": r[1], "duration": r[2], "actual_duration": r[3], "timestamp": r[4], "type": r[5], "distractions": r[6], "timelapse_path": r[7], "distraction_data": json.loads(r[8] if r[8] else "[]"), "note": r[9] or ""} for r in db.c.fetchall()]
                return json.dumps({"history_sessions": history})
            except: return json.dumps({"history_sessions": []})

        elif action == "play_timelapse":
            try:
                path = req.get("path")
                if os.path.exists(path):
                    if not hasattr(self, 'tl_dlg'): self.tl_dlg = None
                    self.tl_dlg = TimelapseDialog(path, req.get("duration", 0), req.get("distractions", 0), req.get("data", {}))
                    self.tl_dlg.show()
                    self.tl_dlg.raise_()
                    self.tl_dlg.activateWindow()
            except Exception as e:
                import traceback
                print("Timelapse Playback Error:", traceback.format_exc())
            return json.dumps({"status": "ok"})
            
        elif action == "save_session_note":
            s_id = req.get("session_id")
            note = req.get("note")
            if s_id:
                db.c.execute("UPDATE pomodoro_sessions SET note = ? WHERE id = ?", (note, s_id))
                db.conn.commit()
            return json.dumps({"status": "ok"})

        elif action == "save_settings":
            for k, v in req.get("data", {}).items(): config.set(k, v)
            self.log_activity("Settings", "Updated application settings via UI.")
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

        # --- SYNC CORE OVERRIDES FOR MASTER TOPOLOGY ---
        elif action == "sync_now":
            def sync_thread():
                try:
                    self.sync_progress.emit("Starting K-Peer Sync...")
                    success, msg = self.sync_manager.setup_repo()
                    if not success:
                        self.handle_sync_completed(False, msg); return
                    
                    origin = self.sync_manager.repo.remotes.origin
                    from sync_manager import DetailedSyncProgress
                    self.sync_progress.emit("Pulling cluster state...")
                    origin.pull(rebase=False, progress=DetailedSyncProgress())
                    
                    master_id = self.get_cluster_master()
                    is_master = (self.sync_manager.device_id == master_id) or (master_id is None)
                    
                    self.sync_progress.emit("Merging remote changes...")
                    self.sync_manager.ensure_uuids_and_timestamps()
                    
                    # Custom Merge Logic adhering to Master Node
                    sync_dir = os.path.join(self.sync_manager.repo_path, self.sync_manager.db_sync_dir)
                    if os.path.exists(sync_dir):
                        db.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence')")
                        valid_tables = [r[0] for r in db.c.fetchall()]
                        for filename in os.listdir(sync_dir):
                            if not filename.endswith('.json') or filename == f"{self.sync_manager.device_id}.json": continue
                            # Strict Topology: If I am a client, I ONLY accept the Master's JSON.
                            if not is_master and master_id and filename != f"{master_id}.json": continue
                            
                            try:
                                with open(os.path.join(sync_dir, filename), 'r', encoding='utf-8') as f: remote_data = json.load(f)
                                r_sync = remote_data.get("last_sync", "")
                                l_sync = config.get("last_sync_timestamp", "")
                                if r_sync and (not l_sync or r_sync > l_sync):
                                    for k, v in remote_data.get("settings", {}).items():
                                        if k not in ["device_id", "has_token", "git_status"]: config.set(k, v)
                                    config.set("last_sync_timestamp", r_sync)
                                
                                for table, rows in remote_data.get("tables", {}).items():
                                    if table not in valid_tables: continue
                                    db.c.execute(f"PRAGMA table_info({table})")
                                    columns = [info[1] for info in db.c.fetchall()]
                                    if "uuid" not in columns or "modified_at" not in columns: continue
                                        
                                    for row in rows:
                                        uid = row.get("uuid")
                                        if not uid: continue
                                        in_mod = row.get("modified_at", "")
                                        db.c.execute(f"SELECT id, modified_at FROM {table} WHERE uuid = ?", (uid,))
                                        existing = db.c.fetchone()
                                        if existing:
                                            if not existing[1] or (in_mod and in_mod > existing[1]):
                                                set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k not in ["id", "uuid"]])
                                                values = [row[k] for k in row.keys() if k not in ["id", "uuid"]] + [existing[0]]
                                                try: db.c.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                                                except: pass
                                        else:
                                            row.pop("id", None) 
                                            cols = ", ".join(row.keys()); placeholders = ", ".join(["?"] * len(row))
                                            try: db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
                                            except: pass
                            except Exception as e: print(f"Merge error {filename}: {e}")
                        db.conn.commit()

                    self.sync_progress.emit("Exporting local state...")
                    local_data = self.sync_manager.export_local_data()
                    export_path = os.path.join(self.sync_manager.repo_path, self.sync_manager.sync_data_file)
                    os.makedirs(os.path.dirname(export_path), exist_ok=True)
                    with open(export_path, 'w', encoding='utf-8') as f: json.dump(local_data, f, indent=2)
                    
                    self.sync_progress.emit("Pushing to cluster...")
                    self.sync_manager.repo.git.add(export_path, force=True)
                    self.sync_manager.repo.git.add(all=True)
                    if self.sync_manager.repo.is_dirty() or self.sync_manager.repo.untracked_files:
                        self.sync_manager.repo.index.commit(f"Sync from {self.sync_manager.device_id}")
                    origin.push(progress=DetailedSyncProgress())
                    self.handle_sync_completed(True, "K-Peer Sync completed successfully")
                except Exception as e:
                    self.handle_sync_completed(False, str(e))
            threading.Thread(target=sync_thread, daemon=True).start()
            return json.dumps({"status": "started"})
            
        elif action == "hard_clone_remote":
            target_device = req.get("target_device")  # could be None, "MASTER", or a device ID
            def hard_clone_thread():
                try:
                    # Safely format progress message
                    safe_target = target_device if target_device else "Unknown"
                    self.sync_progress.emit(f"Starting Hard Clone for Node {safe_target[:8]}...")
                    
                    success, msg = self.sync_manager.setup_repo()
                    if not success:
                        self.handle_sync_completed(False, msg)
                        return
                    
                    self.sync_progress.emit("Pulling Network Data from Git...")
                    origin = self.sync_manager.repo.remotes.origin
                    try:
                        from sync_manager import DetailedSyncProgress
                        origin.pull(rebase=False, progress=DetailedSyncProgress())
                    except Exception as e:
                        print("Pull warning:", e)
                    
                    # Determine target JSON file safely
                    sync_dir = os.path.join(self.sync_manager.repo_path, self.sync_manager.db_sync_dir)
                    target_file = None
                    
                    # If we have a master_id, use it for "MASTER" target
                    # Determine target JSON file
                    master_id = None
                    if hasattr(self.sync_manager, '_get_master_id'):
                        master_id = self.sync_manager._get_master_id()

                    if target_device == "MASTER" and master_id:
                        target_file = os.path.join(sync_dir, f"{master_id}.json")
                    elif target_device and target_device != "MASTER":
                        target_file = os.path.join(sync_dir, f"{target_device}.json")
                    else:
                        target_file = None

                    # If still no file, try using the master's file (even if it's the current device)
                    if not target_file or not os.path.exists(target_file):
                        if master_id:
                            target_file = os.path.join(sync_dir, f"{master_id}.json")
                        else:
                            # fallback to first JSON (excluding own) as before
                            json_files = [f for f in os.listdir(sync_dir) if f.endswith('.json') and f != f"{self.sync_manager.device_id}.json"]
                            if json_files:
                                target_file = os.path.join(sync_dir, json_files[0])

                    if not target_file or not os.path.exists(target_file):
                        self.handle_sync_completed(False, f"No JSON file found. Sync directory: {sync_dir}")
                        return
                    # Final existence check
                    if not os.path.exists(target_file):
                        self.handle_sync_completed(False, f"Target JSON file not found: {target_file}")
                        return
                    
                    self.sync_progress.emit("Wiping local database...")
                    tables_to_clear = [
                        "courses", "pomodoro_sessions", "cascading_goals", "habits", 
                        "habit_logs", "flashcards", "quizzes", "focus_queue", "notes", 
                        "health_profile", "health_logs", "custom_foods", "custom_activities", 
                        "health_plans", "activity_logs", "ingredients", "composite_foods", "recipe_ingredients"
                    ]
                    for table in tables_to_clear:
                        try:
                            db.c.execute(f"DELETE FROM {table}")
                        except Exception as e:
                            print(f"Clear table {table} error: {e}")
                    db.c.execute("DELETE FROM deleted_uuids")
                    db.conn.commit()

                    self.sync_progress.emit("Injecting node data...")
                    with open(target_file, 'r', encoding='utf-8') as f:
                        remote_data = json.load(f)
                    
                    # Import settings (skip device‑specific keys)
                    for k, v in remote_data.get("settings", {}).items():
                        if k not in ["device_id", "has_token", "git_status"]:
                            config.set(k, v)
                    
                    # Import tables
                    for table, rows in remote_data.get("tables", {}).items():
                        if table not in tables_to_clear:
                            continue
                        for row in rows:
                            cols = ", ".join(row.keys())
                            placeholders = ", ".join(["?"] * len(row))
                            try:
                                db.c.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(row.values()))
                            except Exception as e:
                                print(f"Clone insert error {table}: {e}")
                    db.conn.commit()
                    
                    self.handle_sync_completed(True, f"Successfully cloned from {os.path.basename(target_file)}. Restart App.")
                except Exception as e:
                    self.handle_sync_completed(False, str(e))
            
            threading.Thread(target=hard_clone_thread, daemon=True).start()
            return json.dumps({"status": "started"})
        elif action == "force_sync_now":
            def force_sync_thread():
                try:
                    self.sync_progress.emit("Starting MASTER OVERWRITE sync...")
                    success, msg = self.sync_manager.setup_repo()
                    if not success:
                        self.handle_sync_completed(False, msg); return
                        
                    self.sync_progress.emit("Promoting device to Cluster Master...")
                    origin = self.sync_manager.repo.remotes.origin
                    try:
                        from sync_manager import DetailedSyncProgress
                        origin.pull(rebase=False, progress=DetailedSyncProgress())
                    except: pass 
                    
                    cluster_file = os.path.join(self.sync_manager.repo_path, "cluster_state.json")
                    with open(cluster_file, "w") as f:
                        json.dump({"master_id": self.sync_manager.device_id, "timestamp": datetime.now().isoformat()}, f)
                    
                    # Remove all other nodes' JSONs
                    sync_dir = os.path.join(self.sync_manager.repo_path, self.sync_manager.db_sync_dir)
                    if os.path.exists(sync_dir):
                        for f in os.listdir(sync_dir):
                            if f.endswith('.json') and f != f"{self.sync_manager.device_id}.json":
                                try: os.remove(os.path.join(sync_dir, f))
                                except: pass
                    
                    # Clear local deletion log
                    db.c.execute("DELETE FROM deleted_uuids")
                    db.conn.commit()
                    
                    self.sync_progress.emit("Exporting Master local data...")
                    self.sync_manager.ensure_uuids_and_timestamps()
                    local_data = self.sync_manager.export_local_data()
                    export_path = os.path.join(self.sync_manager.repo_path, self.sync_manager.sync_data_file)
                    os.makedirs(os.path.dirname(export_path), exist_ok=True)
                    with open(export_path, 'w', encoding='utf-8') as f: 
                        json.dump(local_data, f, indent=2)
                        
                    self.sync_progress.emit("Force Pushing Master to GitHub...")
                    self.sync_manager.repo.git.add(cluster_file, force=True)
                    self.sync_manager.repo.git.add(export_path, force=True)
                    self.sync_manager.repo.git.add(all=True)
                    if self.sync_manager.repo.is_dirty() or self.sync_manager.repo.untracked_files:
                        self.sync_manager.repo.index.commit(f"MASTER PROMOTE from {self.sync_manager.device_id}")
                    origin.push(progress=DetailedSyncProgress())
                    self.handle_sync_completed(True, "Master Overwrite completed successfully")
                except Exception as e:
                    self.handle_sync_completed(False, str(e))
            threading.Thread(target=force_sync_thread, daemon=True).start()
            return json.dumps({"status": "started"})

        elif action == "get_device_id":
            return json.dumps({"device_id": self.sync_manager.device_id})

        elif action == "set_vision_ui":
            self.vision.ui_active = req.get("active", False)
            return json.dumps({"status": "ok"})

        elif action == "toggle_feed":
            self.feed_active = req.get("enabled", False)
            return json.dumps({"status": "ok"})

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
            net_folders = self.sync_manager.get_network_folders()
            
            repo_path = self.sync_manager.repo_path
            discovered_nodes = set([f["device_id"] for f in net_folders])
            
            if os.path.exists(repo_path):
                for root_dir, _, files in os.walk(repo_path):
                    if '.git' in root_dir: continue
                    for f in files:
                        if f.endswith('.json'): 
                            try:
                                with open(os.path.join(root_dir, f), 'r', encoding='utf-8') as tmp_f:
                                    d = json.load(tmp_f)
                                    dev_id = d.get("device_id")
                                    if dev_id and dev_id not in discovered_nodes:
                                        discovered_nodes.add(dev_id)
                                        net_folders.append({
                                            "device_id": dev_id,
                                            "is_local": dev_id == self.sync_manager.device_id,
                                            "file_count": 1,
                                            "last_update": d.get("last_sync", "Unknown").replace("T", " ")[:16],
                                            "path": ""
                                        })
                            except: pass

            return json.dumps({
                "folders": config.get("sync_local_paths", []),
                "network_folders": net_folders
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
            master_id = None
            try:
                if hasattr(self.sync_manager, '_get_master_id'):
                    master_id = self.sync_manager._get_master_id()
            except:
                pass
            return json.dumps({
                "enabled": config.get("sync_enabled", False), 
                "device_id": self.sync_manager.device_id, 
                "repo_url": config.get("sync_repo_url", ""), 
                "interval": config.get("sync_interval", 3600), 
                "has_token": bool(GITHUB_TOKEN),
                "master_id": master_id
            })

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
            if req.get("queue_id") == "auto":
                db.c.execute("SELECT id, duration, course, type FROM focus_queue WHERE status='pending' ORDER BY id ASC LIMIT 1")
                q = db.c.fetchone()
                if q:
                    self.active_queue_id = q[0]
                    self.total_time = int(q[1]) * 60
                    self.current_course = q[2] or "General"
                    db.c.execute("UPDATE focus_queue SET status='active' WHERE id=?", (self.active_queue_id,))
                    db.conn.commit()
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
                course_safe = self.current_course.replace(' ', '_').replace('/', '')
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.vision.start_rec(f"timelapses/Work_{course_safe}_{ts}.avi")

            self.timer.start(1000)
            self.push_state()
            return json.dumps({"status": "started"})

        elif action == "stop_timer":
            self.is_running = False
            self.timer.stop()
            self.ovl.hide()
            self.vision.stop()
            self.time_left = 0
            
            if self.active_queue_id:
                db.c.execute("UPDATE focus_queue SET status='pending' WHERE id=?", (self.active_queue_id,))
                self.active_queue_id = None
                db.conn.commit()
            
            self.push_state()
            return json.dumps({"status": "stopped"})

        elif action == "pause_timer":
            if self.is_running:
                self.is_running = False
                self.timer.stop()
                self.vision.stop()
                if self.was_distracted:
                    dur = (self.total_time - self.time_left) - self.distraction_start
                    self.distraction_log.append([self.distraction_start / 60.0, dur / 60.0, self.distraction_type_current])
                    self.was_distracted = False
                self.push_state()
            return json.dumps({"status": "paused"})
            
        elif action == "resume_timer":
            if not self.is_running and self.time_left > 0:
                self.is_running = True
                self.timer.start(1000)
                if not config.get("quiet_mode", False):
                    self.vision.start()
                self.push_state()
            return json.dumps({"status": "resumed"})

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
                queue_uuid = db.c.execute("SELECT uuid FROM focus_queue WHERE id=?", (target_id,)).fetchone()
                if queue_uuid:
                    db.c.execute("DELETE FROM focus_queue WHERE id=?", (target_id,))
                    db.c.execute("INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                                ("focus_queue", queue_uuid[0], datetime.now().isoformat()))
                if self.active_queue_id == target_id:
                    self.active_queue_id = None
                    self.is_running = False
                    self.timer.stop()
            elif sub == "clear":
                # Get all UUIDs before clearing
                queue_uuids = db.c.execute("SELECT uuid FROM focus_queue").fetchall()
                db.c.execute("DELETE FROM focus_queue")
                for (uuid_val,) in queue_uuids:
                    db.c.execute("INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                                ("focus_queue", uuid_val, datetime.now().isoformat()))
                self.active_queue_id = None
                self.is_running = False
                self.timer.stop()
            db.conn.commit()
            
            db.c.execute("SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id")
            queue_data = [{"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]} for r in db.c.fetchall()]
            return json.dumps({"queue": queue_data})

        elif action == "manage_nutrition":
            sub = req.get("sub")
            if sub == "get_all":
                db.c.execute("SELECT id, name, kcal, protein, fat, carbs, image_path, is_iranian FROM ingredients ORDER BY name")
                ing = [{"id": r[0], "name": r[1], "kcal": r[2], "protein": r[3], "fat": r[4], "carbs": r[5], "image_path": r[6], "is_iranian": r[7]} for r in db.c.fetchall()]
                
                db.c.execute("SELECT id, name, image_path FROM composite_foods ORDER BY name")
                comps = []
                for c_id, c_name, c_img in db.c.fetchall():
                    db.c.execute("SELECT i.name, ri.amount_grams, i.kcal, i.protein, i.fat, i.carbs FROM recipe_ingredients ri JOIN ingredients i ON ri.ingredient_id = i.id WHERE ri.composite_food_id = ?", (c_id,))
                    parts = [{"name": r[0], "amount_grams": r[1], "kcal": (r[2]*r[1]/100.0), "protein": (r[3]*r[1]/100.0)} for r in db.c.fetchall()]
                    t_kcal = sum(p["kcal"] for p in parts)
                    t_pro = sum(p["protein"] for p in parts)
                    comps.append({"id": c_id, "name": c_name, "image_path": c_img, "parts": parts, "kcal": t_kcal, "protein": t_pro})
                    
                return json.dumps({"ingredients": ing, "composite_foods": comps})
                
            elif sub == "add_ingredient":
                try:
                    db.c.execute("INSERT INTO ingredients (uuid, modified_at, name, kcal, protein, fat, carbs, image_path, is_iranian) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (uuid.uuid4().hex, datetime.now().isoformat(), req.get("name"), float(req.get("kcal") or 0), float(req.get("protein") or 0), float(req.get("fat") or 0), float(req.get("carbs") or 0), req.get("image_path", ""), req.get("is_iranian", False)))
                    db.conn.commit()
                except sqlite3.IntegrityError:
                    pass
                return self.request(json.dumps({"action": "manage_nutrition", "sub": "get_all"}))
                
            elif sub == "delete_ingredient":
                db.c.execute("DELETE FROM ingredients WHERE id=?", (req.get("id"),))
                db.c.execute("DELETE FROM recipe_ingredients WHERE ingredient_id=?", (req.get("id"),))
                db.conn.commit()
                return self.request(json.dumps({"action": "manage_nutrition", "sub": "get_all"}))
                
            elif sub == "add_composite":
                c_uuid = uuid.uuid4().hex
                try:
                    db.c.execute("INSERT INTO composite_foods (uuid, modified_at, name, image_path) VALUES (?, ?, ?, ?)", (c_uuid, datetime.now().isoformat(), req.get("name"), req.get("image_path", "")))
                    c_id = db.c.lastrowid
                    for part in req.get("parts", []):
                        db.c.execute("INSERT INTO recipe_ingredients (uuid, modified_at, composite_food_id, ingredient_id, amount_grams) VALUES (?, ?, ?, ?, ?)", 
                            (uuid.uuid4().hex, datetime.now().isoformat(), c_id, part["ingredient_id"], part["amount_grams"]))
                    db.conn.commit()
                except sqlite3.IntegrityError: pass
                return self.request(json.dumps({"action": "manage_nutrition", "sub": "get_all"}))

            elif sub == "delete_composite":
                db.c.execute("DELETE FROM composite_foods WHERE id=?", (req.get("id"),))
                db.c.execute("DELETE FROM recipe_ingredients WHERE composite_food_id=?", (req.get("id"),))
                db.conn.commit()
                return self.request(json.dumps({"action": "manage_nutrition", "sub": "get_all"}))

        elif action == "manage_health":
            sub = req.get("sub")
            if sub == "save_profile": 
                db.c.execute("INSERT INTO health_profile (uuid, modified_at, data_json) VALUES (?, ?, ?)", 
                            (uuid.uuid4().hex, datetime.now().isoformat(), json.dumps(req.get("data"))))
            elif sub == "log_entry": 
                db.c.execute("INSERT INTO health_logs (uuid, modified_at, log_type, date, data_json) VALUES (?, ?, ?, ?, ?)", 
                            (uuid.uuid4().hex, datetime.now().isoformat(), req.get("log_type"), req.get("date"), json.dumps(req.get("data"))))
            elif sub == "delete_log":
                # Get UUID before deletion
                log_uuid = db.c.execute("SELECT uuid FROM health_logs WHERE id=?", (req.get("id"),)).fetchone()
                if log_uuid:
                    db.c.execute("DELETE FROM health_logs WHERE id=?", (req.get("id"),))
                    db.c.execute("INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                                ("health_logs", log_uuid[0], datetime.now().isoformat()))
            elif sub == "save_food": 
                db.c.execute("INSERT OR REPLACE INTO custom_foods (uuid, modified_at, name, kcal, protein, fat, carbs, category) VALUES (COALESCE((SELECT uuid FROM custom_foods WHERE name=?), ?), ?, ?, ?, ?, ?, ?, ?)", 
                            (req.get("name"), uuid.uuid4().hex, datetime.now().isoformat(), req.get("name"), req.get("kcal"), req.get("protein"), req.get("fat"), req.get("carbs"), req.get("category")))
            elif sub == "save_activity": 
                db.c.execute("INSERT OR REPLACE INTO custom_activities (uuid, modified_at, name, met, category) VALUES (COALESCE((SELECT uuid FROM custom_activities WHERE name=?), ?), ?, ?, ?, ?)", 
                            (req.get("name"), uuid.uuid4().hex, datetime.now().isoformat(), req.get("name"), req.get("met"), req.get("category")))
            elif sub == "save_plan": 
                db.c.execute("INSERT OR REPLACE INTO health_plans (uuid, modified_at, type, title, details) VALUES (COALESCE((SELECT uuid FROM health_plans WHERE title=?), ?), ?, ?, ?, ?)", 
                            (req.get("title"), uuid.uuid4().hex, datetime.now().isoformat(), req.get("type"), req.get("title"), req.get("details")))
            elif sub == "delete_plan":
                # Get UUID before deletion
                plan_uuid = db.c.execute("SELECT uuid FROM health_plans WHERE id=?", (req.get("id"),)).fetchone()
                if plan_uuid:
                    db.c.execute("DELETE FROM health_plans WHERE id=?", (req.get("id"),))
                    db.c.execute("INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                                ("health_plans", plan_uuid[0], datetime.now().isoformat()))
            db.conn.commit()
            return json.dumps({
                "health_logs": [{"id": r[0], "type": r[1], "date": r[2], "data": json.loads(r[3])} 
                                for r in db.c.execute("SELECT id, log_type, date, data_json FROM health_logs ORDER BY modified_at DESC").fetchall()], 
                "custom_foods": [{"id": r[0], "name": r[1], "kcal": r[2], "protein": r[3], "fat": r[4], "carbs": r[5], "category": r[6]} 
                                for r in db.c.execute("SELECT id, name, kcal, protein, fat, carbs, category FROM custom_foods").fetchall()], 
                "custom_activities": [{"id": r[0], "name": r[1], "met": r[2], "category": r[3]} 
                                    for r in db.c.execute("SELECT id, name, met, category FROM custom_activities").fetchall()], 
                "health_plans": [{"id": r[0], "type": r[1], "title": r[2], "details": r[3]} 
                                for r in db.c.execute("SELECT id, type, title, details FROM health_plans").fetchall()]
            })
        elif action == "manage_habit":
            sub = req.get("sub")
            if sub == "add": 
                db.c.execute("INSERT INTO habits (uuid, modified_at, name, type, created_at) VALUES (?, ?, ?, ?, ?)", 
                            (uuid.uuid4().hex, datetime.now().isoformat(), req.get("name"), req.get("type", "Positive"), datetime.now().isoformat()))
            elif sub == "edit": 
                db.c.execute("UPDATE habits SET name=?, type=?, modified_at=? WHERE id=?", 
                            (req.get("name"), req.get("type"), datetime.now().isoformat(), req.get("id")))
            elif sub == "delete": 
                # Get UUID before deletion
                habit_uuid = db.c.execute("SELECT uuid FROM habits WHERE id=?", (req.get("id"),)).fetchone()
                if habit_uuid:
                    db.c.execute("DELETE FROM habits WHERE id=?", (req.get("id"),))
                    db.c.execute("DELETE FROM habit_logs WHERE habit_id=?", (req.get("id"),))
                    db.c.execute("INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                                ("habits", habit_uuid[0], datetime.now().isoformat()))
            elif sub == "toggle_log":
                hid, dt, st = req.get("habit_id"), req.get("date"), req.get("status", 1)
                existing = db.c.execute("SELECT id FROM habit_logs WHERE habit_id=? AND date=?", (hid, dt)).fetchone()
                if existing: 
                    db.c.execute("UPDATE habit_logs SET status=?, modified_at=? WHERE id=?", (st, datetime.now().isoformat(), existing[0]))
                else: 
                    db.c.execute("INSERT INTO habit_logs (uuid, modified_at, habit_id, date, status) VALUES (?, ?, ?, ?, ?)", 
                                (uuid.uuid4().hex, datetime.now().isoformat(), hid, dt, st))
            db.conn.commit()
            return json.dumps({
                "habits": [{"id": r[0], "name": r[1], "type": r[2]} for r in db.c.execute("SELECT id, name, type FROM habits").fetchall()], 
                "habit_logs": [{"habit_id": r[0], "date": r[1], "status": r[2]} for r in db.c.execute("SELECT habit_id, date, status FROM habit_logs").fetchall()]
            })
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
                # Get UUID before deletion
                note_uuid = db.c.execute("SELECT uuid FROM notes WHERE id=?", (req.get("id"),)).fetchone()
                if note_uuid:
                    db.c.execute("DELETE FROM notes WHERE id=?", (req.get("id"),))
                    db.c.execute("INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                                ("notes", note_uuid[0], datetime.now().isoformat()))
            db.conn.commit()
            return json.dumps({
                "notes": [{"id": r[0], "title": r[1], "content": r[2], "course": r[3], "folder": r[4], "color": r[5]} 
                        for r in db.c.execute("SELECT id, title, content, course, folder, color FROM notes ORDER BY id DESC").fetchall()]
            })
        elif action == "manage_flashcard":
            sub = req.get("sub")
            if sub == "add": 
                db.c.execute("INSERT INTO flashcards (uuid, modified_at, front, back, deck, course, folder, color) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                            (uuid.uuid4().hex, datetime.now().isoformat(), req.get("front"), req.get("back"), req.get("deck"), req.get("course"), req.get("folder"), req.get("color")))
            elif sub == "delete":
                # Get UUID before deletion
                card_uuid = db.c.execute("SELECT uuid FROM flashcards WHERE id=?", (req.get("id"),)).fetchone()
                if card_uuid:
                    db.c.execute("DELETE FROM flashcards WHERE id=?", (req.get("id"),))
                    db.c.execute("INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                                ("flashcards", card_uuid[0], datetime.now().isoformat()))
            db.conn.commit()
            return json.dumps({
                "flashcards": [{"id": r[0], "front": r[1], "back": r[2], "deck": r[3], "course": r[4], "folder": r[5], "color": r[6]} 
                            for r in db.c.execute("SELECT id, front, back, deck, course, folder, color FROM flashcards").fetchall()]
            })


        elif action == "manage_quiz":
            sub = req.get("sub")
            if sub == "add": 
                db.c.execute("INSERT INTO quizzes (uuid, modified_at, title, questions_json, course, folder, color) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                            (uuid.uuid4().hex, datetime.now().isoformat(), req.get("title"), req.get("json"), req.get("course"), req.get("folder"), req.get("color")))
            elif sub == "delete":
                # Get UUID before deletion
                quiz_uuid = db.c.execute("SELECT uuid FROM quizzes WHERE id=?", (req.get("id"),)).fetchone()
                if quiz_uuid:
                    db.c.execute("DELETE FROM quizzes WHERE id=?", (req.get("id"),))
                    db.c.execute("INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                                ("quizzes", quiz_uuid[0], datetime.now().isoformat()))
            db.conn.commit()
            return json.dumps({
                "quizzes": [{"id": r[0], "title": r[1], "json": r[2], "course": r[3], "folder": r[4], "color": r[5]} 
                            for r in db.c.execute("SELECT id, title, questions_json, course, folder, color FROM quizzes").fetchall()]
            })

        elif action == "manage_goal":
            sub = req.get("sub")
            if sub == "add": 
                db.c.execute("INSERT INTO cascading_goals (uuid, modified_at, parent_id, title, category, target_hours, deadline) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                            (uuid.uuid4().hex, datetime.now().isoformat(), req.get("parent_id"), req.get("title"), req.get("category"), float(req.get("target_hours") or 0), req.get("deadline").replace('T', ' ') if req.get("deadline") else None))
            elif sub == "delete":
                # Get UUID before deletion
                goal_uuid = db.c.execute("SELECT uuid FROM cascading_goals WHERE id=?", (req.get("id"),)).fetchone()
                if goal_uuid:
                    db.c.execute("DELETE FROM cascading_goals WHERE id=?", (req.get("id"),))
                    db.c.execute("INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                                ("cascading_goals", goal_uuid[0], datetime.now().isoformat()))
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
        
        try:
            db.c.execute("SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id")
            queue_data = [{"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]} for r in db.c.fetchall()]
        except: queue_data = []
        
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
            "last_session_data": getattr(self, 'last_session_data', None)
        }
        self.state_update.emit(json.dumps(state))

    def tick(self):
        if not self.is_running: return
        
        dist_mode = "None"
        
        if not config.get("quiet_mode", False):
            if not getattr(self, 'current_att', True):
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

        if dist_mode != "None":
            if not self.was_distracted:
                self.distraction_start = self.total_time - self.time_left
                self.was_distracted = True
                self.distraction_type_current = dist_mode
        else:
            if self.was_distracted:
                dur = (self.total_time - self.time_left) - self.distraction_start
                self.distraction_log.append([self.distraction_start / 60.0, dur / 60.0, self.distraction_type_current])
                self.was_distracted = False

        if self.time_left > 0:
            self.time_left -= 1
        else:
            if not config.get("quiet_mode", False):
                self.speak(config.get("speech_comp", "Session Complete."))
                
            if self.was_distracted:
                dur = (self.total_time - self.time_left) - self.distraction_start
                self.distraction_log.append([self.distraction_start / 60.0, dur / 60.0, self.distraction_type_current])
                self.was_distracted = False
            
            final_tl_path = getattr(self.vision, 'v_path', '')
                
            try:
                db.c.execute("""
                    INSERT INTO pomodoro_sessions (course, duration, actual_duration, timestamp, type, distractions, distraction_data, timelapse_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (self.current_course, self.total_time // 60, self.total_time // 60, datetime.now().isoformat(), 'Work', self.distractions, json.dumps(self.distraction_log), final_tl_path))
            except sqlite3.OperationalError:
                db.c.execute("""
                    INSERT INTO pomodoro_sessions (course, duration, actual_duration, timestamp, type, distractions)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (self.current_course, self.total_time // 60, self.total_time // 60, datetime.now().isoformat(), 'Work', self.distractions))
            
            self.last_completed_session_id = db.c.lastrowid
            self.last_session_data = {
                "course": self.current_course,
                "duration": self.total_time // 60,
                "distractions": self.distractions,
                "timelapse_path": final_tl_path
            }
            
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
                    
                    self.distraction_log = []
                    self.was_distracted = False
                    self.distraction_type_current = "Manual"
                    
                    db.c.execute("UPDATE focus_queue SET status='active' WHERE id=?", (self.active_queue_id,))
                    db.conn.commit()
                    
                    if not config.get("quiet_mode", False):
                        course_safe = self.current_course.replace(' ', '_').replace('/', '')
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
                
            db.conn.commit()
        
        self.push_state(dist_mode)