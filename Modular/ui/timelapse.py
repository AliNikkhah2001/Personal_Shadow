"""Timelapse dialog for reviewing recorded study sessions."""

import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class TimelapseDialog(QDialog):
    """Dialog for reviewing recorded timelapse sessions."""

    def __init__(self, path, mins, dists, b_data=None):
        super().__init__()
        self.setWindowTitle("Session Debrief")
        self.setFixedSize(800, 600)
        self.setStyleSheet("background-color: #0f0f11; color: white;")

        lay = QVBoxLayout(self)
        self.lbl = QLabel()
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl)

        h = QHBoxLayout()
        h.addWidget(
            QLabel(
                f"<b>Session Stats:</b> {mins} Mins Studied | {dists} Distractions",
                styleSheet="font-size: 18px; color: #40c463;",
            )
        )

        btn = QPushButton("Close")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.close)

        h.addStretch()
        h.addWidget(btn)
        lay.addLayout(h)

        self.cap = cv2.VideoCapture(path)
        self.tmr = QTimer()
        self.tmr.timeout.connect(self._next_frame)
        self.tmr.start(33)

    def _next_frame(self):
        ret, frm = self.cap.read()
        if ret:
            rgb = cv2.cvtColor(frm, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            self.lbl.setPixmap(
                QPixmap.fromImage(QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)).scaled(
                    760, 480, Qt.AspectRatioMode.KeepAspectRatio
                )
            )
        else:
            self.tmr.stop()

    def closeEvent(self, e):
        self.tmr.stop()
        if self.cap:
            self.cap.release()
        super().closeEvent(e)
