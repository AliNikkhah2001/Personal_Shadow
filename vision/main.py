import sys, os
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer, QObject, QEvent, QPoint, QRect
from PyQt6.QtGui import QKeySequence, QShortcut, QImage, QPainter, QPainterPath, QColor, QLinearGradient, QPen, QFontDatabase

from core.config import config
from core.signals import bus
from workers.api_worker import ApiWorker

from ui.dialogs import QuickAddDialog
from ui.tabs.dashboard import DashboardWidget
from ui.tabs.metrics import MetricsWidget
from ui.tabs.productivity import ProductivityWidget
from ui.tabs.course_progress import CourseProgressWidget
from ui.tabs.life_architecture import LifeArchitectureWidget
from ui.tabs.habits import HabitsWidget
from ui.tabs.day_summary import DaySummaryWidget
from ui.tabs.quiz import QuizEngineWidget
from ui.tabs.flashcards import FlashcardWidget
from ui.tabs.notes import MarkdownEditorWidget
from ui.tabs.settings import SettingsWidget

class GlassmorphismFilter(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Paint and isinstance(obj, QFrame):
            obj_name = obj.objectName()
            if obj_name in ["GlassPanel", "Panel", "Sidebar"]:
                p = QPainter(obj)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # 1. Native Background Blur Mapping
                if getattr(self.mw, 'blurred_bg', None) and not self.mw.blurred_bg.isNull():
                    mapped_pt = obj.mapTo(self.mw, QPoint(0, 0))
                    target_rect = QRect(mapped_pt.x(), mapped_pt.y(), obj.width(), obj.height())
                    
                    path = QPainterPath()
                    rad = 0 if obj_name == "Sidebar" else 14
                    path.addRoundedRect(0, 0, obj.width(), obj.height(), rad, rad)
                    p.setClipPath(path)
                    p.drawImage(0, 0, self.mw.blurred_bg, target_rect.x(), target_rect.y(), target_rect.width(), target_rect.height())
                    p.setClipping(False)
                    
                # 2. Acrylic Tint Layer
                opac = int(config.get("panel_opacity", 180))
                p.setBrush(QColor(30, 32, 42, opac))
                p.setPen(QPen(QColor(255, 255, 255, 30), 1))
                rad = 0 if obj_name == "Sidebar" else 14
                p.drawRoundedRect(0, 0, obj.width(), obj.height(), rad, rad)
                
                # 3. Ambient Frost Edge Highlight
                if obj_name != "Sidebar":
                    p.setPen(QPen(QColor(255, 255, 255, 60), 1.5))
                    p.drawLine(14, 0, obj.width() - 14, 0)
                    
                p.end()
                return True # We fully handled the painting!
        return super().eventFilter(obj, event)

class MindPalaceOS(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kourosh's Mind Palace - Master Build")
        self.resize(1450, 950)
        
        self.bg_img = None
        self.blurred_bg = None
        self.is_distracted = False
        
        # Install the global glass filter!
        self.glass_filter = GlassmorphismFilter(self)
        QApplication.instance().installEventFilter(self.glass_filter)
        
        cw = QWidget(self)
        self.setCentralWidget(cw)
        ml = QHBoxLayout(cw)
        ml.setContentsMargins(0,0,0,0)
        ml.setSpacing(0)
        
        sf = QFrame()
        sf.setFixedWidth(260)
        sf.setObjectName("Sidebar")
        sl = QVBoxLayout(sf)
        sl.setContentsMargins(15, 20, 15, 20)
        
        title = QLabel("Mind Palace OS")
        title.setStyleSheet("font-size: 26px; font-weight: 800; color: white; padding-bottom: 20px;")
        sl.addWidget(title)
        
        self.csw = QStackedWidget()
        self.csw.setObjectName("MainContent")
        
        tabs = [
            ("Dashboard", DashboardWidget()),
            ("Momentum Map", MetricsWidget()),
            ("Productivity Hub", ProductivityWidget()),
            ("Course Goals", CourseProgressWidget()),
            ("Life Architecture", LifeArchitectureWidget()),
            ("Habit Matrix", HabitsWidget()),
            ("Day Summary", DaySummaryWidget()),
            ("Quiz Engine", QuizEngineWidget()),
            ("Flashcards", FlashcardWidget()),
            ("Notes", MarkdownEditorWidget()),
            ("Settings", SettingsWidget())
        ]
        
        for i, (name, widget) in enumerate(tabs):
            self.csw.addWidget(widget)
            btn = QPushButton(name)
            btn.setObjectName("NavBtn")
            btn.clicked.connect(lambda _, idx=i: self.csw.setCurrentIndex(idx))
            sl.addWidget(btn)
            
        sl.addStretch()
        ml.addWidget(sf)
        ml.addWidget(self.csw)
        
        self.qa = QuickAddDialog()
        self.qs_hk = QShortcut(QKeySequence("Cmd+Shift+Space"), self)
        self.qs_hk.activated.connect(lambda: (self.qa.show(), self.qa.activateWindow(), self.qa.i.setFocus()))
        
        self.csw.setCurrentIndex(0)
        
        bus.attention_alert.connect(self.trs)
        bus.settings_changed.connect(self.ast)
        
        self.sth()
        self.ast()

    def trs(self, mode):
        self.is_distracted = (mode != "None")
        self.update()

    def apply_downloaded_bg(self, data):
        if not config.get("bg_image_path", ""):
            self.apply_bg(data)

    def sth(self):
        self.aw = ApiWorker()
        self.aw.quote_fetched.connect(self.dsh.set_quote)
        self.aw.image_fetched.connect(self.apply_downloaded_bg)
        self.aw.start()
        self.update_background()

    def update_blur(self):
        if getattr(self, 'bg_img', None) and not self.bg_img.isNull() and self.width() > 0 and self.height() > 0:
            w, h = max(1, self.width() // 16), max(1, self.height() // 16)
            scaled_down = self.bg_img.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self.blurred_bg = scaled_down.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        else:
            self.blurred_bg = None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.update_blur()

    def apply_bg(self, source):
        try:
            img = QImage()
            if isinstance(source, bytes): img.loadFromData(source)
            elif isinstance(source, str) and os.path.exists(source): img.load(source)
            else: 
                self.bg_img = None
                self.update_blur()
                self.update()
                return

            if not img.isNull():
                self.bg_img = img.copy()
            else:
                self.bg_img = None
        except:
            self.bg_img = None
            
        self.update_blur()
        self.update()

    def update_background(self):
        bg_path = config.get("bg_image_path", "")
        if bg_path and os.path.exists(bg_path):
            self.apply_bg(bg_path)
        else:
            self.bg_img = None
            self.update_blur()
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
            grad.setColorAt(0.0, QColor(13, 13, 18))
            grad.setColorAt(1.0, QColor(22, 33, 62))
            p.fillRect(self.rect(), grad)
            
        p.fillRect(self.rect(), QColor(0, 0, 0, 150))
        
        if getattr(self, 'is_distracted', False):
            p.fillRect(self.rect(), QColor(255, 0, 0, 80))

    def ast(self):
        f = config.get("font_family", "Helvetica Neue")
        cfp = config.get("custom_font_path", "")
        
        if cfp and os.path.exists(cfp):
            fid = QFontDatabase.addApplicationFont(cfp)
            if fid != -1:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    f = fams[0]

        s = config.get("font_size", 16)
        cs = config.get("clock_style", "Analog Classic")
        df = "'Courier New', monospace" if "LED" in cs else "'Menlo', monospace"
        
        self.update_background()
        
        self.setStyleSheet(f"""
            QMainWindow, #MainContent {{ 
                background: transparent; 
            }}
            #Sidebar, #GlassPanel, #Panel {{ 
                background: transparent; 
                border: none; 
            }}
            QLabel, QCheckBox, QRadioButton {{ 
                color: #f3f4f6; 
                background: transparent;
                font-family: '{f}', Arial, sans-serif;
                font-size: {s}px;
            }}
            #NavBtn {{ 
                text-align: left; 
                padding: 12px 16px; 
                font-size: 15px; 
                font-weight: 600;
                color: #9ca3af; 
                background: transparent; 
                border: none; 
                border-radius: 8px;
            }}
            #NavBtn:hover {{ 
                background-color: rgba(255,255,255,10); 
                color: #ffffff; 
            }}
            QPushButton {{ 
                background-color: rgba(255, 255, 255, 12); 
                color: white; 
                border: 1px solid rgba(255, 255, 255, 25); 
                border-radius: 8px; 
                padding: 8px 16px; 
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: rgba(255, 255, 255, 25); border: 1px solid rgba(255, 255, 255, 40); }}
            QPushButton:pressed {{ background-color: rgba(255, 255, 255, 5); }}
            #DangerButton {{ background-color: rgba(255, 59, 48, 180); border-color: rgba(255, 59, 48, 255); }}
            #DangerButton:hover {{ background-color: rgba(255, 59, 48, 220); }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateTimeEdit {{ 
                background-color: #1a1a24; 
                color: #ffffff; 
                border: 1px solid rgba(255, 255, 255, 20); 
                border-radius: 6px; 
                padding: 6px 10px; 
                selection-background-color: #0a84ff;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{ background-color: #1a1a24; color: white; border: 1px solid rgba(255,255,255,20); selection-background-color: #0a84ff; }}
            QListWidget, QTreeWidget, QTableWidget, QTextEdit {{ 
                background-color: rgba(20, 20, 26, 200); 
                color: #e5e7eb; 
                border: 1px solid rgba(255, 255, 255, 15); 
                border-radius: 8px; 
                padding: 5px;
            }}
            QHeaderView::section {{ background-color: #15151a; color: white; padding: 5px; border: 1px solid rgba(255,255,255,10); }}
            QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: rgba(255,255,255,30); min-height: 20px; border-radius: 6px; margin: 2px; }}
            QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,50); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0px; }}
            QScrollBar::handle:horizontal {{ background: rgba(255,255,255,30); min-width: 20px; border-radius: 6px; margin: 2px; }}
            QScrollBar::handle:horizontal:hover {{ background: rgba(255,255,255,50); }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
            #DigitalTimeText, #TimeText, #RealDigitalClock {{ font-family: {df}; }}
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MindPalaceOS()
    w.show()
    sys.exit(app.exec())