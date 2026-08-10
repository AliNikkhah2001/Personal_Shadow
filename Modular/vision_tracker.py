import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

import cv2
import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core_sys import config


# Global thread-safe frame container for the HTTP stream
class StreamState:
    frame = None
    lock = threading.Lock()

class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/video_feed':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with StreamState.lock:
                        if StreamState.frame is None:
                            time.sleep(0.1)
                            continue
                        _, jpeg = cv2.imencode('.jpg', StreamState.frame, [cv2.IMWRITE_JPEG_QUALITY, 70])

                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(jpeg))
                    self.end_headers()
                    self.wfile.write(jpeg.tobytes())
                    self.wfile.write(b'\r\n')
                    time.sleep(0.06) # Throttle to roughly 15 FPS
            except Exception:
                pass
        else:
            self.send_error(404)
            self.end_headers()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

class VisionTracker(QObject):
    attention_status = pyqtSignal(bool)
    att_lost = pyqtSignal()
    att_restored = pyqtSignal()
    err_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cap = None
        self.fc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml')
        self.ec = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        self.bg_sub = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=50, detectShadows=False)

        self.tmr = QTimer()
        self.tmr.timeout.connect(self.process)

        self.is_rec = False
        self.writer = None
        self.v_path = ""
        self.last_frame_time = 0
        self.lf = 0
        self.has_valid_feed = False
        self.ui_active = False

        # Start the background HTTP streaming server on port 5050
        try:
            self.server = ThreadedHTTPServer(('127.0.0.1', 5050), StreamingHandler)
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
        except OSError:
            print("Port 5050 already in use, stream server might already be running.")

    def upd_settings(self):
        if self.tmr.isActive():
            self.tmr.setInterval(config.get("vision_sample_interval", 30))

    def start(self):
        if config.get("quiet_mode", False): return
        if not self.cap or not self.cap.isOpened():
            for i in [0, 1]:
                if sys.platform == "win32": tc = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                else: tc = cv2.VideoCapture(i)
                if tc.isOpened():
                    self.cap = tc
                    break
        if self.cap and self.cap.isOpened():
            self.has_valid_feed = True
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
        with StreamState.lock:
            StreamState.frame = None

    def start_rec(self, path):
        self.is_rec = True
        self.v_path = path
        self.last_frame_time = time.time()
        os.makedirs("timelapses", exist_ok=True)
        self.writer = cv2.VideoWriter(self.v_path, cv2.VideoWriter_fourcc(*'MJPG'), 1.0, (640, 480))

    def stop_rec(self):
        self.is_rec = False
        if self.writer:
            self.writer.release()
            self.writer = None

    def process(self):
        if not self.cap or not self.cap.isOpened():
            self.has_valid_feed = False
            self.err_msg.emit("Camera Failed!")
            self.att_lost.emit()
            return

        ret, frm = self.cap.read()
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

        # RECORDING FIX: 1 frame per second to capture short test sessions perfectly
        if self.is_rec and self.writer:
            curr = time.time()
            if curr - self.last_frame_time >= 1.0:
                self.writer.write(cv2.resize(frm, (640, 480)))
                self.last_frame_time = curr

        mode = str(config.get("vision_mode", "Strict (Face & Eyes)"))
        scale = float(config.get("face_scale_factor", 1.2))
        min_n = int(config.get("face_min_neighbors", 8))
        min_s = int(config.get("face_min_size", 120))

        att = False
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

        fps = max(1, 1000 // int(config.get("vision_sample_interval", 30)))
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

        self.attention_status.emit(att)

        # Route 1: Local HTTP Streaming (Fastest)
        with StreamState.lock:
            StreamState.frame = cv2.resize(frm, (480, 360))
