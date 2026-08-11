"""Focus timer and session behavior for the system bridge."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from core_sys import config, db


class SessionMixin:
    """Manage timer state, distraction tracking, and session persistence."""

    def push_state(self, dist_mode="None"):
        mins, secs = divmod(self.time_left, 60)
        time_str = f"{mins:02d}:{secs:02d}"
        pct = 100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0

        self.ovl.update_state(
            time_str,
            pct,
            (self.total_time - self.time_left) // 60,
            self.total_time // 60,
            self.current_course,
            dist_mode,
        )

        try:
            db.c.execute("SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id")
            queue_data = [
                {"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]}
                for r in db.c.fetchall()
            ]
        except Exception:
            queue_data = []

        state = {
            "is_running": self.is_running,
            "time_str": time_str,
            "progress": pct,
            "distractions": self.distractions,
            "distraction_markers": self.distraction_markers,
            "distraction_log": self.distraction_log,
            "course": self.current_course,
            "active_queue_id": self.active_queue_id,
            "queue": queue_data,
            "time_left": self.time_left,
            "total_time": self.total_time,
            "last_completed_session_id": self.last_completed_session_id,
            "last_session_data": getattr(self, "last_session_data", None),
        }
        self.state_update.emit(json.dumps(state))

    def tick(self):
        if not self.is_running:
            return

        dist_mode = "None"

        if not config.get("quiet_mode", False) and not getattr(self, "current_att", True):
            self.distractions += 1
            dist_mode = "Camera"
            self.distraction_markers.append(
                100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0
            )
            if self.distractions % 5 == 0:
                self.set_max_volume()
                self.play_sound("cam")

        if config.get("app_monitoring_enabled", False):
            app_distractions = self.check_processes_for_distraction()
            if app_distractions:
                if dist_mode == "None":
                    dist_mode = "App"
                    self.distractions += 1
                    self.distraction_markers.append(
                        100 - int((self.time_left / self.total_time) * 100) if self.total_time > 0 else 0
                    )
                if config.get("auto_block", False):
                    self.kill_processes(app_distractions)

        if dist_mode != "None":
            if not self.was_distracted:
                self.distraction_start = self.total_time - self.time_left
                self.was_distracted = True
                self.distraction_type_current = dist_mode
        elif self.was_distracted:
            dur = (self.total_time - self.time_left) - self.distraction_start
            self.distraction_log.append(
                [
                    self.distraction_start / 60.0,
                    dur / 60.0,
                    self.distraction_type_current,
                ]
            )
            self.was_distracted = False

        if self.time_left > 0:
            self.time_left -= 1

        if self.time_left == 0:
            self._complete_session()

        self.push_state(dist_mode)

    def _complete_session(self):
        """Handle session completion logic."""
        if not config.get("quiet_mode", False):
            self.speak(config.get("speech_comp", "Session Complete."))

        if self.was_distracted:
            dur = (self.total_time - self.time_left) - self.distraction_start
            self.distraction_log.append(
                [
                    self.distraction_start / 60.0,
                    dur / 60.0,
                    self.distraction_type_current,
                ]
            )
            self.was_distracted = False

        final_tl_path = getattr(self.vision, "v_path", "")

        try:
            db.c.execute(
                """INSERT INTO pomodoro_sessions
                   (course, duration, actual_duration, timestamp, type, distractions, distraction_data, timelapse_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.current_course,
                    self.total_time // 60,
                    self.total_time // 60,
                    datetime.now().isoformat(),
                    "Work",
                    self.distractions,
                    json.dumps(self.distraction_log),
                    final_tl_path,
                ),
            )
        except sqlite3.OperationalError:
            db.c.execute(
                """INSERT INTO pomodoro_sessions
                   (course, duration, actual_duration, timestamp, type, distractions)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    self.current_course,
                    self.total_time // 60,
                    self.total_time // 60,
                    datetime.now().isoformat(),
                    "Work",
                    self.distractions,
                ),
            )

        self.last_completed_session_id = db.c.lastrowid
        self.last_session_data = {
            "course": self.current_course,
            "duration": self.total_time // 60,
            "distractions": self.distractions,
            "timelapse_path": final_tl_path,
        }

        if self.active_queue_id:
            db.c.execute("UPDATE focus_queue SET status='completed' WHERE id=?", (self.active_queue_id,))
            db.safe_commit()

            db.c.execute(
                "SELECT id, duration, course, type FROM focus_queue WHERE status='pending' ORDER BY id ASC LIMIT 1"
            )
            next_item = db.c.fetchone()

            if next_item:
                self.active_queue_id = next_item[0]
                self.total_time = int(next_item[1]) * 60
                self.current_course = next_item[2] or "General"
                self.time_left = self.total_time
                self.distractions = 0
                self.distraction_markers = []
                self.distraction_log = []
                self.was_distracted = False
                self.distraction_type_current = "Manual"
                db.c.execute("UPDATE focus_queue SET status='active' WHERE id=?", (self.active_queue_id,))
                db.safe_commit()

                if not config.get("quiet_mode", False):
                    course_safe = self.current_course.replace(" ", "_").replace("/", "")
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    self.vision.start_rec(f"timelapses/Work_{course_safe}_{ts}.avi")
            else:
                self.active_queue_id = None
                self.is_running = False
                self.timer.stop()
                self.ovl.hide()
                self.vision.stop()
        else:
            self.is_running = False
            self.timer.stop()
            self.ovl.hide()
            self.vision.stop()

        db.safe_commit()

    def _handle_start_timer(self, req):
        if req.get("queue_id") == "auto":
            db.c.execute(
                "SELECT id, duration, course, type FROM focus_queue WHERE status='pending' ORDER BY id ASC LIMIT 1"
            )
            q = db.c.fetchone()
            if q:
                self.active_queue_id = q[0]
                self.total_time = int(q[1]) * 60
                self.current_course = q[2] or "General"
                db.c.execute("UPDATE focus_queue SET status='active' WHERE id=?", (self.active_queue_id,))
                db.safe_commit()
        else:
            self.current_course = req.get("course", "General")
            self.total_time = int(req.get("duration", 25)) * 60

        self.time_left = self.total_time
        self.distractions = 0
        self.distraction_markers = []
        self.distraction_log = []
        self.was_distracted = False
        self.last_completed_session_id = None
        self.last_session_data = None
        self.distraction_type_current = "Manual"

        self.is_running = True
        self.ovl.show()

        if not config.get("quiet_mode", False):
            self.vision.start()
            course_safe = self.current_course.replace(" ", "_").replace("/", "")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.vision.start_rec(f"timelapses/Work_{course_safe}_{ts}.avi")

        self.timer.start(1000)
        self.push_state()
        return json.dumps({"status": "started"})

    def _handle_stop_timer(self, req):
        self.is_running = False
        self.timer.stop()
        self.ovl.hide()
        self.vision.stop()
        self.time_left = 0

        if self.active_queue_id:
            db.c.execute("UPDATE focus_queue SET status='pending' WHERE id=?", (self.active_queue_id,))
            self.active_queue_id = None
            db.safe_commit()

        self.push_state()
        return json.dumps({"status": "stopped"})

    def _handle_pause_timer(self, req):
        if self.is_running:
            self.is_running = False
            self.timer.stop()
            self.vision.stop()
            if self.was_distracted:
                dur = (self.total_time - self.time_left) - self.distraction_start
                self.distraction_log.append(
                    [
                        self.distraction_start / 60.0,
                        dur / 60.0,
                        self.distraction_type_current,
                    ]
                )
                self.was_distracted = False
            self.push_state()
        return json.dumps({"status": "paused"})

    def _handle_resume_timer(self, req):
        if not self.is_running and self.time_left > 0:
            self.is_running = True
            self.timer.start(1000)
            if not config.get("quiet_mode", False):
                self.vision.start()
            self.push_state()
        return json.dumps({"status": "resumed"})
