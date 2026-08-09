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
from core.database import db
from core.signals import bus
from core.utils import render_latex

class QuizEngineWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        sp = QSplitter(Qt.Orientation.Horizontal)
        
        lf = QFrame()
        lf.setObjectName("Panel")
        ll = QVBoxLayout(lf)
        ll.addWidget(QLabel("Saved Quizzes"))
        self.ql = QListWidget()
        self.ql.itemDoubleClicked.connect(self.lsq)
        ll.addWidget(self.ql)
        
        bl = QPushButton("Import JSON")
        bl.clicked.connect(self.iq)
        br = QPushButton("Review Starred")
        br.clicked.connect(self.rs)
        ll.addWidget(bl)
        ll.addWidget(br)
        sp.addWidget(lf)
        
        rf = QFrame()
        rf.setObjectName("Panel")
        rl = QVBoxLayout(rf)
        tb = QHBoxLayout()
        self.cc = QComboBox()
        self.lc()
        bus.course_added.connect(self.lc)
        
        sb = QPushButton("⭐ Star")
        sb.clicked.connect(self.sp)
        tb.addWidget(self.cc)
        tb.addWidget(sb)
        tb.addStretch()
        
        self.qd = QTextEdit()
        self.qd.setReadOnly(True)
        self.qd.setText("Select quiz.")
        
        self.oc = QFrame()
        self.ol = QVBoxLayout(self.oc)
        self.bg = QButtonGroup(self)
        
        ft = QHBoxLayout()
        self.pl = QLabel("")
        self.skb = QPushButton("Skip")
        self.skb.clicked.connect(self.skq)
        self.nb = QPushButton("Next")
        self.nb.clicked.connect(self.nq)
        self.skb.setEnabled(False)
        self.nb.setEnabled(False)
        
        ft.addWidget(self.pl)
        ft.addStretch()
        ft.addWidget(self.skb)
        ft.addWidget(self.nb)
        
        rl.addLayout(tb)
        rl.addWidget(self.qd)
        rl.addWidget(self.oc)
        rl.addStretch()
        rl.addLayout(ft)
        
        sp.addWidget(rf)
        lay.addWidget(sp)
        
        self.dat = []
        self.org = []
        self.wrg = []
        self.skp = []
        self.idx = 0
        self.sc = 0
        self.rql()
        
    def lc(self): 
        self.cc.clear()
        self.cc.addItem("Course...")
        db.c.execute("SELECT name FROM courses")
        for r in db.c.fetchall():
            self.cc.addItem(r[0])
            
    def rql(self): 
        self.ql.clear()
        db.c.execute("SELECT id, title FROM saved_quizzes")
        for i, t in db.c.fetchall():
            it = QListWidgetItem(t)
            it.setData(Qt.ItemDataRole.UserRole, i)
            self.ql.addItem(it)
            
    def iq(self):
        f, _ = QFileDialog.getOpenFileName(self, "Open JSON", "", "JSON Files (*.json)")
        if f: 
            db.c.execute("INSERT INTO saved_quizzes (title, course, filepath) VALUES (?,?,?)", (os.path.basename(f), self.cc.currentText(), f))
            db.conn.commit()
            self.rql()
            
    def lsq(self, item):
        db.c.execute("SELECT filepath FROM saved_quizzes WHERE id=?", (item.data(Qt.ItemDataRole.UserRole),))
        p = db.c.fetchone()[0]
        try: 
            self.org = json.load(open(p, 'r', encoding='utf-8'))
            self.sq_i(self.org)
        except: 
            pass
            
    def rs(self):
        c = self.cc.currentText()
        if c != "Course...":
            db.c.execute("SELECT data_json FROM starred_questions WHERE course=?", (c,))
            rows = db.c.fetchall()
            if rows: 
                sq = [json.loads(r[0]) for r in rows]
                self.org = sq
                self.sq_i(sq)
                
    def sq_i(self, d): 
        self.dat = d
        self.idx = 0
        self.sc = 0
        self.wrg = []
        self.skp = []
        self.nb.setEnabled(True)
        self.skb.setEnabled(True)
        self.shq()
        
    def shq(self):
        for i in reversed(range(self.ol.count())):
            w = self.ol.itemAt(i).widget()
            self.bg.removeButton(w)
            if w:
                w.deleteLater()
            
        q = self.dat[self.idx]
        self.pl.setText(f"Q {self.idx+1}/{len(self.dat)}")
        self.qd.clear()
        c = self.qd.textCursor()
        
        for i, p in enumerate(q.get("q", "").split('$')):
            if i%2==1: 
                self.qd.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl(f"l_{i}"), render_latex(p, config.get("font_size")))
                c.insertImage(f"l_{i}")
            else: 
                c.insertText(p)
                
        for i, o in enumerate(q.get("options", [])): 
            rb = QRadioButton(o)
            self.bg.addButton(rb, i)
            self.ol.addWidget(rb)
            
    def nq(self):
        b = self.bg.checkedButton()
        if not b: return 
        if b.text() == self.dat[self.idx].get("answer"): 
            self.sc += 1
        else: 
            self.wrg.append(self.dat[self.idx])
        self.adv()
        
    def skq(self): 
        self.skp.append(self.dat[self.idx])
        self.adv()
        
    def adv(self): 
        self.idx += 1
        if self.idx < len(self.dat): 
            self.shq()
        else: 
            self.fin()
            
    def fin(self):
        for i in reversed(range(self.ol.count())):
            w = self.ol.itemAt(i).widget()
            if w:
                w.deleteLater()
            
        self.qd.setText(f"Done!\nScore: {self.sc}/{len(self.dat)}\nMissed: {len(self.wrg)}\nSkipped: {len(self.skp)}")
        self.pl.setText("Ended")
        self.nb.setEnabled(False)
        self.skb.setEnabled(False)
        db.c.execute("INSERT INTO exams (course, score, total, date) VALUES (?,?,?,?)", (self.cc.currentText(), self.sc, len(self.dat), datetime.now().isoformat()))
        db.conn.commit()
        
        b1 = QPushButton("Redo All")
        b1.clicked.connect(lambda: self.sq_i(self.org))
        self.ol.addWidget(b1)
        if self.wrg or self.skp: 
            b2 = QPushButton("Redo Wrong/Skipped")
            b2.clicked.connect(lambda: self.sq_i(self.wrg + self.skp))
            self.ol.addWidget(b2)
            
    def sp(self):
        if self.dat and self.idx < len(self.dat): 
            db.c.execute("INSERT INTO starred_questions (course, question, data_json) VALUES (?,?,?)", (self.cc.currentText(), self.dat[self.idx].get("q"), json.dumps(self.dat[self.idx])))
            db.conn.commit()
