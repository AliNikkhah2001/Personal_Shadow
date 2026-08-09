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

class SignalBus(QObject):
    db_updated = pyqtSignal()
    timer_tick = pyqtSignal(str, str, int)
    settings_changed = pyqtSignal()
    course_added = pyqtSignal()
    attention_alert = pyqtSignal(str)
    progress_update = pyqtSignal(float, float)
    active_color_changed = pyqtSignal(QColor)

bus = SignalBus()
