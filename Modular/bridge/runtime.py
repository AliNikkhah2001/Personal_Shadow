"""Runtime services shared by the system bridge."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import threading
import uuid
import zipfile
from datetime import datetime, timedelta

from PyQt6.QtWidgets import QApplication

from core_logger import logger
from core_sys import config, db


class RuntimeServicesMixin:
    """Logging, device integration, monitoring, backup, and query helpers."""

    def log_activity(self, module, desc):
        try:
            now = datetime.now().isoformat()
            db.c.execute(
                "INSERT INTO activity_logs (timestamp, module, description, uuid, modified_at) VALUES (?, ?, ?, ?, ?)",
                (now, module, desc, uuid.uuid4().hex, now),
            )
            db.safe_commit()
        except Exception:
            logger.exception("Failed to log activity")

    def handle_sync_progress(self, msg):
        print(f"[SyncManager] {msg}")
        self.sync_progress.emit(msg)

    def handle_sync_completed(self, success, msg):
        status = "SUCCESS" if success else "FAILED"
        print(f"[SyncManager] {status}: {msg}")
        config.set("git_status", "connected" if success else "error")
        config.set("git_last_sync", datetime.now().isoformat())
        self.sync_completed.emit(success, msg)
        if success:
            self.log_activity("Sync", f"Successfully synced with Git cluster. {msg}")
        else:
            self.log_activity("Sync Error", f"Sync failed: {msg}")

    def handle_attention(self, att):
        self.current_att = att

    def emit_video_frame(self, b64):
        if getattr(self, "feed_active", False):
            self.video_feed.emit(b64)

    def check_auto_scans(self):
        def worker():
            for f in os.listdir(self.scan_dir):
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    img_path = os.path.join(self.scan_dir, f)
                    try:
                        from health_parser import BodyScanParser

                        parser = BodyScanParser(rois_file="rois.json")
                        data = parser.parse_image(img_path)
                    except Exception as e:
                        print("Parse error", e)
                        continue

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    arch_path = os.path.join(self.archive_dir, f"scan_{timestamp}_{f}")
                    os.rename(img_path, arch_path)

                    if data:
                        data["file_path"] = arch_path
                        self.log_activity("Scanner", f"Auto-parsed body scan: {f}")
                        self.scan_ready.emit(json.dumps(data))

        threading.Thread(target=worker, daemon=True).start()

    def handle_sync_result(self, success, msg):
        if not success:
            QApplication.beep()

    def play_sound(self, sound_type="app"):
        if config.get("mute_sounds", False) or config.get("quiet_mode", False):
            return
        sound_name = config.get(f"sound_{sound_type}_dist", "Basso" if sound_type == "cam" else "Ping")
        if sys.platform == "darwin":
            path = f"/System/Library/Sounds/{sound_name}.aiff"
            if os.path.exists(path):
                subprocess.Popen(["afplay", path])
            else:
                QApplication.beep()
        elif sys.platform == "win32":
            try:
                import winsound

                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                QApplication.beep()
        else:
            QApplication.beep()

    def speak(self, text):
        if config.get("mute_speech", False) or config.get("quiet_mode", False):
            return
        if not hasattr(self, "last_speak_time") or (datetime.now() - self.last_speak_time).total_seconds() > 10:
            self.last_speak_time = datetime.now()
            if sys.platform == "darwin":
                subprocess.Popen(["say", text])
            elif sys.platform == "win32":
                try:
                    import pyttsx3

                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                except ImportError:
                    pass
            else:
                subprocess.Popen(["espeak", text], stderr=subprocess.DEVNULL)

    def set_max_volume(self):
        if sys.platform == "darwin":
            if not hasattr(self, "last_vol_time") or (datetime.now() - self.last_vol_time).total_seconds() > 10:
                self.last_vol_time = datetime.now()
                with contextlib.suppress(Exception):
                    subprocess.Popen(["osascript", "-e", "set volume output volume 100"])

    def get_running_processes(self):
        processes = []
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "name", "exe", "cpu_percent", "memory_percent", "create_time"]):
                with contextlib.suppress(Exception):
                    processes.append(
                        {
                            "pid": proc.info["pid"],
                            "name": proc.info["name"],
                            "cpu": proc.info["cpu_percent"] or 0,
                            "memory": proc.info["memory_percent"] or 0,
                        }
                    )
            processes.sort(key=lambda x: x["cpu"], reverse=True)
            return processes
        except ImportError:
            if sys.platform == "win32":
                try:
                    res = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True)
                    for line in res.stdout.strip().split("\n"):
                        parts = line.strip('"').split('","')
                        if len(parts) >= 2:
                            processes.append({"pid": parts[1], "name": parts[0], "cpu": 0, "memory": 0})
                except Exception:
                    pass
        return processes

    def check_processes_for_distraction(self):
        if not config.get("app_monitoring_enabled", False):
            return []
        allowed = config.get("allowed_apps", [])
        blocked = config.get("blocked_apps", [])
        if not blocked and not allowed:
            return []
        running = self.get_running_processes()
        distractions = []
        for proc in running:
            proc_name = proc["name"].lower()
            if blocked:
                for blocked_app in blocked:
                    if blocked_app.lower() in proc_name:
                        distractions.append(proc)
                        break
            elif allowed:
                is_allowed = False
                for allowed_app in allowed:
                    if allowed_app.lower() in proc_name:
                        is_allowed = True
                        break
                if not is_allowed:
                    distractions.append(proc)
        return distractions

    def kill_processes(self, processes):
        try:
            import psutil

            for proc in processes[:3]:
                with contextlib.suppress(Exception):
                    psutil.Process(proc["pid"]).terminate()
        except Exception:
            pass

    def auto_sync(self):
        if config.get("sync_enabled", False):
            threading.Thread(target=self.sync_manager.sync, daemon=True).start()

    def backup_data(self):
        backup_dir = os.path.join(os.path.expanduser("~"), "MindPalaceBackups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"auto_backup_{timestamp}.zip")
        settings = config.cfg.copy()
        settings.pop("sync_github_token", None)
        data = {"settings": settings, "tables": {}}
        tables = [
            "courses",
            "pomodoro_sessions",
            "cascading_goals",
            "habits",
            "habit_logs",
            "flashcards",
            "quizzes",
            "focus_queue",
            "notes",
            "health_profile",
            "health_logs",
            "custom_foods",
            "custom_activities",
            "health_plans",
        ]
        for table in tables:
            try:
                db.c.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in db.c.description]
                data["tables"][table] = [dict(zip(columns, row, strict=False)) for row in db.c.fetchall()]
            except Exception:
                pass
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("data.json", json.dumps(data, indent=2))
        with open(backup_path, "wb") as f:
            f.write(zip_buffer.getvalue())

    def get_goals_tree(self):
        try:
            db.c.execute("SELECT id, parent_id, title, target_hours, deadline FROM cascading_goals")
            return [
                {"id": r[0], "parent_id": r[1], "title": r[2], "target_hours": r[3], "deadline": r[4]}
                for r in db.c.fetchall()
            ]
        except Exception:
            return []

    def get_flat_goals(self):
        try:
            db.c.execute("SELECT id, parent_id, title FROM cascading_goals")
            tree = {r[0]: {"parent": r[1], "title": r[2]} for r in db.c.fetchall()}
            paths = []
            for _gid, data in tree.items():
                path = [data["title"]]
                curr = data["parent"]
                while curr in tree:
                    path.insert(0, tree[curr]["title"])
                    curr = tree[curr]["parent"]
                paths.append(" > ".join(path))
            return sorted(paths)
        except Exception:
            return []

    def get_studied_hours_per_goal(self, date_filter=None):
        try:
            db.c.execute("SELECT id, parent_id, title FROM cascading_goals")
            all_goals = db.c.fetchall()
            if not all_goals:
                return {}

            goal_by_title = {title: gid for gid, _pid, title in all_goals}
            title_to_gid = goal_by_title
            gid_to_parent = {gid: pid for gid, pid, _title in all_goals}

            children_map = {}
            for gid, pid, title in all_goals:
                goal_titles = set()
                goal_titles.add(title)
                if pid not in children_map:
                    children_map[pid] = []
                children_map[pid].append(title)

            if date_filter:
                db.c.execute(
                    "SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=? GROUP BY course",
                    (date_filter,),
                )
            else:
                db.c.execute(
                    "SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY course"
                )
            course_hours = {r[0]: (r[1] or 0) / 60.0 for r in db.c.fetchall()}

            def get_descendant_titles(parent_id):
                titles = []
                for child_title in children_map.get(parent_id, []):
                    titles.append(child_title)
                    child_id = title_to_gid.get(child_title)
                    if child_id is not None:
                        titles.extend(get_descendant_titles(child_id))
                return titles

            def hours_for_title(title):
                total = 0.0
                for course, hrs in course_hours.items():
                    if course == title or course.endswith(" > " + title):
                        total += hrs
                return total

            result = {}
            for gid, pid, title in all_goals:
                total = hours_for_title(title)
                for desc_title in get_descendant_titles(gid):
                    total += hours_for_title(desc_title)
                result[title] = total

            for course_name, hours in course_hours.items():
                leaf = course_name.rsplit(" > ", 1)[-1]
                if course_name not in result and leaf not in result:
                    result[course_name] = hours

            return result
        except Exception:
            return {}

    def get_heatmap_data(self):
        weeks = 28
        matrix = [[0] * 7 for _ in range(weeks)]
        td = datetime.now().date()
        try:
            db.c.execute(
                "SELECT date(timestamp), sum(duration) FROM pomodoro_sessions WHERE type='Work' GROUP BY date(timestamp)"
            )
            history = {r[0]: r[1] / 60.0 for r in db.c.fetchall()}
            for week in range(weeks):
                for day in range(7):
                    target_date = (td - timedelta(days=(weeks - week - 1) * 7 + (6 - day))).isoformat()
                    hrs = history.get(target_date, 0)
                    intensity = 0
                    if hrs > 0:
                        intensity = 1
                    if hrs > 2:
                        intensity = 2
                    if hrs > 4:
                        intensity = 3
                    if hrs > 6:
                        intensity = 4
                    matrix[week][day] = intensity
            return matrix
        except Exception:
            return matrix

    def get_cluster_master(self):
        cluster_file = os.path.join(self.sync_manager.repo_path, "cluster_state.json")
        if os.path.exists(cluster_file):
            try:
                with open(cluster_file) as f:
                    return json.load(f).get("master_id")
            except Exception:
                pass
        return None
