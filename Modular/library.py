import os
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from core_sys import config

try:
    import pymupdf
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

class PDFCanvas(QLabel):
    annotation_drawn = pyqtSignal(QRectF)
    
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.start_pos = None
        self.curr_pos = None
        self.scale_factor = 1.0
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.start_pos = e.pos()
            self.curr_pos = e.pos()

    def mouseMoveEvent(self, e):
        if self.start_pos:
            self.curr_pos = e.pos()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.start_pos:
            x0 = self.start_pos.x() / self.scale_factor
            y0 = self.start_pos.y() / self.scale_factor
            x1 = e.pos().x() / self.scale_factor
            y1 = e.pos().y() / self.scale_factor
            
            rect = QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            if rect.width() > 5 and rect.height() > 5:
                self.annotation_drawn.emit(rect)
                
            self.start_pos = None
            self.curr_pos = None
            self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.start_pos and self.curr_pos:
            p = QPainter(self)
            p.setPen(QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine))
            p.setBrush(QColor(0, 150, 255, 50))
            p.drawRect(QRect(self.start_pos, self.curr_pos))

class LibraryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.lib_path = os.path.expanduser("~/MindPalace_Library")
        self.doc = None
        self.current_page = 0
        self.zoom = 1.5
        self.current_tool = "Highlight"
        self.device_id = config.get("device_id", "UnknownDevice")
        
        lay = QVBoxLayout(self)
        
        if not HAS_FITZ:
            err = QLabel("PyMuPDF is missing. Please run `python check_requirements.py` to install dependencies.")
            err.setStyleSheet("color: #ff453a; font-size: 18px; font-weight: bold;")
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(err)
            return

        # Main Splitter
        sp = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: File Browser
        left_panel = QFrame()
        left_panel.setObjectName("Panel")
        left_lay = QVBoxLayout(left_panel)
        left_lay.addWidget(QLabel("Synced Library", styleSheet="font-weight: bold;"))
        
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("background: transparent; border: 1px solid rgba(255,255,255,20); border-radius: 6px;")
        self.file_list.itemClicked.connect(self.load_pdf)
        self.refresh_files()
        
        btn_refresh = QPushButton("Refresh Folder")
        btn_refresh.clicked.connect(self.refresh_files)
        
        left_lay.addWidget(self.file_list)
        left_lay.addWidget(btn_refresh)
        sp.addWidget(left_panel)
        
        # Center: PDF Viewer
        center_panel = QFrame()
        center_panel.setObjectName("Panel")
        center_lay = QVBoxLayout(center_panel)
        
        # Toolbar
        tb = QHBoxLayout()
        
        # Tools Group
        self.tool_grp = QButtonGroup(self)
        for i, tool in enumerate(["Highlight", "Underline", "Note"]):
            btn = QPushButton(tool)
            btn.setCheckable(True)
            if i == 0: btn.setChecked(True)
            self.tool_grp.addButton(btn, i)
            tb.addWidget(btn)
        self.tool_grp.buttonClicked.connect(self.change_tool)
        
        tb.addStretch()
        
        # Zoom Controls
        btn_zoom_out = QPushButton("-")
        btn_zoom_out.clicked.connect(lambda: self.set_zoom(self.zoom - 0.2))
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.clicked.connect(lambda: self.set_zoom(self.zoom + 0.2))
        tb.addWidget(btn_zoom_out)
        tb.addWidget(btn_zoom_in)
        
        # Auto-Turn
        self.auto_spin = QSpinBox()
        self.auto_spin.setRange(1, 120)
        self.auto_spin.setValue(10)
        self.auto_spin.setSuffix(" s")
        self.btn_auto = QPushButton("Start Auto-Turn")
        self.btn_auto.setCheckable(True)
        self.btn_auto.clicked.connect(self.toggle_auto_turn)
        tb.addWidget(self.auto_spin)
        tb.addWidget(self.btn_auto)
        
        # Fullscreen
        btn_fs = QPushButton("Fullscreen")
        btn_fs.clicked.connect(self.toggle_fullscreen)
        tb.addWidget(btn_fs)
        
        center_lay.addLayout(tb)
        
        # Canvas Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setStyleSheet("background: rgba(10, 10, 15, 180); border-radius: 8px;")
        
        self.canvas = PDFCanvas()
        self.canvas.annotation_drawn.connect(self.add_annotation)
        self.scroll.setWidget(self.canvas)
        center_lay.addWidget(self.scroll)
        
        # Page Navigation
        nav = QHBoxLayout()
        btn_prev = QPushButton("◀ Prev")
        btn_prev.clicked.connect(lambda: self.change_page(-1))
        self.lbl_page = QLabel("Page 0 / 0")
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_next = QPushButton("Next ▶")
        btn_next.clicked.connect(lambda: self.change_page(1))
        nav.addWidget(btn_prev)
        nav.addWidget(self.lbl_page, 1)
        nav.addWidget(btn_next)
        center_lay.addLayout(nav)
        
        sp.addWidget(center_panel)
        
        # Right: Annotation History
        right_panel = QFrame()
        right_panel.setObjectName("Panel")
        right_lay = QVBoxLayout(right_panel)
        right_lay.addWidget(QLabel("Metadata & Annotations", styleSheet="font-weight: bold;"))
        self.annot_list = QListWidget()
        self.annot_list.setStyleSheet("background: transparent; border: 1px solid rgba(255,255,255,20); border-radius: 6px; font-size: 12px;")
        self.annot_list.setWordWrap(True)
        right_lay.addWidget(self.annot_list)
        sp.addWidget(right_panel)
        
        sp.setSizes([200, 800, 250])
        lay.addWidget(sp)
        
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(lambda: self.change_page(1))

    def refresh_files(self):
        self.file_list.clear()
        if os.path.exists(self.lib_path):
            for f in os.listdir(self.lib_path):
                if f.lower().endswith(".pdf"):
                    self.file_list.addItem(f)

    def load_pdf(self, item):
        path = os.path.join(self.lib_path, item.text())
        try:
            self.doc = pymupdf.open(path)
            self.current_page = 0
            self.render_page()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load PDF:\n{e}")

    def change_tool(self, btn):
        self.current_tool = btn.text()

    def set_zoom(self, z):
        self.zoom = max(0.5, min(z, 4.0))
        self.render_page()

    def change_page(self, delta):
        if not self.doc: return
        new_page = self.current_page + delta
        if 0 <= new_page < len(self.doc):
            self.current_page = new_page
            self.render_page()

    def toggle_auto_turn(self, checked):
        if checked:
            self.auto_timer.start(self.auto_spin.value() * 1000)
            self.btn_auto.setStyleSheet("background-color: #30a14e; font-weight: bold;")
            self.btn_auto.setText("Stop Auto-Turn")
        else:
            self.auto_timer.stop()
            self.btn_auto.setStyleSheet("")
            self.btn_auto.setText("Start Auto-Turn")

    def toggle_fullscreen(self):
        main_win = self.window()
        sidebar = main_win.findChild(QFrame, "Sidebar")
        if main_win.isFullScreen():
            main_win.showNormal()
            if sidebar: sidebar.show()
        else:
            main_win.showFullScreen()
            if sidebar: sidebar.hide()

    def render_page(self):
        if not self.doc: return
        page = self.doc[self.current_page]
        mat = pymupdf.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)
        
        fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        
        self.canvas.scale_factor = self.zoom
        self.canvas.setPixmap(QPixmap.fromImage(img))
        self.canvas.setFixedSize(pix.width, pix.height)
        self.lbl_page.setText(f"Page {self.current_page + 1} / {len(self.doc)}")
        
        self.load_annotations(page)

    def add_annotation(self, rect):
        if not self.doc: return
        page = self.doc[self.current_page]
        
        # PyMuPDF Rect format
        r = pymupdf.Rect(rect.x(), rect.y(), rect.x() + rect.width(), rect.y() + rect.height())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            if self.current_tool == "Highlight":
                annot = page.add_highlight_annot(r)
                annot.set_colors(stroke=(1, 1, 0)) # Yellow
                annot.set_info(info={"title": self.device_id, "subject": "Highlight", "content": f"Automated sync capture at {timestamp}"})
                annot.update()
                
            elif self.current_tool == "Underline":
                annot = page.add_underline_annot(r)
                annot.set_colors(stroke=(0, 0.5, 1)) # Blue
                annot.set_info(info={"title": self.device_id, "subject": "Underline", "content": f"Automated sync capture at {timestamp}"})
                annot.update()
                
            elif self.current_tool == "Note":
                text, ok = QInputDialog.getMultiLineText(self, "Add Note", "Enter your note:")
                if ok and text:
                    annot = page.add_text_annot(r.tl, text)
                    annot.set_info(info={"title": self.device_id, "subject": "Note", "content": f"{timestamp}\n{text}"})
                    annot.update()

            # Save the file incrementally back to the drive so the SyncManager catches it
            self.doc.save(self.doc.name, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
            self.render_page()
            
        except Exception as e:
            QMessageBox.warning(self, "Annotation Error", f"Failed to save annotation: {e}")

    def load_annotations(self, page):
        self.annot_list.clear()
        annot = page.first_annot
        while annot:
            info = annot.info
            title = info.get("title", "Unknown Device")
            subject = info.get("subject", "Annotation")
            content = info.get("content", "")
            
            display_text = f"[{subject}] by {title}\n{content}"
            item = QListWidgetItem(display_text)
            self.annot_list.addItem(item)
            
            annot = annot.next