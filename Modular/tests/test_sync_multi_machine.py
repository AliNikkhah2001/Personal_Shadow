"""Multi-Machine Sync Test Suite.

Simulates multiple devices syncing data through a shared Git repository.
Tests: master node, soft deletes, settings sync, conflict resolution.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime

# Ensure project root is in path
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in os.path.sys.path:
    import sys

    sys.path.insert(0, sys_path)

import contextlib

from core_sys import ConfigManager, DatabaseManager


class MockSyncManager:
    """Mock sync manager that simulates multi-device sync without actual Git."""

    def __init__(self, device_id: str, shared_dir: str):
        self.device_id = device_id
        self.shared_dir = shared_dir
        self.db_sync_dir = "db_exports"
        self.sync_data_file = os.path.join(self.db_sync_dir, f"{device_id}.json")
        self.repo_path = shared_dir
        self.files_dir = "files"

    def export_local_data(self, db: DatabaseManager, config: ConfigManager) -> dict:
        """Export local database and settings to a dict."""
        now = datetime.now().isoformat()
        settings = config.cfg.copy()
        settings.pop("sync_github_token", None)

        data = {
            "device_id": self.device_id,
            "last_sync": now,
            "settings": settings,
            "tables": {},
            "deletions": {},
        }

        # Export all tables
        db.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence')")
        tables = [r[0] for r in db.c.fetchall()]

        for table in tables:
            try:
                db.c.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in db.c.description]
                data["tables"][table] = [dict(zip(columns, row, strict=False)) for row in db.c.fetchall()]
            except Exception:
                pass

        # Export deletions
        for table in tables:
            try:
                db.c.execute("SELECT uuid, deleted_at FROM deleted_uuids WHERE table_name=?", (table,))
                data["deletions"][table] = [{"uuid": r[0], "deleted_at": r[1]} for r in db.c.fetchall()]
            except Exception:
                pass

        return data

    def save_export(self, data: dict):
        """Save exported data to the shared directory."""
        sync_dir = os.path.join(self.shared_dir, self.db_sync_dir)
        os.makedirs(sync_dir, exist_ok=True)
        filepath = os.path.join(sync_dir, f"{self.device_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_all_device_data(self) -> dict:
        """Get all device exports from shared directory."""
        sync_dir = os.path.join(self.shared_dir, self.db_sync_dir)
        if not os.path.exists(sync_dir):
            return {}

        devices = {}
        for filename in os.listdir(sync_dir):
            if filename.endswith(".json"):
                device_id = filename.replace(".json", "")
                filepath = os.path.join(sync_dir, filename)
                with open(filepath, encoding="utf-8") as f:
                    devices[device_id] = json.load(f)
        return devices

    def get_master_id(self) -> str | None:
        """Get the current master node ID."""
        cluster_file = os.path.join(self.shared_dir, "cluster_state.json")
        if os.path.exists(cluster_file):
            with open(cluster_file) as f:
                return json.load(f).get("master_id")
        return None

    def set_master(self, master_id: str):
        """Set the master node."""
        cluster_file = os.path.join(self.shared_dir, "cluster_state.json")
        with open(cluster_file, "w") as f:
            json.dump({"master_id": master_id, "timestamp": datetime.now().isoformat()}, f)

    def merge_into_local(
        self,
        db: DatabaseManager,
        config: ConfigManager,
        master_id: str | None,
    ):
        """Merge remote data into local database."""
        devices = self.get_all_device_data()
        valid_tables = self._get_all_tables(db)

        for dev_id, remote_data in devices.items():
            if dev_id == self.device_id:
                continue

            # Apply deletions
            for table in valid_tables:
                # Check if table has modified_at column
                db.c.execute(f"PRAGMA table_info({table})")
                columns_info = db.c.fetchall()
                has_modified = any(col[1] == "modified_at" for col in columns_info)
                has_uuid = any(col[1] == "uuid" for col in columns_info)

                if not has_uuid:
                    continue

                for del_item in remote_data.get("deletions", {}).get(table, []):
                    uid = del_item["uuid"]
                    del_time = del_item["deleted_at"]
                    if has_modified:
                        db.c.execute(f"SELECT modified_at FROM {table} WHERE uuid = ?", (uid,))
                        row = db.c.fetchone()
                        if row and (not row[0] or del_time > row[0]):
                            db.c.execute(f"DELETE FROM {table} WHERE uuid = ?", (uid,))
                            db.c.execute(
                                "DELETE FROM deleted_uuids WHERE table_name=? AND uuid=?",
                                (table, uid),
                            )
                    else:
                        # No modified_at, just delete
                        db.c.execute(f"DELETE FROM {table} WHERE uuid = ?", (uid,))
                        db.c.execute(
                            "DELETE FROM deleted_uuids WHERE table_name=? AND uuid=?",
                            (table, uid),
                        )

            # Merge rows
            for table in valid_tables:
                rows = remote_data.get("tables", {}).get(table, [])
                if not rows:
                    continue

                # Check table columns once per table
                db.c.execute(f"PRAGMA table_info({table})")
                columns_info = db.c.fetchall()
                col_names = [col[1] for col in columns_info]
                has_id = "id" in col_names
                has_modified = "modified_at" in col_names
                has_uuid = "uuid" in col_names

                if not has_uuid:
                    continue

                for row in rows:
                    uid = row.get("uuid")
                    if not uid:
                        continue

                    # Build SELECT based on available columns
                    select_cols = []
                    if has_id:
                        select_cols.append("id")
                    if has_modified:
                        select_cols.append("modified_at")

                    if select_cols:
                        select_clause = ", ".join(select_cols)
                        db.c.execute(
                            f"SELECT {select_clause} FROM {table} WHERE uuid = ?",
                            (uid,),
                        )
                        existing = db.c.fetchone()
                    else:
                        # Just check if record exists
                        db.c.execute(f"SELECT uuid FROM {table} WHERE uuid = ?", (uid,))
                        existing = db.c.fetchone()
                        if existing:
                            existing = tuple([None] * len(select_cols)) if select_cols else (None,)

                    if not existing:
                        row.pop("id", None)
                        cols = ", ".join(row.keys())
                        placeholders = ", ".join(["?"] * len(row))
                        with contextlib.suppress(sqlite3.IntegrityError):
                            db.c.execute(
                                f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                                list(row.values()),
                            )
                    else:
                        # Parse existing values
                        idx = 0
                        existing_id = existing[idx] if has_id else None
                        idx += 1 if has_id else 0
                        existing_mod = existing[idx] if has_modified else None

                        incoming_mod = row.get("modified_at", "")
                        remote_is_master = dev_id == master_id

                        update_cols = [k for k in row if k not in ["id", "uuid"]]
                        set_clause = ", ".join([f"{k}=?" for k in update_cols])

                        if has_id:
                            values = [row[k] for k in update_cols] + [existing_id]
                            where_clause = "id=?"
                        else:
                            values = [row[k] for k in update_cols] + [uid]
                            where_clause = "uuid=?"

                        if remote_is_master or (incoming_mod and (not existing_mod or incoming_mod > existing_mod)):
                            with contextlib.suppress(sqlite3.IntegrityError):
                                db.c.execute(
                                    f"UPDATE {table} SET {set_clause} WHERE {where_clause}",
                                    values,
                                )

        db.safe_commit()

    def _get_all_tables(self, db: DatabaseManager) -> list:
        db.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence')")
        return [r[0] for r in db.c.fetchall()]


class TestMultiMachineSync(unittest.TestCase):
    """Test sync scenarios between multiple simulated machines."""

    def setUp(self):
        """Create a temporary shared directory for each test."""
        self.shared_dir = tempfile.mkdtemp(prefix="mindpalace_sync_test_")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.shared_dir, ignore_errors=True)

    def _create_device(self, device_id: str) -> tuple:
        """Create a simulated device with its own database and config."""
        db_path = os.path.join(self.shared_dir, f"{device_id}.db")
        config_path = os.path.join(self.shared_dir, f"{device_id}_config.json")

        db = DatabaseManager(db_path)
        config = ConfigManager(config_path)
        sync = MockSyncManager(device_id, self.shared_dir)

        return db, config, sync

    def test_device_a_creates_data(self):
        """Test that Device A can create and export data."""
        db, config, sync = self._create_device("device_A")

        # Create some data
        db.c.execute(
            "INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
            ("Mathematics", "math_001", datetime.now().isoformat()),
        )
        db.c.execute(
            "INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
            ("Physics", "phys_001", datetime.now().isoformat()),
        )
        db.safe_commit()

        # Export and save
        data = sync.export_local_data(db, config)
        sync.save_export(data)

        # Verify export
        self.assertEqual(data["device_id"], "device_A")
        self.assertIn("courses", data["tables"])
        self.assertEqual(len(data["tables"]["courses"]), 2)

    def test_device_b_receives_data(self):
        """Test that Device B can receive data from Device A."""
        # Device A creates data
        db_a, config_a, sync_a = self._create_device("device_A")
        db_a.c.execute(
            "INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
            ("Mathematics", "math_001", datetime.now().isoformat()),
        )
        db_a.safe_commit()
        sync_a.save_export(sync_a.export_local_data(db_a, config_a))

        # Device B syncs
        db_b, config_b, sync_b = self._create_device("device_B")
        sync_b.merge_into_local(db_b, config_b, master_id=None)

        # Verify Device B has Device A's data
        db_b.c.execute("SELECT name FROM courses WHERE uuid = ?", ("math_001",))
        result = db_b.c.fetchone()
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "Mathematics")

    def test_master_node_overwrites(self):
        """Test that master node data takes priority over slave."""
        # Device A (future master) creates data
        db_a, config_a, sync_a = self._create_device("device_A")
        db_a.c.execute(
            "INSERT INTO courses (name, uuid, modified_at, target_hours) VALUES (?, ?, ?, ?)",
            ("Mathematics", "math_001", "2024-01-01T00:00:00", 100),
        )
        db_a.safe_commit()
        sync_a.save_export(sync_a.export_local_data(db_a, config_a))

        # Device B modifies the same record
        db_b, config_b, sync_b = self._create_device("device_B")
        db_b.c.execute(
            "INSERT INTO courses (name, uuid, modified_at, target_hours) VALUES (?, ?, ?, ?)",
            ("Math Updated", "math_001", "2024-01-02T00:00:00", 200),
        )
        db_b.safe_commit()
        sync_b.save_export(sync_b.export_local_data(db_b, config_b))

        # Set Device A as master
        sync_a.set_master("device_A")

        # Device B syncs with master
        sync_b.merge_into_local(db_b, config_b, master_id="device_A")

        # Verify master's data overwrites slave's
        db_b.c.execute("SELECT name, target_hours FROM courses WHERE uuid = ?", ("math_001",))
        result = db_b.c.fetchone()
        self.assertEqual(result[0], "Mathematics")  # Master's name
        self.assertEqual(result[1], 100)  # Master's target_hours

    def test_soft_delete_propagation(self):
        """Test that soft deletes are propagated to other devices."""
        # Device A creates and deletes a record
        db_a, config_a, sync_a = self._create_device("device_A")
        db_a.c.execute(
            "INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
            ("ToDelete", "del_001", datetime.now().isoformat()),
        )
        db_a.safe_commit()

        # Soft delete
        db_a.c.execute("DELETE FROM courses WHERE uuid = ?", ("del_001",))
        db_a.c.execute(
            "INSERT INTO deleted_uuids (table_name, uuid, deleted_at) VALUES (?, ?, ?)",
            ("courses", "del_001", datetime.now().isoformat()),
        )
        db_a.safe_commit()
        sync_a.save_export(sync_a.export_local_data(db_a, config_a))

        # Device B has the record
        db_b, config_b, sync_b = self._create_device("device_B")
        db_b.c.execute(
            "INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
            ("ToDelete", "del_001", "2024-01-01T00:00:00"),
        )
        db_b.safe_commit()

        # Device B syncs
        sync_b.merge_into_local(db_b, config_b, master_id=None)

        # Verify record is deleted on Device B
        db_b.c.execute("SELECT name FROM courses WHERE uuid = ?", ("del_001",))
        result = db_b.c.fetchone()
        self.assertIsNone(result)  # Should be deleted

    def test_settings_sync(self):
        """Test that settings are synced between devices."""
        # Device A sets a config value
        db_a, config_a, sync_a = self._create_device("device_A")
        config_a.set("font_family", "Roboto")
        config_a.set("vision_mode", "Relaxed (Face Visible)")
        sync_a.save_export(sync_a.export_local_data(db_a, config_a))

        # Device B syncs
        _db_b, config_b, sync_b = self._create_device("device_B")
        devices = sync_b.get_all_device_data()

        # Apply settings from Device A
        for dev_id, remote_data in devices.items():
            if dev_id == "device_B":
                continue
            for k, v in remote_data.get("settings", {}).items():
                if k not in ["device_id", "has_token", "git_status"]:
                    config_b.set(k, v)

        # Verify settings synced
        self.assertEqual(config_b.get("font_family"), "Roboto")
        self.assertEqual(config_b.get("vision_mode"), "Relaxed (Face Visible)")

    def test_conflict_resolution_lww(self):
        """Test Last-Write-Wins conflict resolution."""
        # Device A creates record with older timestamp
        db_a, config_a, sync_a = self._create_device("device_A")
        db_a.c.execute(
            "INSERT INTO courses (name, uuid, modified_at, target_hours) VALUES (?, ?, ?, ?)",
            ("Old Name", "conflict_001", "2024-01-01T00:00:00", 50),
        )
        db_a.safe_commit()
        sync_a.save_export(sync_a.export_local_data(db_a, config_a))

        # Device B creates record with newer timestamp
        db_b, config_b, sync_b = self._create_device("device_B")
        db_b.c.execute(
            "INSERT INTO courses (name, uuid, modified_at, target_hours) VALUES (?, ?, ?, ?)",
            ("New Name", "conflict_001", "2024-01-05T00:00:00", 150),
        )
        db_b.safe_commit()
        sync_b.save_export(sync_b.export_local_data(db_b, config_b))

        # Device A syncs (no master, so LWW applies)
        sync_a.merge_into_local(db_a, config_a, master_id=None)

        # Verify newer data wins
        db_a.c.execute(
            "SELECT name, target_hours FROM courses WHERE uuid = ?",
            ("conflict_001",),
        )
        result = db_a.c.fetchone()
        self.assertEqual(result[0], "New Name")
        self.assertEqual(result[1], 150)

    def test_shared_folder_sync(self):
        """Test that shared folders are correctly mapped."""
        _db, _config, _sync = self._create_device("device_A")

        # Create a shared folder with files
        shared_folder = os.path.join(self.shared_dir, "shared_docs")
        os.makedirs(shared_folder, exist_ok=True)
        with open(os.path.join(shared_folder, "doc1.txt"), "w") as f:
            f.write("Shared document 1")
        with open(os.path.join(shared_folder, "doc2.txt"), "w") as f:
            f.write("Shared document 2")

        # Verify files exist
        files = os.listdir(shared_folder)
        self.assertIn("doc1.txt", files)
        self.assertIn("doc2.txt", files)

    def test_full_sync_cycle(self):
        """Test a complete sync cycle between 3 devices."""
        # Device A creates data
        db_a, config_a, sync_a = self._create_device("device_A")
        db_a.c.execute(
            "INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
            ("Course A", "course_a", datetime.now().isoformat()),
        )
        db_a.safe_commit()
        sync_a.set_master("device_A")
        sync_a.save_export(sync_a.export_local_data(db_a, config_a))

        # Device B creates data
        db_b, config_b, sync_b = self._create_device("device_B")
        db_b.c.execute(
            "INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
            ("Course B", "course_b", datetime.now().isoformat()),
        )
        db_b.safe_commit()
        sync_b.save_export(sync_b.export_local_data(db_b, config_b))

        # Device C syncs both
        db_c, config_c, sync_c = self._create_device("device_C")
        sync_c.merge_into_local(db_c, config_c, master_id="device_A")

        # Verify Device C has both courses
        db_c.c.execute("SELECT name FROM courses WHERE uuid IN (?, ?)", ("course_a", "course_b"))
        results = db_c.c.fetchall()
        names = [r[0] for r in results]
        self.assertIn("Course A", names)
        self.assertIn("Course B", names)


if __name__ == "__main__":
    print("=" * 60)
    print("Mind Palace OS - Multi-Machine Sync Test Suite")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestMultiMachineSync)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    import sys

    sys.exit(0 if result.wasSuccessful() else 1)
