"""PDF Editor - Advanced PDF rendering and annotation tools.

Contains the AdvancedPDFCanvas and AdvancedPDFWindow classes extracted from
system_bridge.py for modular PDF editing functionality.
"""

from __future__ import annotations

import os
from datetime import datetime

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core_sys import db


class AdvancedPDFCanvas(QLabel):
    """Canvas widget for PDF page rendering and annotation."""

    action_completed = pyqtSignal(str, object, int)

    def __init__(self, page_num):
        super().__init__()
        self.page_num = page_num
        self.mode = "View"
        self.start_pt = None
        self.cur_pt = None
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, e):  # noqa: N802
        if self.mode != "View" and e.button() == Qt.MouseButton.LeftButton:
            self.start_pt = e.pos()
            self.cur_pt = e.pos()

    def mouseMoveEvent(self, e):  # noqa: N802
        if self.start_pt:
            self.cur_pt = e.pos()
            self.update()

    def mouseReleaseEvent(self, e):  # noqa: N802
        if self.start_pt and self.cur_pt and e.button() == Qt.MouseButton.LeftButton:
            if self.mode == "Line":
                self.action_completed.emit(self.mode, (self.start_pt, self.cur_pt), self.page_num)
            else:
                x0, y0 = self.start_pt.x(), self.start_pt.y()
                x1, y1 = self.cur_pt.x(), self.cur_pt.y()
                r = QRectF(float(min(x0, x1)), float(min(y0, y1)), float(abs(x1 - x0)), float(abs(y1 - y0)))
                if r.width() > 5 and r.height() > 5:
                    self.action_completed.emit(self.mode, r, self.page_num)
        self.start_pt = None
        self.cur_pt = None
        self.update()

    def paintEvent(self, e):  # noqa: N802
        super().paintEvent(e)
        if self.start_pt and self.cur_pt:
            p = QPainter(self)
            p.setPen(QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine))
            if self.mode == "Line":
                p.drawLine(self.start_pt, self.cur_pt)
            else:
                p.setBrush(QColor(0, 150, 255, 50))
                p.drawRect(
                    QRectF(
                        float(self.start_pt.x()),
                        float(self.start_pt.y()),
                        float(self.cur_pt.x() - self.start_pt.x()),
                        float(self.cur_pt.y() - self.start_pt.y()),
                    ).normalized()
                )


class AdvancedPDFWindow(QMainWindow):
    """Standalone advanced PDF editor window."""

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.doc = pymupdf.open(filepath)
        self.zoom = 2.0
        self.mode = "View"
        self.resize(1200, 900)
        self.setWindowTitle(f"Native Pro Editor - {os.path.basename(self.filepath)}")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.canvas_container = QWidget()
        self.canvas_container.setStyleSheet("background-color: #0f0f11;")
        self.layout = QVBoxLayout(self.canvas_container)
        self.layout.setSpacing(20)
        self.layout.setContentsMargins(40, 40, 40, 40)

        self.pages = []
        for i in range(len(self.doc)):
            canvas = AdvancedPDFCanvas(i)
            canvas.action_completed.connect(self.handle_action)
            self.layout.addWidget(canvas)
            self.pages.append(canvas)

        self.scroll_area.setWidget(self.canvas_container)
        self.setCentralWidget(self.scroll_area)

        tb = QToolBar("Tools")
        self.addToolBar(tb)
        for act in ["View", "Highlight", "Note", "Box", "Line"]:
            a = tb.addAction(act)
            a.triggered.connect(lambda ch, m=act: self.set_mode(m))
        tb.addSeparator()
        tb.addAction("Zoom In").triggered.connect(lambda: self.set_zoom(self.zoom + 0.5))
        tb.addAction("Zoom Out").triggered.connect(lambda: self.set_zoom(self.zoom - 0.5))
        tb.addSeparator()
        tb.addAction("Screenshot").triggered.connect(self.screenshot)
        tb.addAction("Bookmark").triggered.connect(self.bookmark)

        self.render_all_pages()
        self.setStyleSheet(
            "QMainWindow { background-color: #1e1e2b; } QToolBar { background-color: #282a36; color: white; border: none; padding: 5px; }"
        )

        QShortcut(
            QKeySequence("Down"),
            self,
            lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() + 100),
        )
        QShortcut(
            QKeySequence("Up"),
            self,
            lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() - 100),
        )
        QShortcut(
            QKeySequence("Right"),
            self,
            lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() + 600),
        )
        QShortcut(
            QKeySequence("Left"),
            self,
            lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() - 600),
        )

    def set_mode(self, m):
        self.mode = m
        for canvas in self.pages:
            canvas.mode = m
        self.statusBar().showMessage(f"Mode: {m}")

    def set_zoom(self, z):
        self.zoom = max(0.5, z)
        self.render_all_pages()

    def render_all_pages(self):
        for i, _canvas in enumerate(self.pages):
            self.render_single_page(i)

    def render_single_page(self, page_num):
        page = self.doc[page_num]
        mat = pymupdf.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)
        fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        self.pages[page_num].setPixmap(QPixmap.fromImage(img))
        self.pages[page_num].setFixedSize(pix.width, pix.height)

    def handle_action(self, mode, geom, page_num):
        page = self.doc[page_num]
        if mode == "Line":
            p1, p2 = geom
            annot = page.add_line_annot(
                pymupdf.Point(p1.x() / self.zoom, p1.y() / self.zoom),
                pymupdf.Point(p2.x() / self.zoom, p2.y() / self.zoom),
            )
            annot.set_colors(stroke=(1, 0, 0))
            annot.update()
        else:
            rect = pymupdf.Rect(
                geom.x() / self.zoom,
                geom.y() / self.zoom,
                (geom.x() + geom.width()) / self.zoom,
                (geom.y() + geom.height()) / self.zoom,
            )
            if mode == "Highlight":
                words = page.get_text("words")
                quads = [pymupdf.Rect(w[:4]) for w in words if pymupdf.Rect(w[:4]).intersects(rect)]
                if quads:
                    annot = page.add_highlight_annot(quads)
                    annot.set_colors(stroke=(1, 1, 0))
                    annot.update()
            elif mode == "Box":
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=(0, 0, 1))
                annot.update()
            elif mode == "Note":
                text, ok = QInputDialog.getMultiLineText(self, "Note", "Enter note text:")
                if ok and text:
                    annot = page.add_text_annot(rect.tl, text)
                    annot.update()
        self.doc.save(self.doc.name, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        self.render_single_page(page_num)

    def screenshot(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Screenshot", "screenshot.png", "PNG (*.png)")
        if path:
            pix = self.scroll_area.widget().grab()
            pix.save(path)

    def bookmark(self):
        db.c.execute(
            "INSERT INTO notes (title, content, course, folder, color, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"Bookmark: {os.path.basename(self.filepath)}",
                f"Bookmarked {os.path.basename(self.filepath)}",
                "General",
                "Bookmarks",
                "#facc15",
                datetime.now().isoformat(),
            ),
        )
        db.safe_commit()
        QMessageBox.information(self, "Bookmark", "Bookmark successfully added to Notes database!")
