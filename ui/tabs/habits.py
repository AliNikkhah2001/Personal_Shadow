from PyQt6.QtWidgets import *
from core.database import db
from ui.components import GlassPanel
from datetime import datetime, timedelta

class HabitsWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Habit Matrix (7-Day Rolling)", styleSheet="font-size: 22px; font-weight: bold;"))
        
        self.table = QTableWidget(5, 8)
        headers = ["Habit"] + [(datetime.now() - timedelta(days=i)).strftime("%a %d") for i in range(6, -1, -1)]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setStyleSheet("background: transparent; color: white; gridline-color: rgba(255,255,255,20);")
        self.table.horizontalHeader().setStyleSheet("background-color: transparent;")
        
        habits = ["Gym / Running", "Reading", "Fast Food", "Coding", "Smoking"]
        for row, h in enumerate(habits):
            self.table.setItem(row, 0, QTableWidgetItem(h))
            for col in range(1, 8):
                cb = QCheckBox()
                cb.setStyleSheet("margin-left: 20px;")
                self.table.setCellWidget(row, col, cb)
                
        panel = GlassPanel()
        panel.lay.addWidget(self.table)
        lay.addWidget(panel)
