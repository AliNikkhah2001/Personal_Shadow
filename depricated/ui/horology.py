import numpy as np
from datetime import datetime
from PyQt6.QtCore import QPoint, QRect, Qt, QRectF
from PyQt6.QtGui import QPainterPath, QColor, QPen, QBrush, QFont, QRadialGradient, QConicalGradient

def draw_metallic_gradient(p, rect, base_color):
    grad = QConicalGradient(rect.center(), 45)
    r, g, b = base_color.red(), base_color.green(), base_color.blue()
    grad.setColorAt(0.0, QColor(min(255, r+50), min(255, g+50), min(255, b+50)))
    grad.setColorAt(0.25, QColor(max(0, r-40), max(0, g-40), max(0, b-40)))
    grad.setColorAt(0.5, QColor(min(255, r+70), min(255, g+70), min(255, b+70)))
    grad.setColorAt(0.75, QColor(max(0, r-40), max(0, g-40), max(0, b-40)))
    grad.setColorAt(1.0, QColor(min(255, r+50), min(255, g+50), min(255, b+50)))
    p.setBrush(grad)

def draw_horological_hands(p, style, length, w, is_hour=False):
    c = p.brush().color()
    length = int(length)
    w = int(w)
    
    # Draw Drop Shadow for realism and depth so hands don't look messy or hidden
    p.save()
    p.translate(2, 2)
    p.setBrush(QColor(0, 0, 0, 80))
    p.setPen(Qt.PenStyle.NoPen)
    if style == "Spade": p.drawEllipse(-6, -length+3, 12, 12)
    elif style in ["Dauphine", "Alpha", "Sword"]: p.drawConvexPolygon([QPoint(-w*2, 0), QPoint(w*2, 0), QPoint(0, -length)])
    elif style == "Baton": p.drawRect(-w, 0, w*2, -length)
    else: p.drawConvexPolygon([QPoint(-w, 8), QPoint(w, 8), QPoint(0, -length)])
    p.restore()

    p.setBrush(QBrush(c))
    # Give all hands a crisp micro-outline to separate them from the bright dial
    p.setPen(QPen(QColor(0, 0, 0, 150), 1)) 
    
    if style == "Spade":
        p.drawLine(0, 0, 0, -length + 15)
        p.drawEllipse(-6, -length+3, 12, 12)
    elif style == "Breguet":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(0, 0, 0, -length + 12)
        p.drawEllipse(-4, -length+4, 8, 8)
        p.drawLine(0, -length+4, 0, -length)
    elif style == "Dauphine":
        p.drawConvexPolygon([QPoint(-w*2, 0), QPoint(w*2, 0), QPoint(0, -length)])
    elif style == "Alpha":
        p.drawConvexPolygon([QPoint(-w*2, -10), QPoint(w*2, -10), QPoint(0, -length)])
        p.drawLine(0, 0, 0, -10)
    elif style == "Pencil":
        p.drawRect(-w, 0, w*2, -length+5)
        p.drawConvexPolygon([QPoint(-w, -length+5), QPoint(w, -length+5), QPoint(0, -length)])
    elif style == "Serpentine":
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(0, 0)
        path.cubicTo(w*4, -length//3, -w*4, -length*2//3, 0, -length)
        p.strokePath(path, p.pen())
    elif style == "Mercedes":
        p.drawLine(0, 0, 0, int(-length*0.5))
        if is_hour:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(int(-w*1.5), int(-length*0.7), int(w*3), int(w*3))
            p.drawLine(0, int(-length*0.55), 0, int(-length*0.7))
            p.drawLine(0, int(-length*0.55), int(-w*1.2), int(-length*0.6))
            p.drawLine(0, int(-length*0.55), int(w*1.2), int(-length*0.6))
    elif style == "Sword":
        p.drawConvexPolygon([QPoint(int(-w//2), 0), QPoint(int(-w*2), int(-length*0.6)), QPoint(0, -length), QPoint(int(w*2), int(-length*0.6)), QPoint(int(w//2), 0)])
    elif style == "Arrow":
        p.drawLine(0, 0, 0, int(-length*0.7))
        p.drawConvexPolygon([QPoint(int(-w*2.5), int(-length*0.7)), QPoint(int(w*2.5), int(-length*0.7)), QPoint(0, -length)])
    elif style == "Baton":
        p.drawRect(-w, 0, w*2, -length)
    else:
        p.drawConvexPolygon([QPoint(-w, 8), QPoint(w, 8), QPoint(0, -length)])

def draw_crystal_glare(p, radius):
    """ Drawn LAST so it overlays the hands and center pin properly """
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 12))
    p.drawChord(QRectF(-radius, -radius, radius*2, radius*2), 45*16, 90*16)

def draw_horological_face(p, radius, cfg):
    case = cfg.get("clock_case", "Round")
    bezel = cfg.get("clock_bezel", "Plain")
    ticks = cfg.get("clock_ticks", "Standard")
    indices = cfg.get("clock_indices", "Baton")
    comp = cfg.get("clock_comp", "None")
    
    if bezel == "Fluted":
        p.setPen(QPen(QColor(200,200,200,100), 2))
        for i in range(60): 
            p.drawLine(0, radius, 0, radius+5)
            p.rotate(6)
    elif bezel == "Diver":
        p.setPen(QPen(QColor(30,30,30,250), 10))
        p.drawEllipse(int(-radius-5), int(-radius-5), int(radius*2+10), int(radius*2+10))
        p.setPen(QColor("white"))
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        for i in range(0, 60, 10):
            if i == 0: 
                p.drawConvexPolygon([QPoint(-5, int(-radius-10)), QPoint(5, int(-radius-10)), QPoint(0, -radius)])
            else: 
                p.drawText(QRect(-10, int(-radius-15), 20, 20), Qt.AlignmentFlag.AlignCenter, str(i))
            p.rotate(60)
    elif bezel == "GMT":
        p.setPen(QPen(QColor(200, 0, 0, 200), 8))
        p.drawArc(int(-radius-4), int(-radius-4), int(radius*2+8), int(radius*2+8), 0, 180*16)
        p.setPen(QPen(QColor(0, 0, 200, 200), 8))
        p.drawArc(int(-radius-4), int(-radius-4), int(radius*2+8), int(radius*2+8), 180*16, 180*16)
    elif bezel == "Coin-Edge":
        p.setPen(QPen(QColor(150,150,150,150), 1))
        for i in range(120): 
            p.drawLine(0, radius, 0, radius+3)
            p.rotate(3)

    p.setPen(QPen(QColor(255,255,255,80), 2))
    p.setBrush(QBrush(QColor(15,15,17,200)))
    
    if case == "Square": 
        p.drawRect(int(-radius), int(-radius), int(radius*2), int(radius*2))
    elif case == "Cushion": 
        p.drawRoundedRect(int(-radius), int(-radius), int(radius*2), int(radius*2), 30, 30)
    elif case == "Tonneau": 
        p.drawRoundedRect(int(-radius*0.85), int(-radius), int(radius*1.7), int(radius*2), 20, 40)
    else: 
        p.drawEllipse(int(-radius), int(-radius), int(radius*2), int(radius*2))

    if ticks != "Clean":
        p.save()
        if ticks == "Railroad":
            p.setPen(QPen(QColor(255,255,255,100), 1))
            p.drawEllipse(int(-radius+5), int(-radius+5), int(radius*2-10), int(radius*2-10))
            p.drawEllipse(int(-radius+12), int(-radius+12), int(radius*2-24), int(radius*2-24))
        for i in range(60):
            if i % 5 == 0: 
                p.setPen(QPen(QColor(255,255,255,180), 2))
                p.drawLine(int(radius-12), 0, int(radius-5), 0)
            else: 
                p.setPen(QPen(QColor(255,255,255,60), 1))
                p.drawLine(int(radius-8), 0, int(radius-5), 0)
            p.rotate(6.0)
        p.restore()
        if ticks == "Crosshair":
            p.setPen(QPen(QColor(255,255,255,40), 1))
            p.drawLine(int(-radius+15), 0, int(radius-15), 0)
            p.drawLine(0, int(-radius+15), 0, int(radius-15))

    if indices != "None":
        p.save()
        p.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        p.setPen(QPen(QColor("white")))
        for i in range(1, 13):
            angle = (i * 30 - 90) * np.pi / 180
            r_ind = radius - 22
            x, y = r_ind * np.cos(angle), r_ind * np.sin(angle)
            if indices == "Baton": 
                p.save()
                p.translate(x, y)
                p.rotate(i*30)
                p.drawRect(-2, -5, 4, 10)
                p.restore()
            elif indices == "Dot":
                if i in [3,6,9]: 
                    p.save()
                    p.translate(x, y)
                    p.rotate(i*30)
                    p.drawRect(-2, -6, 4, 12)
                    p.restore()
                elif i == 12: 
                    p.drawConvexPolygon([QPoint(int(x), int(y-8)), QPoint(int(x-6), int(y+6)), QPoint(int(x+6), int(y+6))])
                else: 
                    p.drawEllipse(int(x-4), int(y-4), 8, 8)
            else:
                if indices == "California": 
                    text = ["I","II","III","4","5","6","7","8","9","X","XI","XII"][i-1]
                else: 
                    text = str(i) if indices == "Arabic" else ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"][i-1]
                p.drawText(QRect(int(x)-15, int(y)-15, 30, 30), Qt.AlignmentFlag.AlignCenter, text)
        p.restore()

    if comp == "Date Window":
        p.setBrush(QBrush(QColor("white")))
        p.setPen(QPen(QColor("black")))
        p.drawRect(int(radius-45), -10, 25, 20)
        p.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        p.drawText(QRect(int(radius-45), -10, 25, 20), Qt.AlignmentFlag.AlignCenter, str(datetime.now().day))
    elif comp == "Small Seconds":
        p.setPen(QPen(QColor(255,255,255,80), 1))
        p.drawEllipse(-20, int(radius-50), 40, 40)