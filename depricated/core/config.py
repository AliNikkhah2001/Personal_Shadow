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

class ConfigManager:
    def __init__(self, fn="config.json"):
        self.fn = fn
        self.defaults = {
            "font_family": "Helvetica Neue", "custom_font_path": "", "font_size": 16, 
            "clock_style": "Analog Classic", "clock_case": "Round", "clock_bezel": "Plain", 
            "clock_indices": "Baton", "clock_ticks": "Standard", "clock_hands": "Classic", "clock_comp": "None",
            "dist_delay": 3, "vision_mode": "Strict (Face & Eyes)", "bg_image_path": "", 
            "quotes_path": "data/quotes.json", 
            "panel_opacity": 180, "face_scale_factor": 1.2, "face_min_neighbors": 8, "face_min_size": 120, 
            "vision_sample_interval": 30, "force_close_apps_mins": 5, "sound_app_dist": "Ping", 
            "sound_cam_dist": "Basso", "sound_cam_err": "Hero", "beep_freq": 3,
            "loop_1m": 2, "loop_5m": 5, "loop_15m": 10, "loop_30m": 20, "loop_60m": 30,
            "speech_dist": "You have been distracted. Please return to work.",
            "speech_comp": "Fantastic job! Your deep work session is complete.",
            "deadline_name": "Goal",
            "deadline_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
        }
        try:
            with open(fn, 'r') as f:
                self.cfg = json.load(f)
        except:
            self.cfg = self.defaults.copy()
            
        for k, v in self.defaults.items():
            if self.cfg.get(k) is None:
                self.cfg[k] = v
                
    def get(self, k, d=None): 
        return self.cfg.get(k, d if d is not None else self.defaults.get(k))
        
    def set(self, k, v):
        self.cfg[k] = v
        with open(self.fn, 'w') as f:
            json.dump(self.cfg, f)

config = ConfigManager()
