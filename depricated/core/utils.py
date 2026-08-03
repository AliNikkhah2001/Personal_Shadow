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

def get_color(c_name): 
    if c_name == "Break": 
        return QColor(100,100,100,200)
    if not c_name or c_name == "None": 
        return QColor("#40c463")
    return QColor(f"#{hashlib.md5(c_name.encode()).hexdigest()[:6]}")

def render_latex(t, fs=14, c="white"):
    f = plt.figure(figsize=(0.01, 0.01))
    f.text(0,0, f"${t}$", fontsize=fs, color=c, ha='left', va='bottom')
    cvs = FigureCanvasAgg(f)
    cvs.draw()
    img = QImage(cvs.buffer_rgba(), cvs.get_width_height()[0], cvs.get_width_height()[1], QImage.Format.Format_RGBA8888)
    plt.close(f)
    return img

def get_active_app():
    try: 
        res = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'], capture_output=True, text=True)
        return res.stdout.strip()
    except: 
        return ""

def trigger_mac_notification(title, text):
    try:
        safe_text = text.replace("'", "").replace('"', '')
        subprocess.run(["osascript", "-e", f'display notification "{safe_text}" with title "{title}"'])
    except: 
        pass

def speak_text(text):
    try: 
        subprocess.Popen(["say", text])
    except: 
        pass

def max_volume():
    try: 
        subprocess.Popen(["osascript", "-e", "set volume output volume 100"])
    except: 
        pass
