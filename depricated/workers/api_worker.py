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

class ApiWorker(QThread):
    quote_fetched = pyqtSignal(str)
    image_fetched = pyqtSignal(bytes)
    
    def run(self):
        qp = config.get("quotes_path", "data/quotes.json")
        quotes = [{"quote": "Keep pushing forward.", "author": "System"}]
        if qp and os.path.exists(qp):
            try:
                with open(qp, 'r') as f:
                    quotes = json.load(f)
            except:
                pass
                
        q = random.choice(quotes)
        self.quote_fetched.emit(f'"{q.get("quote", "")}"\n— {q.get("author", "")}')

        bp = config.get("bg_image_path", "")
        if bp and os.path.exists(bp):
            return
            
        try:
            ir = requests.get("https://picsum.photos/1920/1080?random=1", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5, allow_redirects=True)
            if ir.status_code == 200: 
                self.image_fetched.emit(ir.content)
        except: 
            pass
