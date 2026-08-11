import os
import sys

import fitz  # PyMuPDF
from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QRubberBand,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class PageWidget(QLabel):
    """
    Hardware-Accelerated Lazy Loading Page Widget.
    Performs true PDF text intersection mapping for annotations.
    """

    def __init__(self, doc, page_num, editor):
        super().__init__()
        self.doc = doc
        self.page_num = page_num
        self.editor = editor

        self.scale = self.editor.zoom_level
        self._pixmap = None

        # Pre-allocate exact geometric layout space without rendering the image
        self.pdf_rect = self.doc[self.page_num].rect
        self.setFixedSize(int(self.pdf_rect.width * self.scale), int(self.pdf_rect.height * self.scale))

        self.start_pt = None
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)

        # Sleek shadow and border for the page
        self.setStyleSheet("""
            background-color: white;
            border: 1px solid #27272a;
            margin-bottom: 20px;
        """)

    def update_zoom(self, new_scale):
        self.scale = new_scale
        self.setFixedSize(int(self.pdf_rect.width * self.scale), int(self.pdf_rect.height * self.scale))
        self._pixmap = None  # Invalidate cache to force a re-render
        self.update()

    def paintEvent(self, event):  # noqa: N802
        # Lazy Loading: Only render PyMuPDF to QImage when Qt asks to paint this specific widget
        if self._pixmap is None:
            page = self.doc[self.page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            self._pixmap = QPixmap.fromImage(img)
            self.setPixmap(self._pixmap)
        super().paintEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        if self.editor.current_tool == "Pan":
            return
        self.start_pt = event.pos()
        self.rubber_band.setGeometry(QRect(self.start_pt, QSize()))
        # Match Rubberband color to the active tool color
        r, g, b = self.editor.current_color
        self.rubber_band.setStyleSheet(
            f"background-color: rgba({int(r * 255)}, {int(g * 255)}, {int(b * 255)}, 60); border: 1px solid rgba({int(r * 255)}, {int(g * 255)}, {int(b * 255)}, 200);"
        )
        self.rubber_band.show()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self.start_pt and self.rubber_band.isVisible():
            self.rubber_band.setGeometry(QRect(self.start_pt, event.pos()).normalized())

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self.start_pt and self.rubber_band.isVisible():
            self.rubber_band.hide()
            end_pt = event.pos()
            self.apply_annotation(self.start_pt, end_pt)
            self.start_pt = None

    def apply_annotation(self, start, end):
        rect = QRect(start, end).normalized()
        if rect.width() < 5 or rect.height() < 5:
            return

        # Convert Screen CSS Pixels -> Absolute PDF Points
        rect_pdf = fitz.Rect(
            rect.left() / self.scale, rect.top() / self.scale, rect.right() / self.scale, rect.bottom() / self.scale
        )

        page = self.doc[self.page_num]
        tool = self.editor.current_tool
        color = self.editor.current_color
        dirty = False

        if tool in ["Highlight", "Underline", "StrikeOut"]:
            # TRUE TEXT HIGHLIGHTING: Intersect box with exact word geometry
            words = page.get_text("words")
            highlight_rects = []
            for w in words:
                w_rect = fitz.Rect(w[:4])
                if w_rect.intersects(rect_pdf):
                    highlight_rects.append(w_rect)

            if highlight_rects:
                if tool == "Highlight":
                    annot = page.add_highlight_annot(highlight_rects)
                elif tool == "Underline":
                    annot = page.add_underline_annot(highlight_rects)
                elif tool == "StrikeOut":
                    annot = page.add_strikeout_annot(highlight_rects)

                annot.set_colors(stroke=color)
                annot.update()
                dirty = True

        elif tool == "Note":
            text, ok = QInputDialog.getMultiLineText(self, "Add Annotation", "Enter your note:")
            if ok and text:
                annot = page.add_text_annot(fitz.Point(rect_pdf.x0, rect_pdf.y0), text)
                annot.set_colors(stroke=color)
                annot.update()
                dirty = True

        elif tool == "Screenshot":
            pix = page.get_pixmap(clip=rect_pdf, matrix=fitz.Matrix(3.0, 3.0))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            QApplication.clipboard().setImage(img)
            self.editor.statusBar().showMessage("High-Res PDF Region copied to clipboard!", 4000)
            return

        if dirty:
            try:
                # Instant Auto-Save via fast incremental append
                self.doc.save(self.doc.name, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
                self.editor.statusBar().showMessage(f"Added {tool} and Auto-Saved.", 2000)
            except Exception as e:
                self.editor.statusBar().showMessage(f"Error saving: {e!s}", 4000)

            self._pixmap = None  # Force a re-render of this page
            self.update()


class NativePDFEditor(QMainWindow):
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.doc = fitz.open(filepath)
        self.zoom_level = 2.0
        self.current_tool = "Highlight"

        # Predefined PyMuPDF RGB tuples (0.0 to 1.0)
        self.color_palette = {
            "Yellow": (1.0, 0.9, 0.2),
            "Green": (0.2, 0.8, 0.2),
            "Blue": (0.2, 0.6, 1.0),
            "Pink": (1.0, 0.4, 0.7),
            "Purple": (0.6, 0.2, 0.8),
        }
        self.current_color = self.color_palette["Yellow"]

        self.setWindowTitle(f"Mind Palace Advanced Reader - {os.path.basename(filepath)}")
        self.resize(1300, 900)

        self.setup_ui()
        self.setup_shortcuts()

    def setup_ui(self):
        # 1. Dark Mode Styling for Master Window
        self.setStyleSheet("""
            QMainWindow { background-color: #050505; }
            QToolBar { background-color: #0f0f13; border-bottom: 1px solid #1e1e2b; padding: 5px; spacing: 5px; }
            QStatusBar { background-color: #0f0f13; color: #a1a1aa; border-top: 1px solid #1e1e2b; }
            QPushButton { background-color: #181820; color: #e2e8f0; border: 1px solid #27272a; padding: 6px 14px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #272733; }
            QPushButton:checked { background-color: #3b82f6; color: white; border: 1px solid #60a5fa; }
            QLineEdit { background-color: #050505; color: white; border: 1px solid #27272a; padding: 4px; border-radius: 4px; }
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { border: none; background: #050505; width: 12px; margin: 0px; }
            QScrollBar::handle:vertical { background: #27272a; min-height: 30px; border-radius: 6px; }
            QScrollBar::handle:vertical:hover { background: #3f3f46; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; }
        """)

        # 2. Top Control Toolbar (Tools & Colors)
        self.top_bar = QToolBar("Top Controls")
        self.top_bar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.top_bar)

        # Tools Group
        self.tool_grp = QButtonGroup(self)
        for t in ["Pan", "Highlight", "Underline", "StrikeOut", "Note", "Screenshot"]:
            btn = QPushButton(t)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, name=t: self.set_tool(name))
            self.top_bar.addWidget(btn)
            self.tool_grp.addButton(btn)
            if t == "Highlight":
                btn.setChecked(True)

        # Spacer
        spacer1 = QWidget()
        spacer1.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.top_bar.addWidget(spacer1)

        # Color Group
        self.top_bar.addWidget(QLabel(" Color: ", styleSheet="color: #71717a; font-weight: bold; font-size: 11px;"))
        self.color_grp = QButtonGroup(self)
        for name, rgb in self.color_palette.items():
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # Convert 0-1 float back to 0-255 int for CSS
            css_color = f"rgb({int(rgb[0] * 255)}, {int(rgb[1] * 255)}, {int(rgb[2] * 255)})"
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {css_color}; border-radius: 12px; border: 2px solid transparent; }} QPushButton:checked {{ border: 2px solid white; }}"
            )
            btn.clicked.connect(lambda checked, c=rgb: self.set_color(c))
            self.top_bar.addWidget(btn)
            self.color_grp.addButton(btn)
            if name == "Yellow":
                btn.setChecked(True)

        # 3. Continuous Scroll Viewport
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)

        self.canvas_container = QWidget()
        self.canvas_container.setStyleSheet("background-color: #050505;")
        self.layout = QVBoxLayout(self.canvas_container)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Inject Lazy Pages
        self.page_widgets = []
        for i in range(len(self.doc)):
            pw = PageWidget(self.doc, i, self)
            self.layout.addWidget(pw)
            self.page_widgets.append(pw)

        self.scroll_area.setWidget(self.canvas_container)
        self.setCentralWidget(self.scroll_area)

        # 4. Bottom Control Toolbar (Navigation & Zoom)
        self.bottom_bar = QToolBar("Bottom Controls")
        self.bottom_bar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self.bottom_bar)

        self.lbl_page = QLabel(f" Page: 1 / {len(self.doc)} ")
        self.lbl_page.setStyleSheet("color: white; font-weight: bold; margin-right: 10px;")
        self.bottom_bar.addWidget(self.lbl_page)

        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("Go to page...")
        self.page_input.setFixedWidth(100)
        self.page_input.returnPressed.connect(self.jump_to_page)
        self.bottom_bar.addWidget(self.page_input)

        spacer2 = QWidget()
        spacer2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.bottom_bar.addWidget(spacer2)

        btn_z_out = QPushButton("Zoom -")
        btn_z_out.clicked.connect(lambda: self.change_zoom(-0.3))
        btn_z_in = QPushButton("Zoom +")
        btn_z_in.clicked.connect(lambda: self.change_zoom(0.3))

        self.bottom_bar.addWidget(btn_z_out)
        self.bottom_bar.addWidget(btn_z_in)

        # 5. Status Bar
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Engine Loaded. Keys: Arrows/PgUp/PgDn to scroll. Esc to exit.")

    def set_tool(self, name):
        self.current_tool = name
        # If panning, switch cursor. Otherwise crosshair.
        cursor = Qt.CursorShape.OpenHandCursor if name == "Pan" else Qt.CursorShape.CrossCursor
        for pw in self.page_widgets:
            pw.setCursor(cursor)
        self.statusBar().showMessage(f"Tool selected: {name}")

    def set_color(self, rgb):
        self.current_color = rgb

    def change_zoom(self, delta):
        self.zoom_level = max(0.5, min(5.0, self.zoom_level + delta))
        for pw in self.page_widgets:
            pw.update_zoom(self.zoom_level)
        self.statusBar().showMessage(f"Zoom level: {self.zoom_level:.1f}x")

    def jump_to_page(self):
        try:
            target = int(self.page_input.text()) - 1
            if 0 <= target < len(self.page_widgets):
                # Calculate absolute Y position to jump to
                target_widget = self.page_widgets[target]
                y_pos = target_widget.pos().y()
                self.scroll_area.verticalScrollBar().setValue(y_pos)
                self.page_input.clear()
        except ValueError:
            pass

    def on_scroll(self):
        # Update the Bottom Bar Page Number dynamically based on scroll position
        y_scroll = self.scroll_area.verticalScrollBar().value()
        # Find which page widget intersects this Y coordinate
        for i, pw in enumerate(self.page_widgets):
            if pw.pos().y() + pw.height() > y_scroll + 100:  # 100px threshold
                self.lbl_page.setText(f" Page: {i + 1} / {len(self.doc)} ")
                break

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Esc"), self, self.close)

        scroll = self.scroll_area.verticalScrollBar()
        QShortcut(QKeySequence("Down"), self, lambda: scroll.setValue(scroll.value() + 80))
        QShortcut(QKeySequence("Up"), self, lambda: scroll.setValue(scroll.value() - 80))
        QShortcut(QKeySequence("PageDown"), self, lambda: scroll.setValue(scroll.value() + 600))
        QShortcut(QKeySequence("PageUp"), self, lambda: scroll.setValue(scroll.value() - 600))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if len(sys.argv) > 1:
        editor = NativePDFEditor(sys.argv[1])
        editor.show()
        sys.exit(app.exec())
    else:
        print("Usage: python native_pdf_editor.py <path_to_pdf>")
