"""Dashboard and local-data actions for the system bridge."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

from core_sys import config, db, get_color


class DashboardActionsMixin:
    """Serve dashboard state, history, settings, and reset actions."""

    def _handle_init(self, req):
        today_str = datetime.now().date().isoformat()
        ydy_str = (datetime.now().date() - timedelta(days=1)).isoformat()

        try:
            db.c.execute(
                "SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?",
                (today_str,),
            )
            tdy_study = db.c.fetchone()[0] or 0
            db.c.execute(
                "SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?",
                (ydy_str,),
            )
            ydy_study = db.c.fetchone()[0] or 0
            db.c.execute(
                "SELECT sum(distractions) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?",
                (today_str,),
            )
            tdy_dist = db.c.fetchone()[0] or 0
            db.c.execute(
                "SELECT sum(distractions) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?",
                (ydy_str,),
            )
            ydy_dist = db.c.fetchone()[0] or 0

            vols = []
            for hour in range(8, 20):
                db.c.execute(
                    "SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=? AND cast(strftime('%H', timestamp) as integer)=?",
                    (today_str, hour),
                )
                vols.append((db.c.fetchone()[0] or 0) / 60.0)

            db.c.execute("SELECT sum(actual_duration) FROM pomodoro_sessions WHERE type='Work'")
            global_study_hours = (db.c.fetchone()[0] or 0) / 60.0
            db.c.execute("SELECT sum(target_hours) FROM cascading_goals")
            global_target_hours = db.c.fetchone()[0] or 0.0
            if global_target_hours == 0:
                db.c.execute("SELECT sum(target_hours) FROM courses")
                global_target_hours = db.c.fetchone()[0] or 50.0

            db.c.execute("SELECT data_json FROM health_profile ORDER BY id DESC LIMIT 1")
            h_prof = db.c.fetchone()

            db.c.execute("SELECT id, log_type, date, data_json FROM health_logs")
            h_logs = [{"id": r[0], "type": r[1], "date": r[2], "data": json.loads(r[3])} for r in db.c.fetchall()]

            try:
                db.c.execute(
                    "SELECT timestamp, module, description FROM activity_logs ORDER BY timestamp DESC LIMIT 50"
                )
                act_logs = [{"timestamp": r[0], "module": r[1], "description": r[2]} for r in db.c.fetchall()]
            except Exception:
                act_logs = []

            ccolors = {}
            for course in db.c.execute("SELECT name FROM courses").fetchall():
                ccolors[course[0]] = get_color(course[0]).name()

            flat_goals = self.get_flat_goals()
            for flat_goal in flat_goals:
                root_name = flat_goal.split(" > ")[0]
                root_color = get_color(root_name).name()
                ccolors[flat_goal] = root_color
                raw_title = flat_goal.split(" > ")[-1]
                if raw_title not in ccolors:
                    ccolors[raw_title] = root_color

            ccolors["General"] = get_color("General").name()
            ccolors["Break"] = get_color("Break").name()

            return json.dumps(
                {
                    "course_colors": ccolors,
                    "flat_goals": flat_goals,
                    "goals": self.get_goals_tree(),
                    "heatmap": self.get_heatmap_data(),
                    "settings": config.cfg,
                    "activity_logs": act_logs,
                    "habits": [
                        {"id": r[0], "name": r[1], "type": r[2]}
                        for r in db.c.execute("SELECT id, name, type FROM habits").fetchall()
                    ],
                    "habit_logs": [
                        {"habit_id": r[0], "date": r[1], "status": r[2]}
                        for r in db.c.execute("SELECT habit_id, date, status FROM habit_logs").fetchall()
                    ],
                    "flashcards": [
                        {
                            "id": r[0],
                            "front": r[1],
                            "back": r[2],
                            "deck": r[3],
                            "course": r[4],
                            "folder": r[5],
                            "color": r[6],
                        }
                        for r in db.c.execute(
                            "SELECT id, front, back, deck, course, folder, color FROM flashcards"
                        ).fetchall()
                    ],
                    "quizzes": [
                        {"id": r[0], "title": r[1], "json": r[2], "course": r[3], "folder": r[4], "color": r[5]}
                        for r in db.c.execute(
                            "SELECT id, title, questions_json, course, folder, color FROM quizzes"
                        ).fetchall()
                    ],
                    "queue": [
                        {"id": r[0], "title": r[1], "duration": r[2], "type": r[3], "status": r[4], "course": r[5]}
                        for r in db.c.execute(
                            "SELECT id, title, duration, type, status, course FROM focus_queue ORDER BY id"
                        ).fetchall()
                    ],
                    "notes": [
                        {"id": r[0], "title": r[1], "content": r[2], "course": r[3], "folder": r[4], "color": r[5]}
                        for r in db.c.execute(
                            "SELECT id, title, content, course, folder, color FROM notes ORDER BY id DESC"
                        ).fetchall()
                    ],
                    "health_profile": json.loads(h_prof[0]) if h_prof else {},
                    "health_logs": h_logs,
                    "custom_foods": [
                        {
                            "id": r[0],
                            "name": r[1],
                            "kcal": r[2],
                            "protein": r[3],
                            "fat": r[4],
                            "carbs": r[5],
                            "category": r[6],
                        }
                        for r in db.c.execute(
                            "SELECT id, name, kcal, protein, fat, carbs, category FROM custom_foods"
                        ).fetchall()
                    ],
                    "custom_activities": [
                        {"id": r[0], "name": r[1], "met": r[2], "category": r[3]}
                        for r in db.c.execute("SELECT id, name, met, category FROM custom_activities").fetchall()
                    ],
                    "health_plans": [
                        {"id": r[0], "type": r[1], "title": r[2], "details": r[3]}
                        for r in db.c.execute("SELECT id, type, title, details FROM health_plans").fetchall()
                    ],
                    "metrics_data": {
                        "tdy_study": tdy_study / 60.0,
                        "ydy_study": ydy_study / 60.0,
                        "tdy_dist": tdy_dist,
                        "ydy_dist": ydy_dist,
                        "hourly_vol": vols,
                        "global_study_hours": global_study_hours,
                        "global_target_hours": global_target_hours,
                    },
                    "studied_hours": {
                        r[0]: (r[1] or 0) / 60.0
                        for r in db.c.execute(
                            "SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp)=?",
                            (today_str,),
                        ).fetchall()
                    },
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_get_today_data(self, req):
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            db.c.execute(
                "SELECT id, course, duration, actual_duration, timestamp, type, distractions, timelapse_path, distraction_data, note "
                "FROM pomodoro_sessions WHERE timestamp LIKE ? ORDER BY timestamp ASC",
                (today_str + "%",),
            )
            today_sessions = [
                {
                    "id": r[0],
                    "course": r[1],
                    "duration": r[2],
                    "actual_duration": r[3],
                    "timestamp": r[4],
                    "type": r[5],
                    "distractions": r[6],
                    "timelapse_path": r[7],
                    "distraction_data": json.loads(r[8] if r[8] else "[]"),
                    "note": r[9] or "",
                }
                for r in db.c.fetchall()
            ]

            db.c.execute(
                "SELECT course, sum(actual_duration) FROM pomodoro_sessions WHERE type='Work' AND timestamp LIKE ?",
                (today_str + "%",),
            )
            studied = {r[0]: (r[1] or 0) / 60.0 for r in db.c.fetchall()}

            return json.dumps({"today_sessions": today_sessions, "studied_hours": studied})
        except Exception:
            return json.dumps({"today_sessions": [], "studied_hours": {}})

    def _handle_force_reset_all_data(self, req):
        try:
            tables_to_clear = [
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
                "activity_logs",
                "ingredients",
                "composite_foods",
                "recipe_ingredients",
                "deleted_uuids",
            ]
            for table in tables_to_clear:
                with contextlib.suppress(Exception):
                    db.c.execute(f"DELETE FROM {table}")
            db.safe_commit()

            repo_url = config.get("sync_repo_url", "")
            token = config.get("sync_github_token", "")
            sync_enabled = config.get("sync_enabled", False)
            sync_interval = config.get("sync_interval", 3600)

            new_config = config.defaults.copy()
            new_config.update(
                {
                    "sync_repo_url": repo_url,
                    "sync_github_token": token,
                    "sync_enabled": sync_enabled,
                    "sync_interval": sync_interval,
                    "git_status": "unknown",
                    "git_last_sync": None,
                    "sync_msg": "",
                    "sync_progress_pct": 0,
                }
            )

            config.cfg = new_config
            with open(config.fn, "w") as f:
                json.dump(config.cfg, f)

            import shutil
            import time

            repo_path = os.path.expanduser("~/.mindpalace_sync_repo")
            if os.path.exists(repo_path):
                for attempt in range(5):
                    try:
                        if sys.platform == "win32":
                            subprocess.run(
                                ["attrib", "-r", "-s", "/s", "/d", repo_path],
                                capture_output=True,
                                shell=True,
                            )
                        shutil.rmtree(repo_path)
                        break
                    except Exception as e:
                        print(f"Delete attempt {attempt + 1} failed: {e}")
                        time.sleep(1)
                        if attempt == 4:
                            renamed_path = repo_path + "_old_" + str(int(time.time()))
                            try:
                                os.rename(repo_path, renamed_path)
                                print(f"Renamed repo to {renamed_path}")
                            except Exception:
                                print("Could not delete or rename repo - manual cleanup required")

            self.log_activity("System", "Force reset all data performed")
            return json.dumps({"status": "success", "message": "All local data wiped."})
        except Exception as e:
            self.log_activity("System Error", f"Force reset failed: {e!s}")
            return json.dumps({"status": "error", "message": str(e)})

    def _handle_get_history_data(self, req):
        try:
            db.c.execute(
                "SELECT id, course, duration, actual_duration, timestamp, type, distractions, timelapse_path, distraction_data, note "
                "FROM pomodoro_sessions ORDER BY timestamp DESC"
            )
            history = [
                {
                    "id": r[0],
                    "course": r[1],
                    "duration": r[2],
                    "actual_duration": r[3],
                    "timestamp": r[4],
                    "type": r[5],
                    "distractions": r[6],
                    "timelapse_path": r[7],
                    "distraction_data": json.loads(r[8] if r[8] else "[]"),
                    "note": r[9] or "",
                }
                for r in db.c.fetchall()
            ]
            return json.dumps({"history_sessions": history})
        except Exception:
            return json.dumps({"history_sessions": []})

    def _handle_save_session_note(self, req):
        session_id = req.get("session_id")
        note = req.get("note")
        if session_id:
            db.c.execute("UPDATE pomodoro_sessions SET note = ? WHERE id = ?", (note, session_id))
            db.safe_commit()
        return json.dumps({"status": "ok"})

    def _handle_save_settings(self, req):
        for key, value in req.get("data", {}).items():
            config.set(key, value)
        self.log_activity("Settings", "Updated application settings via UI.")
        return json.dumps({"status": "saved"})

    def _handle_reset_data(self, req):
        tables_to_clear = [
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
            "course_targets",
            "starred_questions",
            "exams",
            "todos",
        ]
        for table in tables_to_clear:
            with contextlib.suppress(Exception):
                db.c.execute(f"DELETE FROM {table}")
        db.safe_commit()
        return json.dumps({"status": "cleared"})
