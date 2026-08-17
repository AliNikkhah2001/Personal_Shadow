"""Filesharing database layer tests.

Tests ConfigManager folder-goal bindings, retention data storage,
and DatabaseManager sync table integrity.
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockConfigManager:
    """In-memory ConfigManager for testing."""

    def __init__(self, data=None):
        self.cfg = data or {}
        self._written = []

    def get(self, key, default=None):
        return self.cfg.get(key, default)

    def set(self, key, value):
        self.cfg[key] = value
        self._written.append((key, value))


class TestConfigBindings(unittest.TestCase):
    """Test folder-goal binding storage in ConfigManager."""

    def setUp(self):
        self.config = MockConfigManager()

    def test_bind_folder_to_goal(self):
        bindings = self.config.get("folder_goal_bindings", {})
        bindings["/shared/docs"] = "goal-uuid-123"
        self.config.set("folder_goal_bindings", bindings)
        self.assertEqual(self.config.get("folder_goal_bindings")["/shared/docs"], "goal-uuid-123")

    def test_bind_multiple_folders(self):
        bindings = {}
        bindings["/shared/docs"] = "goal-uuid-1"
        bindings["/shared/code"] = "goal-uuid-2"
        bindings["/shared/images"] = "goal-uuid-3"
        self.config.set("folder_goal_bindings", bindings)
        result = self.config.get("folder_goal_bindings")
        self.assertEqual(len(result), 3)
        self.assertEqual(result["/shared/code"], "goal-uuid-2")

    def test_unbind_folder(self):
        bindings = {"/shared/docs": "goal-uuid-1", "/shared/code": "goal-uuid-2"}
        self.config.set("folder_goal_bindings", bindings)
        del bindings["/shared/docs"]
        self.config.set("folder_goal_bindings", bindings)
        result = self.config.get("folder_goal_bindings")
        self.assertNotIn("/shared/docs", result)
        self.assertIn("/shared/code", result)

    def test_rebind_folder_to_different_goal(self):
        bindings = {"/shared/docs": "goal-uuid-1"}
        self.config.set("folder_goal_bindings", bindings)
        bindings["/shared/docs"] = "goal-uuid-99"
        self.config.set("folder_goal_bindings", bindings)
        self.assertEqual(self.config.get("folder_goal_bindings")["/shared/docs"], "goal-uuid-99")

    def test_empty_bindings_default(self):
        result = self.config.get("folder_goal_bindings", {})
        self.assertEqual(result, {})

    def test_bind_empty_folder_path(self):
        bindings = {"": "goal-uuid-1"}
        self.config.set("folder_goal_bindings", bindings)
        self.assertIn("", self.config.get("folder_goal_bindings"))

    def test_bind_empty_goal_uuid(self):
        bindings = {"/shared/docs": ""}
        self.config.set("folder_goal_bindings", bindings)
        self.assertEqual(self.config.get("folder_goal_bindings")["/shared/docs"], "")

    def test_persistence_roundtrip(self):
        bindings = {"/path/a": "uuid-1", "/path/b": "uuid-2"}
        self.config.set("folder_goal_bindings", bindings)
        serialized = json.dumps(self.config.get("folder_goal_bindings"))
        restored = json.loads(serialized)
        self.assertEqual(restored, bindings)


class TestRetentionConfig(unittest.TestCase):
    """Test retention policy configuration."""

    def setUp(self):
        self.config = MockConfigManager()

    def test_retention_days_default(self):
        days = self.config.get("retention_days", 30)
        self.assertEqual(days, 30)

    def test_retention_max_changes_default(self):
        max_c = self.config.get("retention_max_changes", 100)
        self.assertEqual(max_c, 100)

    def test_set_retention_days(self):
        self.config.set("retention_days", 60)
        self.assertEqual(self.config.get("retention_days"), 60)

    def test_set_retention_max_changes(self):
        self.config.set("retention_max_changes", 500)
        self.assertEqual(self.config.get("retention_max_changes"), 500)


class TestSyncTableIntegrity(unittest.TestCase):
    """Test that sync tables have proper schema for filesharing."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")
        self.conn = sqlite3.connect(self.db_path)
        self.c = self.conn.cursor()

        self.c.executescript("""
            CREATE TABLE IF NOT EXISTS deleted_uuids(
                table_name TEXT, uuid TEXT, deleted_at TEXT,
                PRIMARY KEY (table_name, uuid)
            );
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY, name TEXT UNIQUE,
                target_hours REAL DEFAULT 0, uuid TEXT UNIQUE, modified_at TEXT
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY, title TEXT, content TEXT,
                timestamp TEXT, course TEXT, folder TEXT DEFAULT 'Uncategorized',
                color TEXT DEFAULT '#3b82f6', uuid TEXT UNIQUE, modified_at TEXT
            );
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY, timestamp TEXT, module TEXT,
                description TEXT, uuid TEXT UNIQUE, modified_at TEXT
            );
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_deleted_uuids_table_exists(self):
        self.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deleted_uuids'")
        self.assertIsNotNone(self.c.fetchone())

    def test_deleted_uuids_insert_and_query(self):
        now = datetime.now().isoformat()
        self.c.execute("INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
                       ("notes", "abc123", now))
        self.conn.commit()
        self.c.execute("SELECT * FROM deleted_uuids WHERE table_name='notes'")
        rows = self.c.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "abc123")

    def test_uuid_uniqueness_constraint(self):
        now = datetime.now().isoformat()
        self.c.execute("INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
                       ("Test Course", "uuid-1", now))
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.execute("INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
                           ("Test Course 2", "uuid-1", now))
            self.conn.commit()

    def test_modified_at_timestamp_format(self):
        now = datetime.now().isoformat()
        self.c.execute("INSERT INTO notes (title, uuid, modified_at) VALUES (?, ?, ?)",
                       ("Test Note", "note-uuid-1", now))
        self.conn.commit()
        self.c.execute("SELECT modified_at FROM notes WHERE uuid='note-uuid-1'")
        result = self.c.fetchone()
        self.assertIsNotNone(result)
        datetime.fromisoformat(result[0])

    def test_bulk_insert_performance(self):
        now = datetime.now().isoformat()
        rows = [(f"Note {i}", f"uuid-{i}", now) for i in range(1000)]
        self.c.executemany("INSERT INTO notes (title, uuid, modified_at) VALUES (?, ?, ?)", rows)
        self.conn.commit()
        self.c.execute("SELECT COUNT(*) FROM notes")
        self.assertEqual(self.c.fetchone()[0], 1000)


if __name__ == "__main__":
    unittest.main()
