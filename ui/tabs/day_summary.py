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
from core.database import db
from core.signals import bus
from ui.dialogs import TimelapseDialog

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
