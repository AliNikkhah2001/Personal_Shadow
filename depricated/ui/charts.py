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

class MomentumMap(FigureCanvas):
    def __init__(self):
        self.f, self.axs = plt.subplots(3, 2, figsize=(10, 9))
        self.f.patch.set_alpha(0.0)
        super().__init__(self.f)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color:transparent;")
        self.upd()
        bus.db_updated.connect(self.upd)
        
    def upd(self):
        for ax in self.axs.flat: 
            ax.clear()
            ax.set_facecolor('none')
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
        ax1.imshow(mat, cmap='Blues', aspect='auto', vmin=0, vmax=8)
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
        ax2.bar(hours, vols, color="#0a84ff")
        ax2.set_xlim(-1, 24)
        ax2.set_ylabel("Mins")
        
        ax3 = self.axs[1,0]
        ax3.set_title("Distraction Severity Breakdown", color="white")
        db.c.execute("SELECT distraction_data FROM pomodoro_sessions WHERE type='Work' AND distraction_data IS NOT NULL")
        bins = {"<30s": 0, "<1m": 0, "<5m": 0, "<15m": 0, ">=15m": 0}
        for row in db.c.fetchall():
            if row[0]:
                try:
                    for d in json.loads(row[0]):
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
            ax3.bar(labels, values, color="#30a14e")
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
        ax6.set_title("Distraction Types", color="white")
        db.c.execute("SELECT distraction_data FROM pomodoro_sessions WHERE type='Work' AND distraction_data IS NOT NULL")
        dtypes = {"App": 0, "Camera": 0, "CameraError": 0, "Manual": 0}
        for row in db.c.fetchall():
            if row[0]:
                try:
                    for d in json.loads(row[0]):
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

class MiniTimeline(QWidget):
    def __init__(self, b):
        super().__init__()
        self.b = b
        self.setFixedHeight(30)
        
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h, d = self.width(), self.height(), self.b['duration']
        
        if d <= 0: return
            
        col = get_color(self.b['course'])
        p.setBrush(QBrush(col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 4, 4)
        
        for item in self.b.get('distractions', []):
            ds = item[0]
            dd = item[1]
            dtype = item[2] if len(item) > 2 else "Pause"
            
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
        self.sys_st = "Stopped"
        self.sys_ps = None
        
    def update_t(self, q, idx, st="Stopped", ps=None): 
        self.q = q
        self.cidx = idx
        self.sys_st = st
        self.sys_ps = ps
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
        
        crs = []
        if any(x['type'] == 'Break' for x in self.q): 
            crs.append('Break')
        for x in self.q:
            if x['course'] not in crs: 
                crs.append(x['course'])
                
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
                rem_dur = b['duration'] - b.get('worked', 0)
                if rem_dur < 0: rem_dur = 0
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
                    ds = item[0]
                    dd = item[1]
                    dtype = item[2] if len(item) > 2 else "Manual"
                    
                    ww = (ds - w_drwn) * scls
                    if ww > 0:
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(QBrush(col))
                        p.drawRoundedRect(int(cx), int(cy), int(max(ww,2)), int(rh-15), 4, 4)
                        cx += ww
                    
                    gw = dd * scls
                    if gw > 0:
                        gap_col = QColor("#f1c40f")
                        if dtype == "App": gap_col = QColor("#ff8c00")
                        elif dtype == "Camera": gap_col = QColor("#e74c3c")
                        elif dtype == "CameraError": gap_col = QColor("#800080")
                        
                        p.setPen(QPen(gap_col, 2))
                        p.drawLine(int(cx), int(cy + (rh-15)/2), int(cx + gw), int(cy + (rh-15)/2))
                        p.drawLine(int(cx), int(cy), int(cx), int(cy + rh - 15))
                        p.drawLine(int(cx + gw), int(cy), int(cx + gw), int(cy + rh - 15))
                        
                        if dd >= 5:
                            p.setFont(QFont("Arial", 7, QFont.Weight.Bold))
                            p.drawText(QRectF(int(cx), int(cy - 12), int(gw), 12), Qt.AlignmentFlag.AlignCenter, f"{dd:.1f}m")
                        
                        cx += gw
                    w_drwn = ds
                
                if self.sys_st in ["Paused", "Attention Lost - Paused"] and self.sys_ps:
                    ww = (b.get('worked', 0) - w_drwn) * scls
                    if ww > 0:
                        p.setBrush(QBrush(col))
                        p.setPen(Qt.PenStyle.NoPen)
                        p.drawRoundedRect(int(cx), int(cy), int(max(ww,2)), int(rh-15), 4, 4)
                        cx += ww
                        w_drwn = b.get('worked', 0)
                    active_gap = (datetime.now() - self.sys_ps).total_seconds() / 60.0
                    rw = active_gap * scls
                    if rw > 0:
                        d_col = QColor(255, 255, 0)
                        p.setPen(QPen(d_col, 2, Qt.PenStyle.DashLine))
                        mid_y = int(cy + (rh-15)/2)
                        p.drawLine(int(cx), mid_y, int(cx + rw), mid_y)
                        p.setPen(QPen(d_col, 2))
                        p.drawLine(int(cx), int(cy), int(cx), int(cy+rh-15))
                        p.drawLine(int(cx+rw), int(cy), int(cx+rw), int(cy+rh-15))
                        cx += rw
                
                rem_w = b['duration'] - w_drwn
                if rem_w > 0:
                    pw = rem_w * scls
                    p.setBrush(QBrush(col))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawRoundedRect(int(cx), int(cy), int(max(pw,2)), int(rh-15), 4, 4)
                    cx += pw
                
                self.hitboxes.append((QRect(int(start_cx), int(cy), int(max(cx-start_cx, 2)), int(rh-15)), b))
            else:
                rem_dur = b['duration'] - b.get('worked', 0)
                if rem_dur <= 0: continue
                    
                start_cx = cx
                col = get_color(b['course'])
                col.setAlpha(180)
                ridx = crs.index(b['course'])
                cy = ridx * rh + 10
                
                pw = rem_dur * scls
                p.setBrush(QBrush(col))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(int(cx), int(cy), int(max(pw,2)), int(rh-15), 4, 4)
                cx += pw
                
                self.hitboxes.append((QRect(int(start_cx), int(cy), int(max(cx-start_cx, 2)), int(rh-15)), b))
            
        p.setPen(QPen(Qt.GlobalColor.white))
        p.drawText(int(cx)-35, len(crs)*rh + 20, (start_time + timedelta(minutes=t_mins)).strftime('%H:%M'))