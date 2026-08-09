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
from core.config import config
from core.signals import bus
from ui.horology import draw_horological_face, draw_horological_hands

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
