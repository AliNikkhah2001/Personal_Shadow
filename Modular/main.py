import sys
import os
import urllib3
import traceback
import importlib

# Force Python to look in the current directory for the 'tabs' and 'ui' folders
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QTextEdit, QWidget, QHBoxLayout, QFrame, QVBoxLayout, QStackedWidget, QPushButton, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPainter, QLinearGradient, QColor, QFontDatabase, QKeySequence, QShortcut

from core_sys import config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def load_module_safely(module_path, class_name):
    """Dynamically loads a tab. Returns a safe error widget if the file is missing/broken."""
    try:
        mod = importlib.import_module(module_path)
        widget_class = getattr(mod, class_name)
        return widget_class()
    except Exception as e:
        err_lbl = QLabel(f"⚠️ Component Offline\n\nFailed to load: {module_path}.{class_name}\nError: {str(e)}")
        err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        err_lbl.setStyleSheet("color: #ff453a; font-size: 16px; font-weight: bold; background-color: rgba(255,69,58,20); border: 1px solid #ff453a; border-radius: 12px;")
        return err_lbl

class MindPalaceOS(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kourosh's Mind Palace")
        self.resize(1400, 900)
        self.bg_img = None
        self.is_distracted = False
        self.setCentralWidget(QLabel("Loading System OS Core Modules...", alignment=Qt.AlignmentFlag.AlignCenter, styleSheet="color: white; font-size: 24px;"))
        self.setStyleSheet("background-color: #0f0f11;")
        QTimer.singleShot(200, self.delayed_init)

    def delayed_init(self):
        try: 
            self._do_init()
        except Exception as e:
            msg = traceback.format_exc()
            QMessageBox.critical(self, "Init Error", f"Failed to load OS modules:\n{msg}")
            self.setCentralWidget(QTextEdit(msg))

    def _do_init(self):
        cw = QWidget(self)
        cw.setObjectName("CentralWidget")
        self.setCentralWidget(cw)
        
        ml = QHBoxLayout(cw)
        ml.setContentsMargins(0,0,0,0)
        ml.setSpacing(0)
        
        sf = QFrame()
        sf.setObjectName("Sidebar")
        sf.setFixedWidth(250)
        sl = QVBoxLayout(sf)
        sl.addWidget(QLabel("Kourosh's Mind Palace", objectName="AppTitle"))
        sl.addSpacing(30)
        
        self.csw = QStackedWidget()
        self.csw.setStyleSheet("background: transparent;")
        
        # --- CRASH-PROOF DYNAMIC LOADING ---
        self.dsh = load_module_safely("tabs.dashboard", "DashboardWidget")
        self.met = load_module_safely("tabs.metrics", "MetricsWidget")
        self.prd = load_module_safely("tabs.productivity", "ProductivityWidget")
        self.crg = load_module_safely("tabs.course_progress", "CourseProgressWidget")
        self.ds_sum = load_module_safely("tabs.day_summary", "DaySummaryWidget")
        self.qz = load_module_safely("tabs.quiz", "QuizEngineWidget")
        self.fl = load_module_safely("tabs.flashcards", "FlashcardWidget")
        self.nt = load_module_safely("tabs.notes", "MarkdownEditorWidget")
        self.lib = load_module_safely("tabs.library", "LibraryWidget")
        self.hlth = load_module_safely("tabs.health", "HealthFitnessWidget")
        self.set = load_module_safely("tabs.settings", "SettingsWidget")
        
        for w in [self.dsh, self.met, self.prd, self.crg, self.ds_sum, self.qz, self.fl, self.nt, self.lib, self.hlth, self.set]: 
            self.csw.addWidget(w)
            
        tabs = ["Dashboard", "Momentum Map", "Productivity Hub", "Course Goals", "Day Summary", "Quiz Engine", "Flashcards", "Notes", "PDF Library", "Health & Fitness", "Settings"]
        for i, t in enumerate(tabs):
            b = QPushButton(t)
            b.setObjectName("NavButton")
            b.clicked.connect(lambda c, idx=i: self.csw.setCurrentIndex(idx))
            sl.addWidget(b)
            
        sl.addStretch()
        ml.addWidget(sf)
        ml.addWidget(self.csw)
        
        # Safely load the Quick Add Dialog Hotkey
        try:
            from ui.dialogs import QuickAddDialog
            self.qa = QuickAddDialog()
            self.qs_hk = QShortcut(QKeySequence("Cmd+Shift+Space"), self)
            self.qs_hk.activated.connect(lambda: (self.qa.show(), self.qa.activateWindow(), self.qa.i.setFocus()))
        except Exception as e:
            print(f"QuickAddDialog unavailable: {e}")
            self.qa = None
        
        self.csw.setCurrentIndex(0)
        
        self.update_background()
        self.ast()

    def update_background(self):
        bg_path = config.get("bg_image_path", "")
        if bg_path and os.path.exists(bg_path):
            try:
                img = QImage()
                img.load(bg_path)
                self.bg_img = img.copy() if not img.isNull() else None
            except: self.bg_img = None
        else:
            self.bg_img = None
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if getattr(self, 'bg_img', None) and not self.bg_img.isNull():
            target_size = self.size()
            scaled_img = self.bg_img.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            dx = (scaled_img.width() - target_size.width()) // 2
            dy = (scaled_img.height() - target_size.height()) // 2
            p.drawImage(0, 0, scaled_img, dx, dy, target_size.width(), target_size.height())
        else:
            grad = QLinearGradient(0, 0, self.width(), self.height())
            grad.setColorAt(0.0, QColor("#1a1a2e"))
            grad.setColorAt(1.0, QColor("#16213e"))
            p.fillRect(self.rect(), grad)
        p.fillRect(self.rect(), QColor(0, 0, 0, 150))
        if getattr(self, 'is_distracted', False): p.fillRect(self.rect(), QColor(255, 0, 0, 80))

    def ast(self):
        f = config.get("font_family", "Helvetica Neue")
        cfp = config.get("custom_font_path", "")
        if cfp and os.path.exists(cfp):
            fid = QFontDatabase.addApplicationFont(cfp)
            if fid != -1:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams: f = fams[0]
        s = config.get("font_size", 16)
        cs = config.get("clock_style", "Analog Classic")
        opac = config.get("panel_opacity", 180)
        df = "'Courier New', monospace" if "LED" in cs else "'Menlo', monospace"
        
        self.setStyleSheet(f"""
            QMainWindow, #CentralWidget {{ background: transparent; }}
            QLabel, QCheckBox, QRadioButton {{ color: #f0f0f5; font-family: '{f}'; font-size: {s}px; }}
            #Sidebar {{ background-color: rgba(15,15,18,200); border-right: 1px solid rgba(255,255,255,15); }}
            #AppTitle {{ font-size: 22px; font-weight: 800; padding: 15px 10px; letter-spacing: 1px; color: white; }}
            #NavButton {{ font-size: 16px; color: #9ca3af; text-align: left; padding: 12px 20px; border: none; background: transparent; font-weight: 500; font-family: '{f}'; }}
            #NavButton:hover {{ background-color: rgba(255,255,255,20); color: #ffffff; border-radius: 8px; }}
            #GlassPanel, #Panel {{ background-color: rgba(30,30,35,{opac}); border-top: 1px solid rgba(255,255,255,45); border-left: 1px solid rgba(255,255,255,25); border-bottom: 1px solid rgba(255,255,255,10); border-right: 1px solid rgba(255,255,255,10); border-radius: 16px; }}
            #DigitalTimeText, #TimeText, #RealDigitalClock {{ font-family: {df}; }}
            #QuoteText {{ font-family: 'Georgia'; font-style: italic; color: #cccccc; font-size: 18px; }}
            QPushButton {{ background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,40), stop:1 rgba(255,255,255,10)); color: white; border-top: 1px solid rgba(255,255,255,60); border-left: 1px solid rgba(255,255,255,40); border-bottom: 1px solid rgba(255,255,255,15); border-right: 1px solid rgba(255,255,255,15); border-radius: 10px; padding: 10px 18px; font-weight: 700; font-family: '{f}'; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
            QPushButton:hover {{ background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,60), stop:1 rgba(255,255,255,20)); border-top: 1px solid rgba(255,255,255,90); }}
            #DangerButton {{ background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,69,58,150), stop:1 rgba(255,69,58,80)); }}
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget, QCalendarWidget {{ background-color: rgba(10,10,15,160); color: #e5e7eb; border-top: 1px solid rgba(0,0,0,80); border-radius: 8px; padding: 10px; font-family: '{f}'; font-size: {s}px; }}
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MindPalaceOS()
    w.show()
    sys.exit(app.exec())