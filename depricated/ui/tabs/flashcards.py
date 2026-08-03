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

class FlashcardWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        
        af = QFrame()
        af.setObjectName("Panel")
        al = QHBoxLayout(af)
        self.fi = QLineEdit()
        self.fi.setPlaceholderText("Front...")
        self.bi = QLineEdit()
        self.bi.setPlaceholderText("Back...")
        
        self.cc = QComboBox()
        bus.course_added.connect(self.lc)
        self.lc()
        
        ab = QPushButton("Add")
        ab.clicked.connect(self.ac)
        
        al.addWidget(self.cc)
        al.addWidget(self.fi)
        al.addWidget(self.bi)
        al.addWidget(ab)
        
        self.cf = QFrame()
        self.cf.setObjectName("GlassPanel")
        self.cf.setFixedSize(600, 300)
        cl = QVBoxLayout(self.cf)
        self.ft = QLabel("Next...")
        self.ft.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.ft)
        
        self.fa = QPropertyAnimation(self.cf, b"maximumWidth")
        self.fa.setDuration(150)
        self.fa.finished.connect(self.mf)
        
        self.cd = None
        self.sf = True
        
        ct = QHBoxLayout()
        fb = QPushButton("Flip")
        fb.clicked.connect(self.fl)
        nb = QPushButton("Next")
        nb.clicked.connect(self.ln)
        
        ct.addStretch()
        ct.addWidget(fb)
        ct.addWidget(nb)
        ct.addStretch()
        
        lay.addWidget(af)
        lay.addStretch()
        lay.addWidget(self.cf, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addLayout(ct)
        lay.addStretch()
        
    def lc(self): 
        self.cc.clear()
        self.cc.addItem("General")
        db.c.execute("SELECT name FROM courses")
        for r in db.c.fetchall():
            self.cc.addItem(r[0])
            
    def ac(self):
        if self.fi.text() and self.bi.text():
            try: 
                db.c.execute("INSERT INTO flashcards (course, front, back) VALUES (?, ?, ?)", (self.cc.currentText(), self.fi.text().strip(), self.bi.text().strip()))
            except sqlite3.OperationalError: 
                db.c.execute("INSERT INTO flashcards (front, back) VALUES (?, ?)", (self.fi.text().strip(), self.bi.text().strip()))
            db.conn.commit()
            self.fi.clear()
            self.bi.clear()
            bus.db_updated.emit()
            
    def fl(self):
        if not self.cd: return
        self.fa.setStartValue(600)
        self.fa.setEndValue(0)
        self.fa.start()
        
    def mf(self):
        self.sf = not self.sf
        self.ft.setText(self.cd["front"] if self.sf else self.cd["back"])
        self.fa.disconnect()
        self.fa.finished.connect(lambda: None)
        self.fa.setStartValue(0)
        self.fa.setEndValue(600)
        self.fa.start()
        self.fa.finished.connect(self.ra)
        
    def ra(self): 
        self.fa.disconnect()
        self.fa.finished.connect(self.mf)
        
    def ln(self):
        db.c.execute("SELECT front, back FROM flashcards ORDER BY RANDOM() LIMIT 1")
        r = db.c.fetchone()
        if r: 
            self.cd = {"front": r[0], "back": r[1]}
            self.sf = True
            self.ft.setText(self.cd["front"])
        else: 
            self.ft.setText("Empty.")
