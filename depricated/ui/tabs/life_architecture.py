import json
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from core.database import db
from core.signals import bus

class GoalDialog(QDialog):
    def __init__(self, parent=None, goal_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Goal" if goal_data else "Add New Goal")
        self.setFixedSize(400, 300)
        self.setStyleSheet("background-color: #0f0f11; color: white;")
        self.goal_data = goal_data
        
        lay = QFormLayout(self)
        
        self.title_in = QLineEdit()
        self.title_in.setText(goal_data[1] if goal_data else "")
        lay.addRow("Goal Title:", self.title_in)
        
        self.cat_in = QComboBox()
        self.cat_in.addItems(["Career", "Education", "Health", "Finance", "Project"])
        self.cat_in.setCurrentText(goal_data[2] if goal_data else "Education")
        lay.addRow("Category:", self.cat_in)
        
        self.tgt_in = QDoubleSpinBox()
        self.tgt_in.setRange(0, 10000)
        self.tgt_in.setValue(goal_data[3] if goal_data else 10.0)
        lay.addRow("Target Hours:", self.tgt_in)
        
        self.dl_in = QDateTimeEdit()
        self.dl_in.setCalendarPopup(True)
        self.dl_in.setDisplayFormat("yyyy-MM-dd HH:mm")
        if goal_data and goal_data[4]:
            self.dl_in.setDateTime(QDateTime.fromString(goal_data[4], "yyyy-MM-dd HH:mm:ss"))
        else:
            self.dl_in.setDateTime(QDateTime.currentDateTime().addDays(30))
        lay.addRow("Deadline:", self.dl_in)
        
        btn = QPushButton("Save Goal")
        btn.setStyleSheet("background-color: #0a84ff; padding: 10px; border-radius: 8px; font-weight: bold;")
        btn.clicked.connect(self.accept)
        lay.addRow(btn)

    def get_data(self):
        return {
            "title": self.title_in.text().strip(),
            "category": self.cat_in.currentText(),
            "target": self.tgt_in.value(),
            "deadline": self.dl_in.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        }

class LifeArchitectureWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("Life Architecture & Integrated Goals", styleSheet="font-size: 20px; font-weight: bold; background:transparent;"))
        add_btn = QPushButton("+ Add Goal")
        add_btn.setStyleSheet("background-color: #30a14e; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        add_btn.clicked.connect(self.add_goal)
        header.addStretch()
        header.addWidget(add_btn)
        lay.addLayout(header)
        
        self.tree = QTreeWidget()
        self.tree.setObjectName("Panel")
        self.tree.setHeaderLabels(["Goal Title", "Category", "Target (Hrs)", "Logged (Hrs)", "Progress", "Deadline"])
        self.tree.setColumnWidth(0, 250)
        self.tree.setAlternatingRowColors(True)
        self.tree.setStyleSheet("""
            QTreeWidget { background: rgba(30, 32, 42, 180); color: white; border-radius: 12px; font-size: 14px; } 
            QHeaderView::section { background-color: rgba(20,20,25,200); padding: 8px; font-weight: bold; border-bottom: 1px solid #444; }
            QTreeWidget::item { padding: 8px; }
            QTreeWidget::item:alternate { background-color: rgba(255,255,255,5); }
        """)
        
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_menu)
        
        lay.addWidget(self.tree)
        self.upd()
        bus.db_updated.connect(self.upd)

    def upd(self):
        self.tree.clear()
        db.c.execute("SELECT title, category, target_hours, deadline, id FROM cascading_goals")
        goals = db.c.fetchall()
        
        db.c.execute("SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY course")
        logged_map = {r[0]: (r[1] or 0)/60.0 for r in db.c.fetchall()}
        
        for g in goals:
            title, cat, tgt, dl, gid = g
            logged = logged_map.get(title, 0.0)
            pct = min(100, int((logged/tgt)*100)) if tgt > 0 else 0
            
            item = QTreeWidgetItem([title, cat, f"{tgt:.1f}", f"{logged:.1f}", f"{pct}%", str(dl)])
            item.setData(0, Qt.ItemDataRole.UserRole, gid)
            
            if pct >= 100: item.setForeground(4, QColor("#30a14e"))
            elif pct > 50: item.setForeground(4, QColor("#f1c40f"))
            else: item.setForeground(4, QColor("#ff453a"))
            
            self.tree.addTopLevelItem(item)

    def add_goal(self):
        dlg = GoalDialog(self)
        if dlg.exec():
            d = dlg.get_data()
            db.c.execute("INSERT INTO cascading_goals (title, category, target_hours, deadline) VALUES (?,?,?,?)", (d['title'], d['category'], d['target'], d['deadline']))
            db.conn.commit()
            bus.db_updated.emit()
            bus.course_added.emit()

    def open_menu(self, position):
        item = self.tree.itemAt(position)
        if not item: return
        
        gid = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu()
        menu.setStyleSheet("background-color: #1a1a24; color: white;")
        
        edit_act = menu.addAction("Edit Goal")
        del_act = menu.addAction("Delete Goal")
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        
        if action == edit_act:
            db.c.execute("SELECT id, title, category, target_hours, deadline FROM cascading_goals WHERE id=?", (gid,))
            gdata = db.c.fetchone()
            dlg = GoalDialog(self, gdata)
            if dlg.exec():
                d = dlg.get_data()
                db.c.execute("UPDATE cascading_goals SET title=?, category=?, target_hours=?, deadline=? WHERE id=?", (d['title'], d['category'], d['target'], d['deadline'], gid))
                db.conn.commit()
                bus.db_updated.emit()
                bus.course_added.emit()
                
        elif action == del_act:
            reply = QMessageBox.question(self, "Confirm Delete", f"Delete goal '{item.text(0)}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                db.c.execute("DELETE FROM cascading_goals WHERE id=?", (gid,))
                db.conn.commit()
                bus.db_updated.emit()