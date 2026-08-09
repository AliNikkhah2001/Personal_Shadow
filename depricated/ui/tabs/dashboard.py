from datetime import datetime, timedelta
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer
from core.config import config
from core.signals import bus
from ui.charts import CircularProgress, AnalogClock, DashboardGoalsWidget, DualFocusCalendar, ActivityHeatmap

class DashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        
        top_l = QHBoxLayout()
        self.dl_lbl = QLabel("")
        self.dl_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff9f0a; background-color: rgba(0,0,0,100); padding: 8px 16px; border-radius: 8px;")
        
        self.cfg_btn = QPushButton("⚙ Configure Layout")
        self.cfg_btn.setStyleSheet("background-color: rgba(255,255,255,10); color: white; border-radius: 8px; padding: 8px 16px;")
        self.cfg_btn.clicked.connect(self.open_config)
        
        top_l.addWidget(self.dl_lbl)
        top_l.addStretch()
        top_l.addWidget(self.cfg_btn)
        lay.addLayout(top_l)
        
        self.grid = QGridLayout()
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(2, 1)
        self.grid.setRowStretch(0, 1)
        self.grid.setRowStretch(1, 1)
        
        self.blocks = {}
        
        # Panel 1: Clock
        self.gp = QFrame()
        self.gp.setObjectName("GlassPanel")
        self.gp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.gp.setMinimumSize(300, 250)
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
        self.blocks["Clock"] = self.gp
        
        # Panel 2: Unified Goals
        self.dgw = QFrame()
        self.dgw.setObjectName("GlassPanel")
        self.dgw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.dgw.setMinimumSize(300, 250)
        dgw_lay = QVBoxLayout(self.dgw)
        self.goals_widget = DashboardGoalsWidget()
        dgw_lay.addWidget(self.goals_widget)
        self.blocks["Goals"] = self.dgw
        
        # Panel 3: Dual Calendar
        self.cp = QFrame()
        self.cp.setObjectName("GlassPanel")
        self.cp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.cp.setMinimumSize(300, 250)
        cl = QVBoxLayout(self.cp)
        cl.addWidget(QLabel("Deep Work Calendar", styleSheet="font-weight:bold; color:white; font-size: 16px; background:transparent;"))
        self.cal = DualFocusCalendar()
        cl.addWidget(self.cal)
        self.blocks["Calendar"] = self.cp
        
        # Panel 4: Heatmap
        self.hp = QFrame()
        self.hp.setObjectName("GlassPanel")
        self.hp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hp.setMinimumSize(400, 200)
        hl = QVBoxLayout(self.hp)
        hl.addWidget(QLabel("Deep Work Intensity", styleSheet="font-weight:bold; color:white; font-size: 16px; background:transparent;"))
        self.hm = ActivityHeatmap()
        hl.addWidget(self.hm)
        self.blocks["Heatmap"] = self.hp
        
        self.apply_layout()
        lay.addLayout(self.grid)
        
        self.ql = QLabel("Fetching...")
        self.ql.setObjectName("QuoteText")
        self.ql.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addStretch()
        lay.addWidget(self.ql)
        
        self.tmr = QTimer(self)
        self.tmr.timeout.connect(self.upd_clk)
        self.tmr.start(1000)
        
        bus.timer_tick.connect(self.upd_p)
        bus.settings_changed.connect(self.app_c)
        self.app_c()

    def open_config(self):
        dlg = DashboardLayoutConfigDialog(self)
        if dlg.exec():
            self.apply_layout()

    def apply_layout(self):
        def_layout = {
            "Clock": {"row": 0, "col": 0, "rspan": 1, "cspan": 1, "visible": True},
            "Goals": {"row": 0, "col": 1, "rspan": 1, "cspan": 1, "visible": True},
            "Calendar": {"row": 0, "col": 2, "rspan": 1, "cspan": 1, "visible": True},
            "Heatmap": {"row": 1, "col": 0, "rspan": 1, "cspan": 3, "visible": True}
        }
        active_layout = config.get("dashboard_layout", def_layout)
        for i in reversed(range(self.grid.count())): 
            self.grid.itemAt(i).widget().setParent(None)
        for name, widget in self.blocks.items():
            opts = active_layout.get(name, def_layout[name])
            if opts.get("visible", True):
                self.grid.addWidget(widget, opts["row"], opts["col"], opts["rspan"], opts["cspan"])
                widget.show()
            else:
                widget.hide()

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
                days = rem.days; hours, rem_sec = divmod(rem.seconds, 3600); mins, secs = divmod(rem_sec, 60)
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

class DashboardLayoutConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Dashboard Blocks")
        self.setFixedSize(500, 400)
        self.setStyleSheet("background-color: #0d0d12; color: white;")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Configure Visibility and Grid Positions:", styleSheet="font-weight:bold; font-size:16px;"))
        self.def_layout = {
            "Clock": {"row": 0, "col": 0, "rspan": 1, "cspan": 1, "visible": True},
            "Goals": {"row": 0, "col": 1, "rspan": 1, "cspan": 1, "visible": True},
            "Calendar": {"row": 0, "col": 2, "rspan": 1, "cspan": 1, "visible": True},
            "Heatmap": {"row": 1, "col": 0, "rspan": 1, "cspan": 3, "visible": True}
        }
        self.active = config.get("dashboard_layout", self.def_layout)
        self.inputs = {}
        grid = QGridLayout()
        grid.addWidget(QLabel("Block"), 0, 0); grid.addWidget(QLabel("Visible"), 0, 1); grid.addWidget(QLabel("Row"), 0, 2); grid.addWidget(QLabel("Col"), 0, 3); grid.addWidget(QLabel("ColSpan"), 0, 4)
        r = 1
        for name in ["Clock", "Goals", "Calendar", "Heatmap"]:
            opts = self.active.get(name, self.def_layout[name])
            lbl = QLabel(name); vis = QCheckBox(); vis.setChecked(opts.get("visible", True))
            row_s = QSpinBox(); row_s.setRange(0, 5); row_s.setValue(opts.get("row", 0))
            col_s = QSpinBox(); col_s.setRange(0, 5); col_s.setValue(opts.get("col", 0))
            span_s = QSpinBox(); span_s.setRange(1, 4); span_s.setValue(opts.get("cspan", 1))
            grid.addWidget(lbl, r, 0); grid.addWidget(vis, r, 1); grid.addWidget(row_s, r, 2); grid.addWidget(col_s, r, 3); grid.addWidget(span_s, r, 4)
            self.inputs[name] = {"vis": vis, "row": row_s, "col": col_s, "span": span_s}; r += 1
        lay.addLayout(grid)
        btn = QPushButton("Save Layout")
        btn.setStyleSheet("background-color: #0a84ff; padding: 10px; border-radius: 8px; font-weight: bold;")
        btn.clicked.connect(self.save_and_close)
        lay.addStretch(); lay.addWidget(btn)

    def save_and_close(self):
        new_cfg = {}
        for name, data in self.inputs.items():
            new_cfg[name] = {"visible": data["vis"].isChecked(), "row": data["row"].value(), "col": data["col"].value(), "rspan": 1, "cspan": data["span"].value()}
        config.set("dashboard_layout", new_cfg)
        self.accept()