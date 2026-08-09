from PyQt6.QtWidgets import *
from core.database import db
from core.signals import bus
from core.utils import get_color
from ui.components import GlassPanel

class CourseProgressWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        
        hl = QHBoxLayout()
        hl.addWidget(QLabel("Course Goals & Progress", styleSheet="font-size: 22px; font-weight: bold;"))
        self.apply_btn = QPushButton("Apply Goals")
        self.apply_btn.setStyleSheet("background-color: #0a84ff; font-weight: bold; padding: 8px 16px; border-radius: 8px;")
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

    def upd(self):
        for i in reversed(range(self.vl.count())):
            w = self.vl.itemAt(i).widget()
            if w: w.deleteLater()
        
        self.spinboxes.clear()
        db.c.execute("SELECT name FROM courses")
        courses = [r[0] for r in db.c.fetchall()]
        db.c.execute("SELECT course, target_hours FROM course_targets")
        targets = {r[0]: r[1] for r in db.c.fetchall()}
        db.c.execute("SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY course")
        studied = {r[0]: (r[1] or 0)/60.0 for r in db.c.fetchall()}
        
        for c in courses:
            f = GlassPanel()
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
            f.lay.addLayout(hl)
            
            rem = max(0, t_hrs - s_hrs)
            pb = QProgressBar()
            pb.setMaximum(100)
            pct = min(int((s_hrs / t_hrs) * 100), 100) if t_hrs > 0 else 0
            pb.setValue(pct)
            pb.setFormat(f"{s_hrs:.1f} / {t_hrs:.1f} hrs ({pct}%) | Rem: {rem:.1f} hrs")
            pb.setStyleSheet(f"QProgressBar {{ background-color: rgba(255,255,255,10); border-radius: 8px; text-align: center; font-weight: bold; }} QProgressBar::chunk {{ background-color: {get_color(c).name()}; border-radius: 8px; }}")
            
            f.lay.addWidget(pb)
            self.vl.addWidget(f)
        self.vl.addStretch()

    def save_all(self):
        for c, sp in self.spinboxes.items():
            db.c.execute("INSERT OR REPLACE INTO course_targets (course, target_hours) VALUES (?, ?)", (c, sp.value()))
        db.conn.commit()
        self.upd()
