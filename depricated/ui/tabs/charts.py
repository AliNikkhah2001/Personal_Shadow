import json
import calendar
from datetime import datetime, timedelta
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QGridLayout, QSizePolicy
from PyQt6.QtCore import Qt, QRect, QRectF, QTime, QPointF
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QFont, QPainterPath
from core.config import config
from core.database import db
from core.signals import bus
from core.utils import get_color
from ui.horology import draw_horological_face, draw_horological_hands, draw_crystal_glare

def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = (gy + 1) if (gm > 2) else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

class CircularProgress(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(140, 140)
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
        size = min(self.width(), self.height()) - 20
        r = QRect((self.width() - size)//2, (self.height() - size)//2, size, size)
        
        pt.setPen(QPen(QColor(255,255,255,30), 10))
        pt.drawArc(r, 0, 360*16)
        pct = min(self.st / self.pl, 1.0)
        
        pt.setPen(QPen(self.ring_color, 10, cap=Qt.PenCapStyle.RoundCap))
        pt.drawArc(r, 90*16, int(-pct * 360 * 16))
        
        pt.setPen(QColor("white"))
        pt.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        pt.drawText(QRect(r.x(), r.y() + r.height()//4, r.width(), 30), Qt.AlignmentFlag.AlignCenter, f"{int(pct*100)}%")
        
        pt.setFont(QFont("Arial", 9))
        pt.setPen(QColor(200, 200, 200))
        pt.drawText(QRect(r.x(), r.y() + r.height()//2, r.width(), 30), Qt.AlignmentFlag.AlignCenter, f"{int(self.st)}/{int(self.pl)}m")

class AnalogClock(QWidget):
    def __init__(self): 
        super().__init__()
        self.setMinimumSize(220, 220)
        self.ring_color = QColor("#0a84ff")
        bus.active_color_changed.connect(self.set_color)
        
    def set_color(self, c): 
        self.ring_color = c
        self.update()
        
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center_x, center_y = self.width()/2, self.height()/2
        p.translate(center_x, center_y)
        radius = min(100, min(center_x, center_y) - 10)
        
        draw_horological_face(p, radius, config.cfg)
        
        t = QTime.currentTime()
        h_style = config.get("clock_hands", "Classic")
        comp = config.get("clock_comp", "None")
        
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("white")))
        
        p.save()
        p.rotate(30.0 * (t.hour() + t.minute()/60.0))
        draw_horological_hands(p, h_style, radius * 0.5, 4, True)
        p.restore()
        
        p.save()
        p.rotate(6.0 * (t.minute() + t.second()/60.0))
        draw_horological_hands(p, h_style, radius * 0.75, 3, False)
        p.restore()
        
        sec_col = self.ring_color
        if comp == "Small Seconds": 
            p.save()
            p.translate(0, radius * 0.45)
            p.rotate(6.0 * t.second())
            p.setBrush(QBrush(sec_col))
            draw_horological_hands(p, "Baton", radius * 0.2, 1, False)
            p.restore()
        else:
            p.setBrush(QBrush(sec_col))
            p.setPen(QPen(sec_col, 2))
            p.save()
            p.rotate(6.0 * t.second())
            if h_style in ["Serpentine", "Arrow", "Sword"]: 
                draw_horological_hands(p, h_style, radius * 0.85, 1, False)
            else: 
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRect(-1, 0, 2, int(-radius * 0.85))
            p.restore()
            
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(-4, -4, 8, 8)
        
        # Draw Glare explicitly OVER the hands so it doesn't dim them
        draw_crystal_glare(p, radius)

class DashboardGoalsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0,0,0,0)
        
        self.lbl_tot = QLabel("Global Target: 0.0 / 0.0 hrs (0%)")
        self.lbl_tot.setStyleSheet("font-weight: bold; font-size: 16px; color: #0a84ff; background: transparent;")
        self.lay.addWidget(self.lbl_tot)
        
        self.bars_lay = QVBoxLayout()
        self.lay.addLayout(self.bars_lay)
        self.lay.addStretch()
        self.upd()
        bus.db_updated.connect(self.upd)
        
    def upd(self):
        for i in reversed(range(self.bars_lay.count())):
            w = self.bars_lay.itemAt(i).widget()
            if w: w.deleteLater()
                
        # Integrates deeply with Cascading Goals
        db.c.execute("SELECT title, target_hours, logged_hours FROM cascading_goals WHERE target_hours > 0")
        goals = db.c.fetchall()
        
        tot_tgt = sum(g[1] for g in goals)
        tot_std = sum(g[2] for g in goals)
        pct = min(100, int((tot_std/tot_tgt)*100)) if tot_tgt > 0 else 0
        self.lbl_tot.setText(f"Global Goals: {tot_std:.1f} / {tot_tgt:.1f} hrs ({pct}%)")
        
        rem_list = sorted([(g[0], max(0, g[1] - g[2]), g[2], g[1]) for g in goals], key=lambda x: x[1], reverse=True)
        
        for title, rem, std, tgt in rem_list[:5]:
            lbl = QLabel(f"{title[:20]} - Rem: {rem:.1f}h")
            lbl.setStyleSheet("background: transparent; font-size: 13px; color: white;")
            pb = QProgressBar()
            pb.setMaximum(100)
            pb.setValue(min(100, int((std/tgt)*100)) if tgt > 0 else 0)
            pb.setFixedHeight(14)
            pb.setTextVisible(False)
            pb.setStyleSheet(f"QProgressBar {{ background-color: rgba(255,255,255,10); border-radius: 6px; }} QProgressBar::chunk {{ background-color: {get_color(title).name()}; border-radius: 6px; }}")
            self.bars_lay.addWidget(lbl)
            self.bars_lay.addWidget(pb)

class DualFocusCalendar(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.current_date = datetime.now()
        self.work_data = {}
        self.deadlines = []
        
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀")
        self.prev_btn.clicked.connect(self.prev_m)
        self.prev_btn.setStyleSheet("background: transparent; border: none; color: white; font-size: 16px; font-weight: bold;")
        
        self.title = QLabel()
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color: white; font-weight: bold; font-size: 16px; background: transparent;")
        
        self.next_btn = QPushButton("▶")
        self.next_btn.clicked.connect(self.next_m)
        self.next_btn.setStyleSheet("background: transparent; border: none; color: white; font-size: 16px; font-weight: bold;")
        
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.title, 1)
        nav.addWidget(self.next_btn)
        self.lay.addLayout(nav)
        
        self.grid = QFrame()
        self.grid.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.grid.paintEvent = self.paint_grid
        self.grid.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.lay.addWidget(self.grid, 1)
        
        self.upd()
        bus.db_updated.connect(self.upd)

    def prev_m(self):
        first_day = self.current_date.replace(day=1)
        self.current_date = first_day - timedelta(days=1)
        self.upd()

    def next_m(self):
        days_in_month = calendar.monthrange(self.current_date.year, self.current_date.month)[1]
        last_day = self.current_date.replace(day=days_in_month)
        self.current_date = last_day + timedelta(days=1)
        self.upd()

    def upd(self):
        jy, jm, _ = gregorian_to_jalali(self.current_date.year, self.current_date.month, 1)
        j_months = ["Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar", "Mehr", "Aban", "Azar", "Dey", "Bahman", "Esfand"]
        self.title.setText(f"{self.current_date.strftime('%B %Y')} / {j_months[jm-1]} {jy}")
        
        db.c.execute("SELECT date(timestamp), sum(duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY date(timestamp)")
        self.work_data = {r[0]: r[1]/60.0 for r in db.c.fetchall()}
        
        db.c.execute("SELECT date(deadline) FROM cascading_goals WHERE deadline IS NOT NULL AND deadline != ''")
        self.deadlines = [r[0] for r in db.c.fetchall()]
        self.grid.update()

    def paint_grid(self, e):
        p = QPainter(self.grid)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.grid.width(), self.grid.height()
        cw, ch = w / 7, h / 7
        
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        p.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        for i, day in enumerate(days):
            p.setPen(QColor("#ff453a") if day in ["Sat", "Sun"] else QColor("white"))
            p.drawText(QRectF(i*cw, 0, cw, ch), Qt.AlignmentFlag.AlignCenter, day)

        year, month = self.current_date.year, self.current_date.month
        cal = calendar.Calendar()
        month_days = cal.monthdatescalendar(year, month)
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        for row, week in enumerate(month_days):
            for col, date in enumerate(week):
                if date.month != month: continue
                
                x, y = col * cw, (row + 1) * ch
                rect = QRectF(x + 2, y + 2, cw - 4, ch - 4)
                date_str = date.strftime("%Y-%m-%d")
                
                h_val = self.work_data.get(date_str, 0)
                if h_val > 0:
                    bg = QColor("#216e39") if h_val > 6 else (QColor("#30a14e") if h_val > 4 else (QColor("#40c463") if h_val > 2 else QColor("#9be9a8")))
                    p.setBrush(bg)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawRoundedRect(rect, 6, 6)
                elif date_str == today_str:
                    p.setBrush(QColor(255, 255, 255, 20))
                    p.setPen(QPen(QColor("#0a84ff"), 2))
                    p.drawRoundedRect(rect, 6, 6)
                else:
                    p.setBrush(QColor(255, 255, 255, 5))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawRoundedRect(rect, 6, 6)
                    
                jy, jm, jd = gregorian_to_jalali(date.year, date.month, date.day)
                p.setFont(QFont("Arial", 8))
                p.setPen(QColor("#ffcc00"))
                p.drawText(QRectF(x, y + 2, cw - 4, ch), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, str(jd))
                
                p.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                p.setPen(QColor("white"))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(date.day))
                
                if date_str in self.deadlines:
                    p.setBrush(QColor("#ff453a"))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QPointF(x + cw/2, y + ch - 6), 3, 3)

class ActivityHeatmap(FigureCanvas):
    def __init__(self):
        # The key fix here: set alpha to 0.0 and facecolor to 'none' so the white box goes away
        self.f, self.ax = plt.subplots(figsize=(6, 2.5))
        self.f.patch.set_alpha(0.0)
        self.ax.set_facecolor('none')
        super().__init__(self.f)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color:transparent;")
        self.upd()
        bus.db_updated.connect(self.upd)
        
    def upd(self):
        self.ax.clear()
        self.ax.set_facecolor('none')
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
            
        self.ax.imshow(mat, cmap='Blues', aspect='auto', vmin=0, vmax=8)
        self.ax.axis('off')
        
        for i in range(5):
            for j in range(7):
                if hmat[i,j] > 0: 
                    self.ax.text(j, i, f"{hmat[i,j]:.1f}h", ha="center", va="center", color="white" if mat[i,j]>4 else "#a0a0a0", fontsize=8, fontweight='bold')
        self.draw()