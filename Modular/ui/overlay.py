from PyQt6.QtCore import QRectF, Qt, QTime
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from core_sys import config, get_color
from horology import draw_clock_complications, draw_clock_face, draw_clock_ticks_and_indices, draw_horological_hand


class OverlayWidget(QWidget):
    """Floating overlay widget showing timer progress."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(200, 200)
        self.sp = 0
        self.dp = 0
        self.txt = "00:00"
        self.sm = 0
        self.pm = 1
        self.ring_color = QColor("#0a84ff")
        self.bg_override_color = None
        sc = QApplication.primaryScreen().geometry()
        self.move(sc.width() // 2 - 100, 20)
        self.oldPos = None

    def update_state(self, time_str, progress_pct, worked_mins, total_mins, active_course, distraction_mode):
        self.txt = time_str
        self.sp = progress_pct / 100.0
        self.sm = worked_mins
        self.pm = total_mins
        self.dp = min(self.sm / max(self.pm, 1), 1.0)
        self.ring_color = get_color(active_course)

        if distraction_mode == "App":
            self.bg_override_color = QColor(255, 140, 0, 220)
        elif distraction_mode == "Camera":
            self.bg_override_color = QColor(255, 50, 50, 220)
        else:
            self.bg_override_color = None
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.oldPos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self.oldPos is not None:
            d = e.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + d.x(), self.y() + d.y())
            self.oldPos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        self.oldPos = None

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = 90
        p.translate(100, 100)
        bg_col = self.bg_override_color if self.bg_override_color else QColor(15, 15, 17, 220)
        draw_clock_face(p, radius, bg_col)
        p.setPen(QPen(QColor(255, 255, 255, 30), 8))
        p.drawArc(-70, -70, 140, 140, 0, 360 * 16)
        p.setPen(QPen(self.ring_color, 8, cap=Qt.PenCapStyle.RoundCap))
        p.drawArc(-70, -70, 140, 140, 90 * 16, int(-self.sp * 360 * 16))
        p.setPen(QColor("white"))
        p.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        p.drawText(QRectF(-90, 20, 180, 40), Qt.AlignmentFlag.AlignCenter, self.txt)
        draw_clock_ticks_and_indices(p, radius)
        draw_clock_complications(p, radius)

        t = QTime.currentTime()
        h_style = config.get("clock_hands", "Classic")
        comp = config.get("clock_complication", "None")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("white")))
        p.save()
        p.rotate(30.0 * (t.hour() + t.minute() / 60.0))
        draw_horological_hand(p, h_style, 45, 3, True)
        p.restore()
        p.save()
        p.rotate(6.0 * (t.minute() + t.second() / 60.0))
        draw_horological_hand(p, h_style, 65, 2, False)
        p.restore()

        sec_col = self.ring_color
        if comp == "Small Seconds":
            p.save()
            p.translate(0, int(radius - 40))
            p.setBrush(QBrush(sec_col))
            p.setPen(QPen(sec_col, 1))
            p.rotate(6.0 * t.second())
            p.drawLine(0, 0, 0, -12)
            p.restore()
        else:
            p.setBrush(QBrush(sec_col))
            p.setPen(QPen(sec_col, 2))
            p.save()
            p.rotate(6.0 * t.second())
            if h_style in ["Serpentine", "Arrow", "Sword"]:
                draw_horological_hand(p, h_style, 75, 1, False)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRect(-1, 0, 2, -75)
            p.restore()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(-3, -3, 6, 6)
