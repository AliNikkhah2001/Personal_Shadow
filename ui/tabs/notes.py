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

class MarkdownEditorWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        sp = QSplitter(Qt.Orientation.Horizontal)
        
        self.ed = QTextEdit()
        self.ed.setObjectName("Panel")
        self.ed.textChanged.connect(self.up)
        
        self.pr = QTextEdit()
        self.pr.setObjectName("Panel")
        self.pr.setReadOnly(True)
        
        sp.addWidget(self.ed)
        sp.addWidget(self.pr)
        
        tb = QHBoxLayout()
        self.ti = QLineEdit()
        sb = QPushButton("Save")
        sb.clicked.connect(self.sn)
        
        tb.addWidget(self.ti)
        tb.addWidget(sb)
        
        lay.addLayout(tb)
        lay.addWidget(sp)
        
    def up(self): 
        self.pr.setHtml(f"<div style='color: white; font-family: {config.get('font_family')};'>{markdown.markdown(self.ed.toPlainText(), extensions=['fenced_code', 'tables'])}</div>")
        
    def sn(self):
        if self.ti.text() and self.ed.toPlainText(): 
            db.c.execute("INSERT INTO notes (title, content, timestamp) VALUES (?, ?, ?)", (self.ti.text(), self.ed.toPlainText(), datetime.now().isoformat()))
            db.conn.commit()
