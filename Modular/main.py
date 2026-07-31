import sys
import os
import requests
import re
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QProgressBar
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from core_sys import CACHE_DIR
from system_bridge import SystemBridge

class DownloaderThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def run(self):
        dirs = ['js', 'css', 'webfonts', 'img']
        for d in dirs: os.makedirs(os.path.join(CACHE_DIR, d), exist_ok=True)

        assets = [
            ("js/react.js", "https://unpkg.com/react@18/umd/react.production.min.js"),
            ("js/react-dom.js", "https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"),
            ("js/babel.js", "https://unpkg.com/@babel/standalone/babel.min.js"),
            ("js/tailwind.js", "https://cdn.tailwindcss.com"),
            ("js/marked.js", "https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
            ("css/all.min.css", "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"),
            ("webfonts/fa-solid-900.woff2", "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2"),
            ("webfonts/fa-regular-400.woff2", "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-regular-400.woff2"),
            ("webfonts/fa-brands-400.woff2", "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-brands-400.woff2")
        ]

        for i, (path, url) in enumerate(assets):
            target = os.path.join(CACHE_DIR, path)
            if not os.path.exists(target):
                self.status.emit(f"Caching {path.split('/')[-1]}...")
                try:
                    r = requests.get(url, timeout=15)
                    with open(target, 'wb') as f: f.write(r.content)
                except: pass
            self.progress.emit(int(((i + 1) / len(assets)) * 70))

        self.status.emit("Verifying Fonts...")
        css_path = os.path.join(CACHE_DIR, "css", "fonts.css")
        if not os.path.exists(css_path):
            font_url = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Cinzel:wght@600;800&display=swap"
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(font_url, headers=headers, timeout=15)
                css_content = r.text
                urls = re.findall(r'url\([\'"]?(https://[^\'")]+)[\'"]?\)', css_content)
                for url in set(urls):
                    fname = url.split('/')[-1]
                    wpath = os.path.join(CACHE_DIR, 'webfonts', fname)
                    if not os.path.exists(wpath):
                        self.status.emit(f"Downloading font {fname}...")
                        wr = requests.get(url, headers=headers, timeout=15)
                        with open(wpath, 'wb') as f: f.write(wr.content)
                    css_content = css_content.replace(url, f"../webfonts/{fname}")
                with open(css_path, 'w') as f: f.write(css_content)
            except: pass
            
        self.progress.emit(100)
        self.status.emit("Booting Mind Palace OS...")
        self.finished.emit()

class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(450, 160)
        self.setStyleSheet("background-color: #0a0a0f; color: #e2e8f0; border: 1px solid #1e1e2b; border-radius: 12px;")
        
        lay = QVBoxLayout(self)
        self.lbl = QLabel("Initializing Mind Palace OS Offline Cache...", alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100); self.pbar.setValue(0)
        self.pbar.setStyleSheet("QProgressBar { border: 1px solid #1e1e2b; border-radius: 6px; text-align: center; background-color: #14141d; color: white; font-weight: bold; } QProgressBar::chunk { background-color: #3b82f6; border-radius: 5px; }")
        lay.addStretch(); lay.addWidget(self.lbl); lay.addSpacing(15); lay.addWidget(self.pbar); lay.addStretch()

    def start_download(self):
        self.thread = DownloaderThread()
        self.thread.progress.connect(self.pbar.setValue)
        self.thread.status.connect(self.lbl.setText)
        self.thread.finished.connect(self.launch_main)
        self.thread.start()

    def launch_main(self):
        self.main_window = MindPalaceWebOS()
        self.main_window.show()
        self.close()

class MindPalaceWebOS(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shadow OS - Master Architecture")
        self.resize(1400, 900)
        
        self.browser = QWebEngineView()
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        self.channel = QWebChannel()
        self.bridge = SystemBridge()
        self.channel.registerObject("backend", self.bridge)
        self.browser.page().setWebChannel(self.channel)
        
        with open("index.html", "r", encoding="utf-8") as f: html_content = f.read()
        base_url = QUrl.fromLocalFile(os.path.abspath(CACHE_DIR) + os.sep)
        self.browser.setHtml(html_content, base_url)
        self.setCentralWidget(self.browser)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = SplashScreen()
    splash.show()
    splash.start_download()
    sys.exit(app.exec())