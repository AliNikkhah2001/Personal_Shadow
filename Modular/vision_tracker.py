import cv2
import base64
import sys
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage
from core_sys import config

class VisionTracker(QObject):
    def __init__(self):
        super().__init__()
        self.cap = None
        self.fc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml')

    def start(self):
        if config.get("quiet_mode", False): return
        if not self.cap or not self.cap.isOpened():
            for i in [0, 1]:
                if sys.platform == "win32": tc = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                else: tc = cv2.VideoCapture(i)
                if tc.isOpened():
                    self.cap = tc
                    break

    def stop(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def process_frame(self):
        if not self.cap or not self.cap.isOpened(): return False, None
        ret, frm = self.cap.read()
        if not ret: return False, None
        
        gray = cv2.equalizeHist(cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY))
        faces = self.fc.detectMultiScale(gray, config.get("face_scale_factor", 1.2), config.get("face_min_neighbors", 8), minSize=(100,100))
        
        att = False
        if len(faces) > 0:
            (x,y,w,h) = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)[0]
            cv2.rectangle(frm, (x,y), (x+w,y+h), (0,255,0), 2)
            att = True
            
        _, buffer = cv2.imencode('.jpg', cv2.resize(frm, (480, 360)), [cv2.IMWRITE_JPEG_QUALITY, 60])
        b64 = base64.b64encode(buffer).decode('utf-8')
        return att, b64