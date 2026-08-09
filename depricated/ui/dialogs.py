import os, json, cv2
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from core.database import db
from core.config import config
from core.signals import bus
from ui.charts import MiniTimeline

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
        hl1.addWidget(QLabel("Total Target (mins):")); self.tot_m = QSpinBox(); self.tot_m.setRange(10, 1440); self.tot_m.setValue(120); hl1.addWidget(self.tot_m)
        lay.addLayout(hl1)
        
        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("Work Block (mins):")); self.wk_m = QSpinBox(); self.wk_m.setRange(5, 240); self.wk_m.setValue(45); hl2.addWidget(self.wk_m)
        lay.addLayout(hl2)
        
        hl3 = QHBoxLayout()
        hl3.addWidget(QLabel("Break Block (mins):")); self.bk_m = QSpinBox(); self.bk_m.setRange(1, 120); self.bk_m.setValue(15); hl3.addWidget(self.bk_m)
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
            for name in scores: scores[name] += weights[name]
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
            if a in ["Google Chrome", "Finder"]: cb.setChecked(True)
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
        if self.cap: self.cap.release()
        super().closeEvent(e)

class QuickAddDialog(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 100)
        
        from ui.components import GlassPanel
        self.f = GlassPanel(self)
        self.f.setFixedSize(500, 100)
        
        self.i = QLineEdit()
        self.i.setPlaceholderText("Quick Add Task (Press Enter)...")
        self.i.setStyleSheet("background-color: rgba(10,10,15,180); color: white; padding: 12px; font-size: 16px; border-radius: 8px;")
        self.i.returnPressed.connect(self.s)
        self.f.lay.addWidget(self.i)
        QVBoxLayout(self).addWidget(self.f)
        
    def s(self):
        if self.i.text().strip(): 
            db.c.execute("INSERT INTO todos (task, is_done, quadrant) VALUES (?, 0, 'Urgent & Important')", (self.i.text().strip(),))
            db.conn.commit()
            bus.db_updated.emit()
            self.i.clear()
            self.hide()
