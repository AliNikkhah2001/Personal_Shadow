import cv2
import time
import os
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QImage

from core.config import config
from core.signals import bus

class VisionTracker(QObject):
    frame_ready = pyqtSignal(QImage)
    att_lost = pyqtSignal()
    att_restored = pyqtSignal()
    err_msg = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.tmr = QTimer()
        self.tmr.timeout.connect(self.process)
        self.lf = 0
        self.cap = None
        self.fc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml')
        self.ec = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        self.bg_sub = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=50, detectShadows=False)
        self.is_rec = False
        self.writer = None
        self.v_path = ""
        self.last_frame_time = 0
        
        # FIX: The missing hardware feed lock that caused the AttributeError
        self.has_valid_feed = False 

    def upd_settings(self):
        if self.tmr.isActive(): 
            self.tmr.setInterval(config.get("vision_sample_interval", 30))

    def start(self): 
        if self.cap is None or not self.cap.isOpened():
            for i in [0, 1]:
                tc = cv2.VideoCapture(i)
                if tc.isOpened(): 
                    self.cap = tc
                    break
        if self.cap and self.cap.isOpened():
            self.tmr.start(config.get("vision_sample_interval", 30))
        else:
            self.has_valid_feed = False
            self.err_msg.emit("Camera Failed to Initialize")

    def stop(self):
        self.stop_rec()
        self.tmr.stop()
        if self.cap: 
            self.cap.release()
            self.cap = None
        self.has_valid_feed = False
    
    def start_rec(self, path): 
        self.is_rec = True
        self.v_path = path
        self.last_frame_time = time.time()
        os.makedirs("timelapses", exist_ok=True)
        # 1 frame every 24 sec -> rendered at 15fps -> 1 hour = 10 sec video
        self.writer = cv2.VideoWriter(self.v_path, cv2.VideoWriter_fourcc(*'MJPG'), 15.0, (640, 480))
        
    def stop_rec(self): 
        self.is_rec = False
        if self.writer: 
            self.writer.release()
            self.writer = None

    def process(self):
        att = False
        mode = str(config.get("vision_mode", "Strict (Face & Eyes)"))
        scale = config.get("face_scale_factor", 1.2)
        min_n = config.get("face_min_neighbors", 8)
        min_s = config.get("face_min_size", 120)
        
        if not self.cap or not self.cap.isOpened():
            self.has_valid_feed = False
            self.err_msg.emit("Camera Failed!")
            self.att_lost.emit()
            return
            
        ret, frm = self.cap.read()
        
        # Hardware drop or pitch-black privacy shutter detection
        if not ret or frm is None:
            self.has_valid_feed = False
            self.err_msg.emit("Feed dropped!")
            self.att_lost.emit()
            return
            
        if np.mean(frm) < 2.0:
            self.has_valid_feed = False
            self.err_msg.emit("Camera Feed Blank (Off/Covered)!")
            self.att_lost.emit()
            return
            
        self.has_valid_feed = True
        gray = cv2.equalizeHist(cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY))
        
        if self.is_rec and self.writer:
            curr = time.time()
            if curr - self.last_frame_time >= 24.0:
                frm_resized = cv2.resize(frm, (640, 480))
                self.writer.write(frm_resized)
                self.last_frame_time = curr
            
        if "Presence" in mode:
            fg = self.bg_sub.apply(cv2.GaussianBlur(gray, (21, 21), 0))
            _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
            if cv2.countNonZero(fg) > 3000 or len(self.fc.detectMultiScale(gray, scale, min_n, minSize=(min_s,min_s))) > 0: 
                att = True
        else:
            faces = self.fc.detectMultiScale(gray, scale, min_n, minSize=(min_s,min_s))
            if len(faces) > 0:
                (x,y,w,h) = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)[0]
                cv2.rectangle(frm, (x,y), (x+w,y+h), (0,255,0), 2)
                if "Visible" in mode: 
                    att = True
                else:
                    eyes = self.ec.detectMultiScale(gray[y:y+int(h/2), x:x+w], 1.1, 10, minSize=(20,20))
                    if len(eyes) > 0: 
                        att = True
        
        rgb = cv2.cvtColor(frm, cv2.COLOR_BGR2RGB)
        self.frame_ready.emit(QImage(rgb.data, rgb.shape[1], rgb.shape[0], QImage.Format.Format_RGB888))

        fps = max(1, 1000 // config.get("vision_sample_interval", 30))
        delay_frames = int(config.get("dist_delay", 3)) * fps
        was_lost = self.lf >= delay_frames
        
        if not att: 
            self.lf = min(self.lf + 1, delay_frames)
        else: 
            self.lf = max(self.lf - max(1, fps // 2), 0)
            
        is_lost = self.lf >= delay_frames
        if is_lost and not was_lost: 
            self.att_lost.emit()
        elif not is_lost and was_lost: 
            self.att_restored.emit()