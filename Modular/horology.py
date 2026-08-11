from datetime import datetime

import numpy as np
from PyQt6.QtCore import QPoint, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen

from core_sys import config


def draw_clock_face(p, radius, bg_color):
    shape = config.get("clock_case_shape", "Round")
    bezel = config.get("clock_bezel", "Plain")

    if bezel == "GMT (Pepsi)":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(200, 40, 40, 220)))
        p.drawPie(QRectF(-radius - 6, -radius - 6, (radius + 6) * 2, (radius + 6) * 2), 0, 180 * 16)
        p.setBrush(QBrush(QColor(40, 80, 200, 220)))
        p.drawPie(QRectF(-radius - 6, -radius - 6, (radius + 6) * 2, (radius + 6) * 2), 180 * 16, 180 * 16)
    elif bezel == "Diver":
        p.setPen(QPen(QColor(30, 30, 35, 255), 14))
        p.drawEllipse(int(-radius - 2), int(-radius - 2), int((radius + 2) * 2), int((radius + 2) * 2))

    p.setBrush(QBrush(bg_color))
    p.setPen(Qt.PenStyle.NoPen)

    if shape == "Square":
        p.drawRect(int(-radius), int(-radius), int(radius * 2), int(radius * 2))
    elif shape == "Cushion":
        p.drawRoundedRect(
            int(-radius), int(-radius), int(radius * 2), int(radius * 2), int(radius * 0.3), int(radius * 0.3)
        )
    elif shape == "Tonneau":
        path = QPainterPath()
        path.moveTo(-radius * 0.7, -radius)
        path.lineTo(radius * 0.7, -radius)
        path.quadTo(radius, 0, radius * 0.7, radius)
        path.lineTo(-radius * 0.7, radius)
        path.quadTo(-radius, 0, -radius * 0.7, -radius)
        p.drawPath(path)
    else:
        p.drawEllipse(int(-radius), int(-radius), int(radius * 2), int(radius * 2))

    if bezel == "Fluted":
        p.save()
        p.setPen(QPen(QColor(200, 200, 200, 80), 3))
        for _ in range(60):
            p.drawLine(int(radius - 8), 0, int(radius), 0)
            p.rotate(6.0)
        p.restore()
    elif bezel == "Coin-Edge":
        p.save()
        p.setPen(QPen(QColor(150, 150, 150, 100), 1))
        for _ in range(120):
            p.drawLine(int(radius - 4), 0, int(radius), 0)
            p.rotate(3.0)
        p.restore()


def draw_clock_ticks_and_indices(p, radius):
    ticks = config.get("clock_ticks", "Standard")
    indices = config.get("clock_indices", "None")

    if ticks != "Clean":
        p.save()
        if ticks == "Railroad":
            p.setPen(QPen(QColor(255, 255, 255, 100), 1))
            p.drawEllipse(int(-radius + 15), int(-radius + 15), int((radius - 15) * 2), int((radius - 15) * 2))
            p.drawEllipse(int(-radius + 20), int(-radius + 20), int((radius - 20) * 2), int((radius - 20) * 2))
            for _i in range(60):
                p.drawLine(int(radius - 20), 0, int(radius - 15), 0)
                p.rotate(6.0)
        elif ticks == "Crosshair":
            p.setPen(QPen(QColor(255, 255, 255, 50), 1))
            p.drawLine(int(-radius + 10), 0, int(radius - 10), 0)
            p.drawLine(0, int(-radius + 10), 0, int(radius - 10))
            for i in range(60):
                if i % 5 != 0:
                    p.drawLine(int(radius - 12), 0, int(radius - 10), 0)
                p.rotate(6.0)
        else:
            for i in range(60):
                if i % 5 == 0:
                    p.setPen(QPen(QColor(255, 255, 255, 180), 2))
                    p.drawLine(int(radius - 15), 0, int(radius - 10), 0)
                else:
                    p.setPen(QPen(QColor(255, 255, 255, 60), 1))
                    p.drawLine(int(radius - 12), 0, int(radius - 10), 0)
                p.rotate(6.0)
        p.restore()

    if indices != "None":
        p.save()
        p.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        for i in range(1, 13):
            angle = (i * 30 - 90) * np.pi / 180
            x = (radius - 25) * np.cos(angle)
            y = (radius - 25) * np.sin(angle)
            if indices == "Baton":
                p.save()
                p.translate(x, y)
                p.rotate(i * 30)
                p.setBrush(QBrush(QColor("white")))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRect(-2, -6, 4, 12)
                p.restore()
            else:
                p.setPen(QPen(QColor("white")))
                text = (
                    str(i)
                    if "Arabic" in indices
                    else ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"][i - 1]
                )
                p.drawText(QRectF(x - 15, y - 15, 30, 30), Qt.AlignmentFlag.AlignCenter, text)
        p.restore()


def draw_clock_complications(p, radius):
    comp = config.get("clock_complication", "None")
    if comp == "Date Window":
        p.save()
        p.setBrush(QBrush(QColor("white")))
        p.setPen(QPen(QColor("black"), 1))
        p.drawRect(int(radius - 40), -8, 20, 16)
        p.setPen(QPen(QColor("black")))
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.drawText(QRectF(radius - 40, -8, 20, 16), Qt.AlignmentFlag.AlignCenter, str(datetime.now().day))
        p.restore()
    elif comp == "Small Seconds":
        p.save()
        p.translate(0, int(radius - 40))
        p.setPen(QPen(QColor(255, 255, 255, 100), 1))
        p.drawEllipse(-15, -15, 30, 30)
        for _i in range(12):
            p.drawLine(12, 0, 15, 0)
            p.rotate(30.0)
        p.restore()


def draw_horological_hand(p, style, length, w, is_hour=False):
    color = p.brush().color()
    length, w = int(length), int(w)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color))

    if style == "Spade":
        p.setPen(QPen(color, 2))
        p.drawLine(0, 0, 0, -length + 15)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(-6, -length + 3, 12, 12)
    elif style == "Sword":
        p.drawConvexPolygon(
            [
                QPoint(int(-w // 2), 0),
                QPoint(int(-w * 2), int(-length * 0.6)),
                QPoint(0, -length),
                QPoint(int(w * 2), int(-length * 0.6)),
                QPoint(int(w // 2), 0),
            ]
        )
    else:
        p.drawRect(-w, 0, w * 2, -length + 5)
        p.drawConvexPolygon([QPoint(-w, -length + 5), QPoint(w, -length + 5), QPoint(0, -length)])
