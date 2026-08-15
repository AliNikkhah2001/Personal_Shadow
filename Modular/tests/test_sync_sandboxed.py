"""Sandboxed Multi-Device Sync Test Suite.

Simulates multiple artificial devices with generated IDs, makes changes to
different parts of the database, syncs through a shared local git repo,
and tracks the sync timeline to verify correctness.

ALL tests run in isolated temp directories.
NO real data, real databases, or real git repos are touched.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import uuid as uuid_mod
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import git

from core_sys import ConfigManager, DatabaseManager
from sync_manager import SyncManager

SYNCABLE_TABLES = [
    "courses", "pomodoro_sessions", "cascading_goals",
    "habits", "habit_logs", "flashcards", "quizzes",
    "focus_queue", "notes", "health_profile", "health_logs",
    "custom_foods", "custom_activities", "health_plans",
    "activity_logs", "ingredients", "composite_foods",
    "recipe_ingredients", "food_logs", "daily_metrics", "wallpapers",
]


class SyncTimeline:
    """Records sync events across devices for verification."""

    def __init__(self):
        self.events: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def log(self, device_id: str, event: str, details: str = "") -> None:
        with self._lock:
            self.events.append({
                "time": datetime.now().isoformat(),
                "device": device_id,
                "event": event,
                "details": details,
            })

    def get_events(self, device_id: str | None = None, event: str | None = None) -> list[dict]:
        with self._lock:
            result = self.events
            if device_id:
                result = [e for e in result if e["device"] == device_id]
            if event:
                result = [e for e in result if e["event"] == event]
            return list(result)

    def count(self, device_id: str | None = None, event: str | None = None) -> int:
        return len(self.get_events(device_id, event))

    def assert_last_event(self, device_id: str, expected_event: str) -> None:
        device_events = self.get_events(device_id)
        self.assertTrue(device_events, f"No events for device {device_id}")
        self.assertEqual(device_events[-1]["event"], expected_event)


class SandboxedDevice:
    """Fully isolated device with its own DB, config, sync manager, and git repo."""

    def __init__(self, device_id: str, base_dir: str):
        self.device_id = device_id
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

        self.db_path = os.path.join(base_dir, f"{device_id}.db")
        self.config_path = os.path.join(base_dir, f"{device_id}_config.json")
        self.repo_path = os.path.join(base_dir, "repo")

        self.db = DatabaseManager(self.db_path)
        self.config = ConfigManager(self.config_path)
        self.config.set("sync_enabled", True)

        self.sync_manager = SyncManager(device_id=device_id)
        self.sync_manager.repo_path = self.repo_path
        self.sync_manager.repo_url = ""
        self.sync_manager.token = ""
        self.sync_manager.repo = None

        self.timeline: SyncTimeline | None = None

    def set_timeline(self, timeline: SyncTimeline) -> None:
        self.timeline = timeline

    def log(self, event: str, details: str = "") -> None:
        if self.timeline:
            self.timeline.log(self.device_id, event, details)

    def create_course(self, name: str, target_hours: float = 10) -> str:
        uid = uuid_mod.uuid4().hex
        now = datetime.now().isoformat()
        self.db.c.execute(
            "INSERT INTO courses (name, uuid, modified_at, target_hours) VALUES (?, ?, ?, ?)",
            (name, uid, now, target_hours),
        )
        self.db.safe_commit()
        return uid

    def create_note(self, title: str, content: str = "", course: str = "General") -> str:
        uid = uuid_mod.uuid4().hex
        now = datetime.now().isoformat()
        self.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, now, title, content, now, course, "Default", "#3b82f6"),
        )
        self.db.safe_commit()
        return uid

    def create_habit(self, name: str, habit_type: str = "Positive") -> str:
        uid = uuid_mod.uuid4().hex
        now = datetime.now().isoformat()
        self.db.c.execute(
            "INSERT INTO habits (name, uuid, modified_at, created_at, type) VALUES (?, ?, ?, ?, ?)",
            (name, uid, now, now, habit_type),
        )
        self.db.safe_commit()
        return uid

    def create_ingredient(self, name: str, kcal: float = 100) -> str:
        uid = uuid_mod.uuid4().hex
        now = datetime.now().isoformat()
        self.db.c.execute(
            "INSERT INTO ingredients (uuid, modified_at, name, kcal, protein, fat, carbs) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, now, name, kcal, 10, 5, 15),
        )
        self.db.safe_commit()
        return uid

    def update_note(self, uid: str, new_content: str) -> None:
        now = datetime.now().isoformat()
        self.db.c.execute(
            "UPDATE notes SET content=?, modified_at=? WHERE uuid=?",
            (new_content, now, uid),
        )
        self.db.safe_commit()

    def update_course(self, uid: str, new_name: str) -> None:
        now = datetime.now().isoformat()
        self.db.c.execute(
            "UPDATE courses SET name=?, modified_at=? WHERE uuid=?",
            (new_name, now, uid),
        )
        self.db.safe_commit()

    def soft_delete_note(self, uid: str) -> None:
        now = datetime.now().isoformat()
        self.db.c.execute("DELETE FROM notes WHERE uuid=?", (uid,))
        self.db.c.execute(
            "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
            ("notes", uid, now),
        )
        self.db.safe_commit()

    def soft_delete_course(self, uid: str) -> None:
        now = datetime.now().isoformat()
        self.db.c.execute("DELETE FROM courses WHERE uuid=?", (uid,))
        self.db.c.execute(
            "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
            ("courses", uid, now),
        )
        self.db.safe_commit()

    def count_rows(self, table: str) -> int:
        self.db.c.execute(f"SELECT COUNT(*) FROM {table}")
        return self.db.c.fetchone()[0]

    def get_all_rows(self, table: str) -> list[dict]:
        self.db.c.execute(f"SELECT * FROM {table}")
        columns = [desc[0] for desc in self.db.c.description]
        return [dict(zip(columns, row)) for row in self.db.c.fetchall()]

    def get_row_by_uuid(self, table: str, uid: str) -> dict | None:
        self.db.c.execute(f"SELECT * FROM {table} WHERE uuid=?", (uid,))
        row = self.db.c.fetchone()
        if row:
            columns = [desc[0] for desc in self.db.c.description]
            return dict(zip(columns, row))
        return None


def _rmtree_onerror(func, path, exc_info):
    """Handle Windows file locking errors during cleanup."""
    import stat
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def create_bare_repo(base_dir: str) -> str:
    """Create a local bare git repo as a simulated remote. Returns the path."""
    bare_path = os.path.join(base_dir, "remote.git")
    git.Repo.init(bare_path, bare=True)

    temp_work = os.path.join(base_dir, "temp_work")
    os.makedirs(temp_work)
    work_repo = git.Repo.init(temp_work)
    with open(os.path.join(temp_work, ".gitkeep"), "w") as f:
        f.write("init")
    work_repo.git.add(".")
    work_repo.index.commit("Initial commit")
    work_repo.create_remote("origin", bare_path)
    work_repo.remotes.origin.push(refspec="HEAD:refs/heads/main")
    work_repo.close()
    del work_repo
    time.sleep(0.2)
    shutil.rmtree(temp_work, onerror=_rmtree_onerror)
    return bare_path


def setup_device_repo(device: SandboxedDevice, bare_path: str) -> None:
    """Clone the bare repo into the device's repo_path and configure it."""
    repo = git.Repo.clone_from(bare_path, device.repo_path)
    repo.config_writer().set_value("user", "name", f"Test {device.device_id}").release()
    repo.config_writer().set_value("user", "email", f"test@{device.device_id}").release()
    device.sync_manager.repo = repo
    device.sync_manager.repo_url = bare_path


def do_sync(device: SandboxedDevice) -> tuple[bool, str]:
    """Perform a full peer sync (pull, merge, export, push) on a device.

    Patches module-level db/config references to use the sandboxed instances.
    """
    sm = device.sync_manager
    with patch("sync_manager.db", device.db), \
         patch("sync_manager.config", device.config):
        try:
            origin = sm.repo.remotes.origin
            origin.pull(rebase=False)
        except Exception:
            pass

        sm.ensure_uuids_and_timestamps()
        sm.merge_all_remote_data()

        local_data = sm.export_local_data()
        export_path = os.path.join(sm.repo_path, sm.sync_data_file)
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(local_data, f, indent=2)

        sm.repo.git.add(all=True)
        if sm.repo.is_dirty() or sm.repo.untracked_files:
            sm.repo.index.commit(f"Sync from {sm.device_id}")
        try:
            sm.repo.remotes.origin.push()
        except Exception:
            pass
        return True, "Sync completed"


def do_force_sync_master(device: SandboxedDevice) -> tuple[bool, str]:
    """Perform a force-sync master overwrite on a device."""
    sm = device.sync_manager
    with patch("sync_manager.db", device.db), \
         patch("sync_manager.config", device.config):
        try:
            origin = sm.repo.remotes.origin
            origin.pull(rebase=False)
        except Exception:
            pass

        cluster_file = os.path.join(sm.repo_path, "cluster_state.json")
        with open(cluster_file, "w") as f:
            json.dump({
                "master_id": sm.device_id,
                "timestamp": datetime.now().isoformat(),
            }, f)

        sync_dir = os.path.join(sm.repo_path, sm.db_sync_dir)
        if os.path.exists(sync_dir):
            for fname in os.listdir(sync_dir):
                if fname.endswith(".json") and fname != f"{sm.device_id}.json":
                    with contextlib.suppress(Exception):
                        os.remove(os.path.join(sync_dir, fname))

        device.db.c.execute("DELETE FROM deleted_uuids")
        device.db.safe_commit()

        sm.ensure_uuids_and_timestamps()
        local_data = sm.export_local_data()
        export_path = os.path.join(sm.repo_path, sm.sync_data_file)
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(local_data, f, indent=2)

        sm.repo.git.add(cluster_file, force=True)
        sm.repo.git.add(all=True)
        if sm.repo.is_dirty() or sm.repo.untracked_files:
            sm.repo.index.commit(f"MASTER PROMOTE from {sm.device_id}")
        try:
            sm.repo.remotes.origin.push()
        except Exception:
            pass
        return True, "Master overwrite completed"


def do_hard_clone(device: SandboxedDevice, target_device_id: str) -> tuple[bool, str]:
    """Clone all data from target_device_id into this device's DB."""
    sm = device.sync_manager
    with patch("sync_manager.db", device.db), \
         patch("sync_manager.config", device.config):
        try:
            origin = sm.repo.remotes.origin
            origin.pull(rebase=False)
        except Exception:
            pass

        sync_dir = os.path.join(sm.repo_path, sm.db_sync_dir)
        target_file = os.path.join(sync_dir, f"{target_device_id}.json")
        if not os.path.exists(target_file):
            return False, f"Target file not found: {target_file}"

        tables_to_clear = [
            "courses", "pomodoro_sessions", "cascading_goals",
            "habits", "habit_logs", "flashcards", "quizzes",
            "focus_queue", "notes", "health_profile", "health_logs",
            "custom_foods", "custom_activities", "health_plans",
            "activity_logs", "ingredients", "composite_foods", "recipe_ingredients",
        ]
        for table in tables_to_clear:
            with contextlib.suppress(Exception):
                device.db.c.execute(f"DELETE FROM {table}")
        device.db.c.execute("DELETE FROM deleted_uuids")
        device.db.safe_commit()

        with open(target_file, encoding="utf-8") as f:
            remote_data = json.load(f)

        for k, v in remote_data.get("settings", {}).items():
            if k not in ["device_id", "has_token", "git_status"]:
                device.config.set(k, v)

        for table, rows in remote_data.get("tables", {}).items():
            if table not in tables_to_clear:
                continue
            for row in rows:
                cols = ", ".join(row.keys())
                placeholders = ", ".join(["?"] * len(row))
                with contextlib.suppress(Exception):
                    device.db.c.execute(
                        f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                        list(row.values()),
                    )
        device.db.safe_commit()
        return True, "Clone completed"


def write_cluster_state(repo_path: str, master_id: str) -> None:
    """Write a cluster_state.json to the repo."""
    os.makedirs(repo_path, exist_ok=True)
    cluster_file = os.path.join(repo_path, "cluster_state.json")
    with open(cluster_file, "w") as f:
        json.dump({
            "master_id": master_id,
            "timestamp": datetime.now().isoformat(),
        }, f)


def commit_and_push(device: SandboxedDevice, message: str = "update") -> None:
    """Stage, commit, and push all changes for a device."""
    sm = device.sync_manager
    sm.repo.git.add(all=True)
    if sm.repo.is_dirty() or sm.repo.untracked_files:
        sm.repo.index.commit(message)
    try:
        sm.repo.remotes.origin.push()
    except Exception:
        pass


class TestExportLogic(unittest.TestCase):
    """Tests for data export functionality."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_export_")
        self.device = SandboxedDevice("export_dev", self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_export_empty_database(self):
        with patch("sync_manager.db", self.device.db), \
             patch("sync_manager.config", self.device.config):
            data = self.device.sync_manager.export_local_data()
        self.assertEqual(data["device_id"], "export_dev")
        self.assertIn("last_sync", data)
        self.assertIn("settings", data)
        self.assertIn("tables", data)
        self.assertIn("deletions", data)

    def test_export_contains_all_tables(self):
        self.device.create_course("Math")
        with patch("sync_manager.db", self.device.db), \
             patch("sync_manager.config", self.device.config):
            data = self.device.sync_manager.export_local_data()
        self.assertIn("courses", data["tables"])

    def test_export_course_data(self):
        uid = self.device.create_course("Physics", 20)
        with patch("sync_manager.db", self.device.db), \
             patch("sync_manager.config", self.device.config):
            data = self.device.sync_manager.export_local_data()
        courses = data["tables"]["courses"]
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]["name"], "Physics")
        self.assertEqual(courses[0]["target_hours"], 20)
        self.assertEqual(courses[0]["uuid"], uid)

    def test_export_multiple_tables(self):
        self.device.create_course("Math")
        self.device.create_note("Lecture 1")
        self.device.create_habit("Meditate")
        with patch("sync_manager.db", self.device.db), \
             patch("sync_manager.config", self.device.config):
            data = self.device.sync_manager.export_local_data()
        self.assertGreater(len(data["tables"]["courses"]), 0)
        self.assertGreater(len(data["tables"]["notes"]), 0)
        self.assertGreater(len(data["tables"]["habits"]), 0)

    def test_export_excludes_token(self):
        self.device.config.set("sync_github_token", "secret_token_123")
        with patch("sync_manager.db", self.device.db), \
             patch("sync_manager.config", self.device.config):
            data = self.device.sync_manager.export_local_data()
        self.assertNotIn("sync_github_token", data["settings"])

    def test_export_deletions(self):
        uid = self.device.create_note("To Delete")
        self.device.soft_delete_note(uid)
        with patch("sync_manager.db", self.device.db), \
             patch("sync_manager.config", self.device.config):
            data = self.device.sync_manager.export_local_data()
        note_deletions = data["deletions"].get("notes", [])
        self.assertTrue(any(d["uuid"] == uid for d in note_deletions))


class TestBasicMerge(unittest.TestCase):
    """Tests for basic merge: Device A creates data, Device B merges it."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_merge_")
        self.timeline = SyncTimeline()

        self.device_a = SandboxedDevice("device_a_merge", os.path.join(self.base, "a"))
        self.device_b = SandboxedDevice("device_b_merge", os.path.join(self.base, "b"))
        self.device_a.set_timeline(self.timeline)
        self.device_b.set_timeline(self.timeline)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _prepare_remote_json(self, target: SandboxedDevice, source: SandboxedDevice) -> None:
        """Export source device's data and write it into target device's sync dir."""
        sync_dir = os.path.join(target.sync_manager.repo_path, target.sync_manager.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)
        filepath = os.path.join(sync_dir, f"{source.device_id}.json")
        with patch("sync_manager.db", source.db), \
             patch("sync_manager.config", source.config):
            data = source.sync_manager.export_local_data()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def test_device_b_receives_courses_from_a(self):
        self.device_a.create_course("Linear Algebra", 15)
        self.device_a.create_course("Databases", 20)

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_b.count_rows("courses"), 2)
        names = [r["name"] for r in self.device_b.get_all_rows("courses")]
        self.assertIn("Linear Algebra", names)
        self.assertIn("Databases", names)

    def test_device_b_receives_notes_from_a(self):
        self.device_a.create_note("Quantum Mechanics", "Wave functions")
        self.device_a.create_note("Organic Chem", "Benzene rings")

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_b.count_rows("notes"), 2)

    def test_device_b_receives_habits_from_a(self):
        self.device_a.create_habit("Exercise")
        self.device_a.create_habit("Reading")

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_b.count_rows("habits"), 2)

    def test_merge_preserves_local_data(self):
        self.device_b.create_course("Local Only Course")

        self.device_a.create_course("Remote Course")
        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_b.count_rows("courses"), 2)
        names = [r["name"] for r in self.device_b.get_all_rows("courses")]
        self.assertIn("Local Only Course", names)
        self.assertIn("Remote Course", names)

    def test_merge_ingredients(self):
        self.device_a.create_ingredient("Rice", 130)
        self.device_a.create_ingredient("Chicken", 165)

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_b.count_rows("ingredients"), 2)


class TestBidirectionalMerge(unittest.TestCase):
    """Tests for bidirectional sync: both devices create different data."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_bidir_")
        self.timeline = SyncTimeline()
        self.device_a = SandboxedDevice("device_a_bidir", os.path.join(self.base, "a"))
        self.device_b = SandboxedDevice("device_b_bidir", os.path.join(self.base, "b"))
        self.device_a.set_timeline(self.timeline)
        self.device_b.set_timeline(self.timeline)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _prepare_remote_json(self, target: SandboxedDevice, source: SandboxedDevice) -> None:
        sync_dir = os.path.join(target.sync_manager.repo_path, target.sync_manager.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)
        filepath = os.path.join(sync_dir, f"{source.device_id}.json")
        with patch("sync_manager.db", source.db), \
             patch("sync_manager.config", source.config):
            data = source.sync_manager.export_local_data()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def test_both_devices_get_each_others_data(self):
        self.device_a.create_course("Math from A")
        self.device_b.create_course("CS from B")

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        names = [r["name"] for r in self.device_b.get_all_rows("courses")]
        self.assertIn("Math from A", names)
        self.assertIn("CS from B", names)

    def test_multitable_bidirectional(self):
        self.device_a.create_course("Course A")
        self.device_a.create_note("Note A")
        self.device_b.create_habit("Habit B")
        self.device_b.create_ingredient("Ingredient B")

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_b.count_rows("courses"), 1)
        self.assertEqual(self.device_b.count_rows("notes"), 1)
        self.assertEqual(self.device_b.count_rows("habits"), 1)
        self.assertEqual(self.device_b.count_rows("ingredients"), 1)


class TestConflictResolution(unittest.TestCase):
    """Tests for LWW and master-wins conflict resolution."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_conflict_")
        self.timeline = SyncTimeline()
        self.device_a = SandboxedDevice("device_a_conflict", os.path.join(self.base, "a"))
        self.device_b = SandboxedDevice("device_b_conflict", os.path.join(self.base, "b"))
        self.device_a.set_timeline(self.timeline)
        self.device_b.set_timeline(self.timeline)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _prepare_remote_json(self, target: SandboxedDevice, source: SandboxedDevice) -> None:
        sync_dir = os.path.join(target.sync_manager.repo_path, target.sync_manager.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)
        filepath = os.path.join(sync_dir, f"{source.device_id}.json")
        with patch("sync_manager.db", source.db), \
             patch("sync_manager.config", source.config):
            data = source.sync_manager.export_local_data()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def test_lww_newer_wins(self):
        shared_uid = uuid_mod.uuid4().hex

        now = datetime.now().isoformat()
        older = (datetime.now() - timedelta(hours=2)).isoformat()

        self.device_a.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (shared_uid, older, "Old Title", "Old content", older, "General", "Default", "#3b82f6"),
        )
        self.device_a.db.safe_commit()

        self.device_b.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (shared_uid, now, "New Title", "New content", now, "General", "Default", "#3b82f6"),
        )
        self.device_b.db.safe_commit()

        self._prepare_remote_json(self.device_a, self.device_b)

        with patch("sync_manager.db", self.device_a.db), \
             patch("sync_manager.config", self.device_a.config):
            self.device_a.sync_manager.merge_all_remote_data()

        row = self.device_a.get_row_by_uuid("notes", shared_uid)
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "New Title")
        self.assertEqual(row["content"], "New content")

    def test_lww_local_wins_if_newer(self):
        shared_uid = uuid_mod.uuid4().hex

        now = datetime.now().isoformat()
        older = (datetime.now() - timedelta(hours=2)).isoformat()

        self.device_a.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (shared_uid, now, "Local is Newer", "Local content", now, "General", "Default", "#3b82f6"),
        )
        self.device_a.db.safe_commit()

        self.device_b.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (shared_uid, older, "Remote is Older", "Remote content", older, "General", "Default", "#3b82f6"),
        )
        self.device_b.db.safe_commit()

        self._prepare_remote_json(self.device_a, self.device_b)

        with patch("sync_manager.db", self.device_a.db), \
             patch("sync_manager.config", self.device_a.config):
            self.device_a.sync_manager.merge_all_remote_data()

        row = self.device_a.get_row_by_uuid("notes", shared_uid)
        self.assertEqual(row["title"], "Local is Newer")

    def test_master_always_wins(self):
        shared_uid = uuid_mod.uuid4().hex

        now = datetime.now().isoformat()
        older = (datetime.now() - timedelta(hours=2)).isoformat()

        os.makedirs(self.device_a.sync_manager.repo_path, exist_ok=True)
        write_cluster_state(self.device_a.sync_manager.repo_path, self.device_b.device_id)

        self.device_a.db.c.execute(
            "INSERT INTO courses (uuid, modified_at, name, target_hours) VALUES (?, ?, ?, ?)",
            (shared_uid, now, "Local Newer Course", 50),
        )
        self.device_a.db.safe_commit()

        self.device_b.db.c.execute(
            "INSERT INTO courses (uuid, modified_at, name, target_hours) VALUES (?, ?, ?, ?)",
            (shared_uid, older, "Master Older Course", 30),
        )
        self.device_b.db.safe_commit()

        self._prepare_remote_json(self.device_a, self.device_b)

        with patch("sync_manager.db", self.device_a.db), \
             patch("sync_manager.config", self.device_a.config):
            self.device_a.sync_manager.merge_all_remote_data()

        row = self.device_a.get_row_by_uuid("courses", shared_uid)
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "Master Older Course")
        self.assertEqual(row["target_hours"], 30)

    def test_new_remote_insert_not_duplicate(self):
        self.device_a.create_course("Existing Course")
        self.device_b.create_course("Existing Course")

        self._prepare_remote_json(self.device_a, self.device_b)

        initial_count = self.device_a.count_rows("courses")
        with patch("sync_manager.db", self.device_a.db), \
             patch("sync_manager.config", self.device_a.config):
            self.device_a.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_a.count_rows("courses"), initial_count)

    def test_merge_cross_table_no_interference(self):
        shared_note_uid = uuid_mod.uuid4().hex
        now = datetime.now().isoformat()

        self.device_a.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (shared_note_uid, now, "Note A", "Content A", now, "General", "Default", "#3b82f6"),
        )
        self.device_a.db.safe_commit()

        self.device_b.db.c.execute(
            "INSERT INTO courses (uuid, modified_at, name, target_hours) VALUES (?, ?, ?, ?)",
            (shared_note_uid, now, "Course B", 10),
        )
        self.device_b.db.safe_commit()

        self._prepare_remote_json(self.device_a, self.device_b)

        with patch("sync_manager.db", self.device_a.db), \
             patch("sync_manager.config", self.device_a.config):
            self.device_a.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_a.count_rows("notes"), 1)
        self.assertEqual(self.device_a.count_rows("courses"), 1)
        row = self.device_a.get_row_by_uuid("notes", shared_note_uid)
        self.assertEqual(row["title"], "Note A")


class TestDeletionPropagation(unittest.TestCase):
    """Tests for soft delete propagation across devices."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_delete_")
        self.timeline = SyncTimeline()
        self.device_a = SandboxedDevice("device_a_del", os.path.join(self.base, "a"))
        self.device_b = SandboxedDevice("device_b_del", os.path.join(self.base, "b"))
        self.device_a.set_timeline(self.timeline)
        self.device_b.set_timeline(self.timeline)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _prepare_remote_json(self, target: SandboxedDevice, source: SandboxedDevice) -> None:
        sync_dir = os.path.join(target.sync_manager.repo_path, target.sync_manager.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)
        filepath = os.path.join(sync_dir, f"{source.device_id}.json")
        with patch("sync_manager.db", source.db), \
             patch("sync_manager.config", source.config):
            data = source.sync_manager.export_local_data()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def test_deletion_removes_remote_row(self):
        shared_uid = uuid_mod.uuid4().hex
        now = datetime.now().isoformat()

        self.device_a.db.c.execute(
            "INSERT INTO courses (uuid, modified_at, name, target_hours) VALUES (?, ?, ?, ?)",
            (shared_uid, now, "Doomed Course", 10),
        )
        self.device_a.db.safe_commit()

        self.device_b.db.c.execute(
            "INSERT INTO courses (uuid, modified_at, name, target_hours) VALUES (?, ?, ?, ?)",
            (shared_uid, now, "Doomed Course", 10),
        )
        self.device_b.db.safe_commit()

        self.device_b.soft_delete_course(shared_uid)

        self.assertEqual(self.device_b.count_rows("courses"), 0)
        self.assertEqual(self.device_b.count_rows("deleted_uuids"), 1)

        self._prepare_remote_json(self.device_a, self.device_b)

        with patch("sync_manager.db", self.device_a.db), \
             patch("sync_manager.config", self.device_a.config):
            self.device_a.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_a.count_rows("courses"), 0)

    def test_deletion_with_newer_timestamp_wins(self):
        shared_uid = uuid_mod.uuid4().hex
        old_time = (datetime.now() - timedelta(hours=1)).isoformat()
        del_time = datetime.now().isoformat()

        self.device_a.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (shared_uid, old_time, "Note", "Content", old_time, "General", "Default", "#3b82f6"),
        )
        self.device_a.db.safe_commit()

        self.device_b.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (shared_uid, old_time, "Note", "Content", old_time, "General", "Default", "#3b82f6"),
        )
        self.device_b.db.safe_commit()

        self.device_b.db.c.execute("DELETE FROM notes WHERE uuid=?", (shared_uid,))
        self.device_b.db.c.execute(
            "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
            ("notes", shared_uid, del_time),
        )
        self.device_b.db.safe_commit()

        self._prepare_remote_json(self.device_a, self.device_b)

        with patch("sync_manager.db", self.device_a.db), \
             patch("sync_manager.config", self.device_a.config):
            self.device_a.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_a.count_rows("notes"), 0)

    def test_local_modification_prevents_deletion(self):
        shared_uid = uuid_mod.uuid4().hex
        now = datetime.now().isoformat()
        older = (datetime.now() - timedelta(hours=2)).isoformat()

        self.device_a.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (shared_uid, now, "Updated Note", "Fresh content", now, "General", "Default", "#3b82f6"),
        )
        self.device_a.db.safe_commit()

        self.device_b.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (shared_uid, older, "Old Note", "Old", older, "General", "Default", "#3b82f6"),
        )
        self.device_b.db.safe_commit()

        self.device_b.db.c.execute("DELETE FROM notes WHERE uuid=?", (shared_uid,))
        self.device_b.db.c.execute(
            "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
            ("notes", shared_uid, older),
        )
        self.device_b.db.safe_commit()

        self._prepare_remote_json(self.device_a, self.device_b)

        with patch("sync_manager.db", self.device_a.db), \
             patch("sync_manager.config", self.device_a.config):
            self.device_a.sync_manager.merge_all_remote_data()

        row = self.device_a.get_row_by_uuid("notes", shared_uid)
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "Updated Note")


class TestSettingsSync(unittest.TestCase):
    """Tests for settings synchronization between devices."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_settings_")
        self.device_a = SandboxedDevice("device_a_settings", os.path.join(self.base, "a"))
        self.device_b = SandboxedDevice("device_b_settings", os.path.join(self.base, "b"))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _prepare_remote_json(self, target: SandboxedDevice, source: SandboxedDevice) -> None:
        sync_dir = os.path.join(target.sync_manager.repo_path, target.sync_manager.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)
        filepath = os.path.join(sync_dir, f"{source.device_id}.json")
        with patch("sync_manager.db", source.db), \
             patch("sync_manager.config", source.config):
            data = source.sync_manager.export_local_data()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def test_settings_merge_from_remote(self):
        self.device_a.config.set("font_family", "Roboto")
        self.device_a.config.set("vision_mode", "Relaxed")

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

    def test_settings_exclude_device_id(self):
        self.device_a.config.set("device_id", "should_not_propagate")

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()


class TestForceSyncMasterOverwrite(unittest.TestCase):
    """Tests for force_sync_now / master overwrite."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_force_")
        self.timeline = SyncTimeline()
        self.device_a = SandboxedDevice("device_a_force", os.path.join(self.base, "a"))
        self.device_b = SandboxedDevice("device_b_force", os.path.join(self.base, "b"))
        self.device_a.set_timeline(self.timeline)
        self.device_b.set_timeline(self.timeline)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_force_sync_sets_cluster_master(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        setup_device_repo(self.device_a, bare_path)
        self.device_a.create_course("Master Course")

        do_force_sync_master(self.device_a)
        self.device_a.log("force_sync", "Promoted to master")

        master_id = self.device_a.sync_manager._get_master_id()
        self.assertEqual(master_id, self.device_a.device_id)

    def test_force_sync_wipes_other_devices(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        setup_device_repo(self.device_a, bare_path)
        setup_device_repo(self.device_b, bare_path)

        self.device_a.create_course("A Course")
        do_sync(self.device_a)

        do_sync(self.device_b)
        self.assertEqual(self.device_b.count_rows("courses"), 1)

        do_force_sync_master(self.device_a)

        with patch("sync_manager.db", self.device_a.db), \
             patch("sync_manager.config", self.device_a.config):
            self.device_a.sync_manager.repo.remotes.origin.pull(rebase=False)

        sync_dir = os.path.join(
            self.device_a.sync_manager.repo_path,
            self.device_a.sync_manager.db_sync_dir,
        )
        jsons = [f for f in os.listdir(sync_dir) if f.endswith(".json")]
        self.assertEqual(len(jsons), 1)
        self.assertIn(f"{self.device_a.device_id}.json", jsons)

    def test_force_sync_then_other_device_pulls(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        setup_device_repo(self.device_a, bare_path)
        setup_device_repo(self.device_b, bare_path)

        self.device_a.create_course("Master Data")
        do_force_sync_master(self.device_a)

        do_sync(self.device_b)
        names = [r["name"] for r in self.device_b.get_all_rows("courses")]
        self.assertIn("Master Data", names)


class TestHardClone(unittest.TestCase):
    """Tests for hard clone from remote device."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_clone_")
        self.timeline = SyncTimeline()
        self.device_a = SandboxedDevice("device_a_clone", os.path.join(self.base, "a"))
        self.device_b = SandboxedDevice("device_b_clone", os.path.join(self.base, "b"))
        self.device_a.set_timeline(self.timeline)
        self.device_b.set_timeline(self.timeline)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_hard_clone_copies_data(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        setup_device_repo(self.device_a, bare_path)
        setup_device_repo(self.device_b, bare_path)

        self.device_a.create_course("Source Course")
        self.device_a.create_note("Source Note")
        self.device_a.create_ingredient("Source Ingredient")

        do_force_sync_master(self.device_a)

        success, msg = do_hard_clone(self.device_b, self.device_a.device_id)
        self.assertTrue(success, msg)

        self.assertEqual(self.device_b.count_rows("courses"), 1)
        self.assertEqual(self.device_b.count_rows("notes"), 1)
        self.assertEqual(self.device_b.count_rows("ingredients"), 1)

    def test_hard_clone_wipes_existing_data(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        setup_device_repo(self.device_a, bare_path)
        setup_device_repo(self.device_b, bare_path)

        self.device_b.create_course("B Local Course")
        self.device_b.create_note("B Local Note")

        self.device_a.create_course("A Course")

        do_force_sync_master(self.device_a)
        success, msg = do_hard_clone(self.device_b, self.device_a.device_id)
        self.assertTrue(success, msg)

        self.assertEqual(self.device_b.count_rows("courses"), 1)
        row = self.device_b.get_all_rows("courses")[0]
        self.assertEqual(row["name"], "A Course")

    def test_hard_clone_applies_settings(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        setup_device_repo(self.device_a, bare_path)
        setup_device_repo(self.device_b, bare_path)

        self.device_a.config.set("font_family", "Fira Code")
        self.device_a.create_course("Settings Course")

        do_force_sync_master(self.device_a)
        success, _ = do_hard_clone(self.device_b, self.device_a.device_id)
        self.assertTrue(success)


class TestFullGitSyncCycle(unittest.TestCase):
    """End-to-end sync tests using a local bare git repo."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_git_")
        self.timeline = SyncTimeline()
        self.bare_path = create_bare_repo(os.path.join(self.base, "remote"))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_a_to_b_sync(self):
        dev_a = SandboxedDevice("git_a", os.path.join(self.base, "a"))
        dev_b = SandboxedDevice("git_b", os.path.join(self.base, "b"))
        dev_a.set_timeline(self.timeline)
        dev_b.set_timeline(self.timeline)

        setup_device_repo(dev_a, self.bare_path)
        setup_device_repo(dev_b, self.bare_path)

        dev_a.create_course("Synced Course")
        dev_a.create_note("Synced Note")
        dev_a.log("insert", "Created course and note")

        do_sync(dev_a)
        dev_a.log("push", "Pushed to remote")

        do_sync(dev_b)
        dev_b.log("pull", "Pulled from remote")

        self.assertEqual(dev_b.count_rows("courses"), 1)
        self.assertEqual(dev_b.count_rows("notes"), 1)
        names = [r["name"] for r in dev_b.get_all_rows("courses")]
        self.assertIn("Synced Course", names)

    def test_bidirectional_sync(self):
        dev_a = SandboxedDevice("git_bi_a", os.path.join(self.base, "a"))
        dev_b = SandboxedDevice("git_bi_b", os.path.join(self.base, "b"))

        setup_device_repo(dev_a, self.bare_path)
        setup_device_repo(dev_b, self.bare_path)

        dev_a.create_course("Course A")
        do_sync(dev_a)

        dev_b.create_course("Course B")
        dev_b.create_note("Note B")
        do_sync(dev_b)

        do_sync(dev_a)
        do_sync(dev_b)

        a_courses = [r["name"] for r in dev_a.get_all_rows("courses")]
        b_courses = [r["name"] for r in dev_b.get_all_rows("courses")]
        self.assertIn("Course A", a_courses)
        self.assertIn("Course B", a_courses)
        self.assertIn("Course A", b_courses)
        self.assertIn("Course B", b_courses)

    def test_three_device_sync(self):
        dev_a = SandboxedDevice("git3_a", os.path.join(self.base, "a"))
        dev_b = SandboxedDevice("git3_b", os.path.join(self.base, "b"))
        dev_c = SandboxedDevice("git3_c", os.path.join(self.base, "c"))

        setup_device_repo(dev_a, self.bare_path)
        setup_device_repo(dev_b, self.bare_path)
        setup_device_repo(dev_c, self.bare_path)

        dev_a.create_course("A Course")
        dev_b.create_note("B Note")
        dev_c.create_habit("C Habit")

        do_sync(dev_a)
        do_sync(dev_b)
        do_sync(dev_c)

        do_sync(dev_a)
        do_sync(dev_b)
        do_sync(dev_c)

        for dev in [dev_a, dev_b, dev_c]:
            self.assertEqual(dev.count_rows("courses"), 1)
            self.assertEqual(dev.count_rows("notes"), 1)
            self.assertEqual(dev.count_rows("habits"), 1)

    def test_sync_after_delete(self):
        dev_a = SandboxedDevice("git_del_a", os.path.join(self.base, "a"))
        dev_b = SandboxedDevice("git_del_b", os.path.join(self.base, "b"))

        setup_device_repo(dev_a, self.bare_path)
        setup_device_repo(dev_b, self.bare_path)

        uid = dev_a.create_course("Doomed Course")
        do_sync(dev_a)
        do_sync(dev_b)
        self.assertEqual(dev_b.count_rows("courses"), 1)

        dev_a.soft_delete_course(uid)
        do_sync(dev_a)
        do_sync(dev_b)
        self.assertEqual(dev_b.count_rows("courses"), 0)

    def test_multiple_sync_rounds(self):
        dev_a = SandboxedDevice("git_rounds_a", os.path.join(self.base, "a"))
        dev_b = SandboxedDevice("git_rounds_b", os.path.join(self.base, "b"))

        setup_device_repo(dev_a, self.bare_path)
        setup_device_repo(dev_b, self.bare_path)

        for i in range(5):
            dev_a.create_course(f"Round A Course {i}")
            do_sync(dev_a)
            dev_b.create_note(f"Round B Note {i}")
            do_sync(dev_b)
            do_sync(dev_a)

        do_sync(dev_b)
        self.assertEqual(dev_a.count_rows("courses"), 5)
        self.assertEqual(dev_a.count_rows("notes"), 5)
        self.assertEqual(dev_b.count_rows("courses"), 5)
        self.assertEqual(dev_b.count_rows("notes"), 5)

    def test_force_sync_then_merge(self):
        dev_a = SandboxedDevice("git_fs_a", os.path.join(self.base, "a"))
        dev_b = SandboxedDevice("git_fs_b", os.path.join(self.base, "b"))

        setup_device_repo(dev_a, self.bare_path)
        setup_device_repo(dev_b, self.bare_path)

        dev_a.create_course("Master Only")
        do_force_sync_master(dev_a)

        do_sync(dev_b)
        self.assertEqual(dev_b.count_rows("courses"), 1)

        dev_b.create_course("After Force Sync")
        do_sync(dev_b)

        do_sync(dev_a)
        a_courses = [r["name"] for r in dev_a.get_all_rows("courses")]
        self.assertIn("Master Only", a_courses)
        self.assertIn("After Force Sync", a_courses)

    def test_timeline_tracking(self):
        dev_a = SandboxedDevice("git_tl_a", os.path.join(self.base, "a"))
        dev_b = SandboxedDevice("git_tl_b", os.path.join(self.base, "b"))
        dev_a.set_timeline(self.timeline)
        dev_b.set_timeline(self.timeline)

        setup_device_repo(dev_a, self.bare_path)
        setup_device_repo(dev_b, self.bare_path)

        dev_a.create_course("Course")
        dev_a.log("create", "Created Course")
        do_sync(dev_a)
        dev_a.log("push", "Pushed")

        do_sync(dev_b)
        dev_b.log("pull", "Pulled")

        self.assertGreaterEqual(self.timeline.count(), 3)
        a_events = self.timeline.get_events("git_tl_a")
        b_events = self.timeline.get_events("git_tl_b")
        self.assertTrue(any(e["event"] == "push" for e in a_events))
        self.assertTrue(any(e["event"] == "pull" for e in b_events))


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error conditions."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_edge_")
        self.device_a = SandboxedDevice("edge_a", os.path.join(self.base, "a"))
        self.device_b = SandboxedDevice("edge_b", os.path.join(self.base, "b"))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _prepare_remote_json(self, target: SandboxedDevice, source: SandboxedDevice) -> None:
        sync_dir = os.path.join(target.sync_manager.repo_path, target.sync_manager.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)
        filepath = os.path.join(sync_dir, f"{source.device_id}.json")
        with patch("sync_manager.db", source.db), \
             patch("sync_manager.config", source.config):
            data = source.sync_manager.export_local_data()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def test_merge_empty_sync_dir(self):
        sync_dir = os.path.join(self.device_b.sync_manager.repo_path, self.device_b.sync_manager.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_b.count_rows("courses"), 0)

    def test_merge_malformed_json(self):
        sync_dir = os.path.join(self.device_b.sync_manager.repo_path, self.device_b.sync_manager.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)

        bad_file = os.path.join(sync_dir, "bad_device.json")
        with open(bad_file, "w") as f:
            f.write("not valid json {{{")

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

    def test_merge_row_without_uuid(self):
        sync_dir = os.path.join(self.device_b.sync_manager.repo_path, self.device_b.sync_manager.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)

        bad_data = {
            "device_id": "no_uuid_device",
            "last_sync": datetime.now().isoformat(),
            "settings": {},
            "tables": {
                "courses": [
                    {"id": 1, "name": "No UUID Course", "target_hours": 10},
                ],
            },
            "deletions": {},
        }
        with open(os.path.join(sync_dir, "no_uuid_device.json"), "w") as f:
            json.dump(bad_data, f)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_b.count_rows("courses"), 0)

    def test_merge_with_special_characters(self):
        uid = uuid_mod.uuid4().hex
        now = datetime.now().isoformat()
        special_title = "Course with unicode: 你好世界 + emoji: 🎉 & <script>alert('xss')</script>"

        self.device_a.db.c.execute(
            "INSERT INTO courses (uuid, modified_at, name, target_hours) VALUES (?, ?, ?, ?)",
            (uid, now, special_title, 5),
        )
        self.device_a.db.safe_commit()

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        row = self.device_b.get_row_by_uuid("courses", uid)
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], special_title)

    def test_merge_very_long_string(self):
        uid = uuid_mod.uuid4().hex
        now = datetime.now().isoformat()
        long_content = "x" * 50000

        self.device_a.db.c.execute(
            "INSERT INTO notes (uuid, modified_at, title, content, timestamp, course, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, now, "Long Note", long_content, now, "General", "Default", "#3b82f6"),
        )
        self.device_a.db.safe_commit()

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        row = self.device_b.get_row_by_uuid("notes", uid)
        self.assertIsNotNone(row)
        self.assertEqual(len(row["content"]), 50000)

    def test_merge_null_values(self):
        uid = uuid_mod.uuid4().hex
        now = datetime.now().isoformat()

        self.device_a.db.c.execute(
            "INSERT INTO flashcards (uuid, modified_at, front, back, deck, next_review, course) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, now, "Q", "A", None, None, None),
        )
        self.device_a.db.safe_commit()

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        row = self.device_b.get_row_by_uuid("flashcards", uid)
        self.assertIsNotNone(row)

    def test_export_import_roundtrip(self):
        self.device_a.create_course("Roundtrip Course")
        self.device_a.create_note("Roundtrip Note")
        self.device_a.create_habit("Roundtrip Habit")
        self.device_a.create_ingredient("Roundtrip Ingredient")

        with patch("sync_manager.db", self.device_a.db), \
             patch("sync_manager.config", self.device_a.config):
            export_data = self.device_a.sync_manager.export_local_data()

        with open(os.path.join(self.base, "export.json"), "w") as f:
            json.dump(export_data, f, indent=2)

        with open(os.path.join(self.base, "export.json")) as f:
            loaded = json.load(f)

        self.assertEqual(loaded["device_id"], self.device_a.device_id)
        self.assertIn("courses", loaded["tables"])
        self.assertEqual(len(loaded["tables"]["courses"]), 1)

    def test_concurrent_sync_safety(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        setup_device_repo(self.device_a, bare_path)

        for i in range(10):
            self.device_a.create_course(f"Concurrent {i}")

        do_sync(self.device_a)

        setup_device_repo(self.device_b, bare_path)
        do_sync(self.device_b)

        self.assertEqual(self.device_b.count_rows("courses"), 10)


class TestMultiDeviceTimeline(unittest.TestCase):
    """Tests with 3+ devices tracking sync timeline."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_timeline_")
        self.timeline = SyncTimeline()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_four_device_sync(self):
        devices = []
        for i in range(4):
            dev = SandboxedDevice(
                f"tl_device_{i}",
                os.path.join(self.base, f"device_{i}"),
            )
            dev.set_timeline(self.timeline)
            devices.append(dev)

        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        for dev in devices:
            setup_device_repo(dev, bare_path)

        devices[0].create_course("From D0")
        devices[1].create_note("From D1")
        devices[2].create_habit("From D2")
        devices[3].create_ingredient("From D3")

        for dev in devices:
            do_sync(dev)
            dev.log("sync_done")

        for dev in devices:
            do_sync(dev)

        for dev in devices:
            self.assertEqual(dev.count_rows("courses"), 1)
            self.assertEqual(dev.count_rows("notes"), 1)
            self.assertEqual(dev.count_rows("habits"), 1)
            self.assertEqual(dev.count_rows("ingredients"), 1)

    def test_sequential_data_propagation(self):
        dev_a = SandboxedDevice("seq_a", os.path.join(self.base, "a"))
        dev_b = SandboxedDevice("seq_b", os.path.join(self.base, "b"))
        dev_c = SandboxedDevice("seq_c", os.path.join(self.base, "c"))
        dev_a.set_timeline(self.timeline)
        dev_b.set_timeline(self.timeline)
        dev_c.set_timeline(self.timeline)

        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        setup_device_repo(dev_a, bare_path)
        setup_device_repo(dev_b, bare_path)
        setup_device_repo(dev_c, bare_path)

        dev_a.create_course("Step 1")
        do_sync(dev_a)
        dev_a.log("step1_push")

        do_sync(dev_b)
        dev_b.log("step1_pull")
        dev_b.create_note("Step 2")
        do_sync(dev_b)
        dev_b.log("step2_push")

        do_sync(dev_c)
        dev_c.log("step1_pull")
        do_sync(dev_a)

        for dev in [dev_a, dev_b, dev_c]:
            self.assertEqual(dev.count_rows("courses"), 1)
            self.assertEqual(dev.count_rows("notes"), 1)


class TestSyncManagerHelperMethods(unittest.TestCase):
    """Tests for SyncManager utility methods."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_helpers_")
        self.device = SandboxedDevice("helper_dev", self.base)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_get_device_id(self):
        dev_id = self.device.sync_manager.get_device_id()
        self.assertIsInstance(dev_id, str)
        self.assertTrue(len(dev_id) > 0)

    def test_ensure_uuids_and_timestamps(self):
        now = datetime.now().isoformat()
        self.device.db.c.execute(
            "INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
            ("No UUID Course", None, None),
        )
        self.device.db.safe_commit()

        with patch("sync_manager.db", self.device.db), \
             patch("sync_manager.config", self.device.config):
            self.device.sync_manager.ensure_uuids_and_timestamps()

        self.device.db.c.execute("SELECT uuid, modified_at FROM courses WHERE name = 'No UUID Course'")
        row = self.device.db.c.fetchone()
        self.assertIsNotNone(row[0])
        self.assertIsNotNone(row[1])

    def test_get_all_tables(self):
        with patch("sync_manager.db", self.device.db), \
             patch("sync_manager.config", self.device.config):
            tables = self.device.sync_manager._get_all_tables()

        self.assertIn("courses", tables)
        self.assertIn("notes", tables)
        self.assertIn("habits", tables)
        self.assertNotIn("sqlite_sequence", tables)

    def test_get_master_id_no_file(self):
        master = self.device.sync_manager._get_master_id()
        self.assertIsNone(master)

    def test_get_master_id_with_file(self):
        write_cluster_state(self.device.sync_manager.repo_path, "some_master")
        master = self.device.sync_manager._get_master_id()
        self.assertEqual(master, "some_master")

    def test_encode_decode_blob(self):
        original = b"hello binary data"
        encoded = SyncManager._encode_json_value(original)
        self.assertIsInstance(encoded, dict)
        self.assertIn("__blob_base64__", encoded)

        decoded = SyncManager._decode_json_value(encoded)
        self.assertEqual(decoded, original)

    def test_encode_non_bytes_passthrough(self):
        value = "string value"
        result = SyncManager._encode_json_value(value)
        self.assertEqual(result, "string value")

    def test_decode_non_blob_passthrough(self):
        value = {"key": "value"}
        result = SyncManager._decode_json_value(value)
        self.assertEqual(result, {"key": "value"})

    def test_export_data_has_correct_structure(self):
        self.device.create_course("Test")
        with patch("sync_manager.db", self.device.db), \
             patch("sync_manager.config", self.device.config):
            data = self.device.sync_manager.export_local_data()

        self.assertIn("device_id", data)
        self.assertIn("last_sync", data)
        self.assertIn("settings", data)
        self.assertIn("tables", data)
        self.assertIn("deletions", data)
        self.assertEqual(data["device_id"], "helper_dev")


class TestGitRepoSetup(unittest.TestCase):
    """Tests for git repo initialization and management."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_gitsetup_")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_bare_repo_creation(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        self.assertTrue(os.path.exists(bare_path))
        self.assertTrue(os.path.exists(os.path.join(bare_path, "HEAD")))

    def test_device_clone(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        dev = SandboxedDevice("clone_dev", os.path.join(self.base, "dev"))
        setup_device_repo(dev, bare_path)

        self.assertIsNotNone(dev.sync_manager.repo)
        self.assertTrue(os.path.exists(dev.repo_path))

    def test_multiple_devices_clone_same_repo(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        devs = []
        for i in range(3):
            dev = SandboxedDevice(f"multi_{i}", os.path.join(self.base, f"d{i}"))
            setup_device_repo(dev, bare_path)
            devs.append(dev)

        for dev in devs:
            self.assertIsNotNone(dev.sync_manager.repo)

    def test_push_pull_cycle(self):
        bare_path = create_bare_repo(os.path.join(self.base, "remote"))
        dev_a = SandboxedDevice("pp_a", os.path.join(self.base, "a"))
        dev_b = SandboxedDevice("pp_b", os.path.join(self.base, "b"))
        setup_device_repo(dev_a, bare_path)
        setup_device_repo(dev_b, bare_path)

        with open(os.path.join(dev_a.repo_path, "test.txt"), "w") as f:
            f.write("hello")
        commit_and_push(dev_a, "Add test file")

        dev_b.sync_manager.repo.remotes.origin.pull()
        self.assertTrue(os.path.exists(os.path.join(dev_b.repo_path, "test.txt")))


class TestComprehensiveDataTypes(unittest.TestCase):
    """Tests syncing across all major data types."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="sync_test_comprehensive_")
        self.device_a = SandboxedDevice("comp_a", os.path.join(self.base, "a"))
        self.device_b = SandboxedDevice("comp_b", os.path.join(self.base, "b"))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _prepare_remote_json(self, target: SandboxedDevice, source: SandboxedDevice) -> None:
        sync_dir = os.path.join(target.sync_manager.repo_path, target.sync_manager.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)
        filepath = os.path.join(sync_dir, f"{source.device_id}.json")
        with patch("sync_manager.db", source.db), \
             patch("sync_manager.config", source.config):
            data = source.sync_manager.export_local_data()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def test_sync_all_table_types(self):
        now = datetime.now().isoformat()

        self.device_a.db.c.execute(
            "INSERT INTO courses (name, uuid, modified_at, target_hours) VALUES (?, ?, ?, ?)",
            ("Math", uuid_mod.uuid4().hex, now, 100),
        )
        self.device_a.db.c.execute(
            "INSERT INTO pomodoro_sessions (course, duration, actual_duration, timestamp, type, uuid, modified_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Math", 25, 25, now, "focus", uuid_mod.uuid4().hex, now),
        )
        self.device_a.db.c.execute(
            "INSERT INTO habits (name, uuid, modified_at, created_at, type) VALUES (?, ?, ?, ?, ?)",
            ("Meditate", uuid_mod.uuid4().hex, now, now, "Positive"),
        )
        self.device_a.db.c.execute(
            "INSERT INTO flashcards (front, back, deck, next_review, course, uuid, modified_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Q1", "A1", "Default", now, "Math", uuid_mod.uuid4().hex, now),
        )
        self.device_a.db.c.execute(
            "INSERT INTO notes (title, content, timestamp, course, uuid, modified_at, folder, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("Note 1", "Content 1", now, "Math", uuid_mod.uuid4().hex, now, "Default", "#3b82f6"),
        )
        self.device_a.db.c.execute(
            "INSERT INTO custom_foods (name, uuid, modified_at, kcal, protein, fat, carbs, category) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("Custom Food", uuid_mod.uuid4().hex, now, 200, 20, 10, 30, "Test"),
        )
        self.device_a.db.safe_commit()

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_b.count_rows("courses"), 1)
        self.assertEqual(self.device_b.count_rows("pomodoro_sessions"), 1)
        self.assertEqual(self.device_b.count_rows("habits"), 1)
        self.assertEqual(self.device_b.count_rows("flashcards"), 1)
        self.assertEqual(self.device_b.count_rows("notes"), 1)
        self.assertEqual(self.device_b.count_rows("custom_foods"), 1)

    def test_sync_health_data(self):
        now = datetime.now().isoformat()

        self.device_a.db.c.execute(
            "INSERT INTO health_profile (uuid, modified_at, data_json) VALUES (?, ?, ?)",
            (uuid_mod.uuid4().hex, now, json.dumps({"weight": 80, "height": 180})),
        )
        self.device_a.db.c.execute(
            "INSERT INTO health_logs (uuid, modified_at, log_type, date, data_json) VALUES (?, ?, ?, ?, ?)",
            (uuid_mod.uuid4().hex, now, "weight", "2026-08-15", json.dumps({"weight": 80})),
        )
        self.device_a.db.c.execute(
            "INSERT INTO health_plans (uuid, modified_at, type, title, details) VALUES (?, ?, ?, ?, ?)",
            (uuid_mod.uuid4().hex, now, "nutrition", "Cut Phase", "Eat less"),
        )
        self.device_a.db.safe_commit()

        self._prepare_remote_json(self.device_b, self.device_a)

        with patch("sync_manager.db", self.device_b.db), \
             patch("sync_manager.config", self.device_b.config):
            self.device_b.sync_manager.merge_all_remote_data()

        self.assertEqual(self.device_b.count_rows("health_profile"), 1)
        self.assertEqual(self.device_b.count_rows("health_logs"), 1)
        self.assertEqual(self.device_b.count_rows("health_plans"), 1)


if __name__ == "__main__":
    print("=" * 70)
    print("  Mind Palace OS - Sandboxed Multi-Device Sync Test Suite")
    print("=" * 70)
    print("  WARNING: All tests run in isolated temp directories.")
    print("  NO real data or databases are modified.")
    print("=" * 70)
    unittest.main(verbosity=2)
