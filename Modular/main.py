import contextlib
import json
import logging
import os
import re
import sys
from datetime import datetime

import git
import matplotlib
import requests
import urllib3

matplotlib.use("Agg")
from PyQt6.QtCore import Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QProgressBar, QVBoxLayout, QWidget

# Force Python to look in the current directory for custom modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core_sys import CACHE_DIR, config
from sync_manager import SyncManager
from system_bridge import SystemBridge

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- AUTOMATIC GLOBAL AUDIT LOGGING ---
logging.basicConfig(
    filename="mindpalace_audit.log",
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s [%(threadName)s] %(levelname)s - %(message)s",
)


def global_audit_tracer(frame, event, arg):
    if event == "call":
        filename = frame.f_code.co_filename
        # Only log our own files to prevent spamming PyQt internals
        if "main.py" in filename or "system_bridge.py" in filename:
            func_name = frame.f_code.co_name
            # Exclude very high-frequency loops like tick() and UI paints
            if not func_name.startswith("<") and func_name not in [
                "tick",
                "chk_fcs",
                "process",
                "paintEvent",
                "update_frame",
            ]:
                logging.debug(f"CALL: {func_name} (Line {frame.f_lineno} in {os.path.basename(filename)})")
    return global_audit_tracer


if os.getenv("MINDPALACE_TRACE") == "1":
    sys.setprofile(global_audit_tracer)
# --------------------------------------


class DownloaderThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def run(self):
        dirs = ["js", "css", "webfonts", "img"]
        for d in dirs:
            os.makedirs(os.path.join(CACHE_DIR, d), exist_ok=True)

        assets = [
            ("js/react.js", "https://unpkg.com/react@18/umd/react.production.min.js"),
            ("js/react-dom.js", "https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"),
            ("js/babel.js", "https://unpkg.com/@babel/standalone/babel.min.js"),
            ("js/tailwind.js", "https://cdn.tailwindcss.com"),
            ("js/marked.js", "https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
            ("js/chart.umd.js", "https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"),
            ("js/three.module.js", "https://unpkg.com/three@0.160.0/build/three.module.js"),
            ("css/all.min.css", "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"),
            (
                "webfonts/fa-solid-900.woff2",
                "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2",
            ),
            (
                "webfonts/fa-regular-400.woff2",
                "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-regular-400.woff2",
            ),
            (
                "webfonts/fa-brands-400.woff2",
                "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-brands-400.woff2",
            ),
        ]

        for i, (path, url) in enumerate(assets):
            target = os.path.join(CACHE_DIR, path)
            if not os.path.exists(target):
                self.status.emit(f"Caching {path.split('/')[-1]}...")
                try:
                    r = requests.get(url, timeout=15)
                    with open(target, "wb") as f:
                        f.write(r.content)
                except Exception:
                    pass
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
                    fname = url.split("/")[-1]
                    wpath = os.path.join(CACHE_DIR, "webfonts", fname)
                    if not os.path.exists(wpath):
                        self.status.emit(f"Downloading font {fname}...")
                        wr = requests.get(url, headers=headers, timeout=15)
                        with open(wpath, "wb") as f:
                            f.write(wr.content)
                    css_content = css_content.replace(url, f"../webfonts/{fname}")
                with open(css_path, "w") as f:
                    f.write(css_content)
            except Exception:
                pass

        self.progress.emit(100)
        self.status.emit("Booting Mind Palace OS...")
        self.finished.emit()


class SyncProgressThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str, dict)

    def __init__(self, device_id, repo_path):
        super().__init__()
        self.device_id = device_id
        self.repo_path = repo_path

    def run(self):
        try:
            self.status.emit("Checking Git upstream...")
            self.progress.emit(10)

            if not os.path.exists(self.repo_path):
                self.finished.emit(False, "Sync repo not found", {})
                return

            repo = git.Repo(self.repo_path)
            origin = repo.remotes.origin

            self.status.emit("Fetching all remote data...")
            self.progress.emit(20)
            origin.fetch(progress=DetailedSyncProgress())

            self.status.emit("Pulling latest from all devices...")
            self.progress.emit(30)
            origin.pull(rebase=False, progress=DetailedSyncProgress())

            self.status.emit("Merging data from all devices...")
            self.progress.emit(50)

            sync_manager = SyncManager(self.device_id)
            sync_manager.repo = repo
            sync_manager.repo_path = self.repo_path

            self.status.emit("Applying remote changes & deletions...")
            self.progress.emit(60)
            sync_manager.ensure_uuids_and_timestamps()
            sync_manager.merge_all_remote_data()

            self.status.emit("Exporting local changes...")
            self.progress.emit(75)
            local_data = sync_manager.export_local_data()
            export_path = os.path.join(self.repo_path, sync_manager.sync_data_file)
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            with open(export_path, "w") as f:
                json.dump(local_data, f, indent=2)

            self.status.emit("Syncing files...")
            self.progress.emit(85)
            with contextlib.suppress(BaseException):
                sync_manager.sync_files()

            self.status.emit("Pushing merged data to remote...")
            self.progress.emit(90)
            repo.git.add(export_path, force=True)
            repo.git.add(all=True)

            if repo.is_dirty() or repo.untracked_files:
                repo.index.commit(f"Full sync from {self.device_id}")
                origin.push(progress=DetailedSyncProgress())

            self.status.emit("Sync completed - all devices up to date")
            self.progress.emit(100)

            last_activity = f"Full sync completed at {datetime.now().strftime('%H:%M:%S')}"
            sync_info = {
                "last_activity": last_activity,
                "last_device": self.device_id,
                "device_id": self.device_id,
                "repo_path": self.repo_path,
            }
            self.finished.emit(True, "Full sync complete", sync_info)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit(False, f"Sync error: {e!s}", {})


class DetailedSyncProgress(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=""):
        pass


class SplashScreen(QWidget):
    def __init__(self, show_sync=True):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(500, 220)
        self.setStyleSheet("background-color: #0a0a0f; color: #e2e8f0; border: 1px solid #1e1e2b; border-radius: 12px;")
        self.show_sync = show_sync

        lay = QVBoxLayout(self)
        self.title_lbl = QLabel("Mind Palace OS", alignment=Qt.AlignmentFlag.AlignCenter)
        self.title_lbl.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color: #3b82f6;")

        self.lbl = QLabel("Initializing...", alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl.setFont(QFont("Arial", 11))
        self.lbl.setWordWrap(True)

        self.device_lbl = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.device_lbl.setFont(QFont("Arial", 9))
        self.device_lbl.setStyleSheet("color: #64748b;")

        self.activity_lbl = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.activity_lbl.setFont(QFont("Arial", 9))
        self.activity_lbl.setStyleSheet("color: #64748b;")

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.pbar.setStyleSheet(
            "QProgressBar { border: 1px solid #1e1e2b; border-radius: 6px; text-align: center; background-color: #14141d; color: white; font-weight: bold; } QProgressBar::chunk { background-color: #3b82f6; border-radius: 5px; }"
        )

        lay.addStretch()
        lay.addWidget(self.title_lbl)
        lay.addSpacing(8)
        lay.addWidget(self.lbl)
        lay.addSpacing(4)
        lay.addWidget(self.device_lbl)
        lay.addWidget(self.activity_lbl)
        lay.addSpacing(15)
        lay.addWidget(self.pbar)
        lay.addStretch()

    def start_sync_check(self, device_id, repo_path):
        self.sync_thread = SyncProgressThread(device_id, repo_path)
        self.sync_thread.progress.connect(self.pbar.setValue)
        self.sync_thread.status.connect(self.lbl.setText)
        self.sync_thread.finished.connect(self.on_sync_finished)
        self.sync_thread.start()

    def on_sync_finished(self, success, message, sync_info):
        if success:
            self.lbl.setText("Ready to launch")
            if sync_info.get("device_id"):
                self.device_lbl.setText(f"Device: {sync_info['device_id'][:8]}...")
            if sync_info.get("last_activity"):
                self.activity_lbl.setText(f"Last Activity: {sync_info['last_activity']}")
        else:
            self.lbl.setText(f"Sync failed: {message}")
            self.device_lbl.setText("Running in offline mode")

        QTimer.singleShot(1500, self.launch_main)

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

        # Load the sleek SVG logo
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.browser = QWebEngineView()
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        self.channel = QWebChannel()
        self.bridge = SystemBridge()
        self.channel.registerObject("backend", self.bridge)
        self.browser.page().setWebChannel(self.channel)

        with open("frontend/index.html", encoding="utf-8") as f:
            html_content = f.read()

        base_url = QUrl.fromLocalFile(os.path.abspath(".") + os.sep)
        self.browser.setHtml(html_content, base_url)
        self.setCentralWidget(self.browser)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    app.setStyle("Fusion")

    sync_manager = SyncManager()
    device_id = sync_manager.device_id
    repo_path = sync_manager.repo_path

    cache_exists = os.path.exists(os.path.join(CACHE_DIR, "js", "react.js"))
    repo_exists = os.path.exists(repo_path)
    sync_enabled = config.get("sync_enabled", False)

    if not cache_exists:
        splash = SplashScreen(show_sync=False)
        splash.show()
        splash.start_download()
    elif repo_exists and sync_enabled:
        splash = SplashScreen(show_sync=True)
        splash.show()
        splash.start_sync_check(device_id, repo_path)
    else:
        w = MindPalaceWebOS()
        w.show()

    sys.exit(app.exec())