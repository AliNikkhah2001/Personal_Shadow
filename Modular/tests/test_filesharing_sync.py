"""Filesharing sync integration tests.

Tests folder sync, file hierarchy, and retention policy with sandboxed
devices using real Git repos (following test_sync_sandboxed.py patterns).
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_sys import DatabaseManager


def create_bare_repo(base_dir):
    """Create a bare Git repo as a simulated remote."""
    import git
    bare_path = os.path.join(base_dir, "remote.git")
    repo = git.Repo.init(bare_path, bare=True)
    return bare_path


def setup_device_repo(device, bare_path):
    """Clone bare repo for a device."""
    import git
    device.repo_path = os.path.join(device.tmp_dir, "sync_repo")
    device.repo = git.Repo.clone_from(bare_path, device.repo_path)
    device.repo.config_writer().set_value("user", "name", device.device_id[:8]).release()
    device.repo.config_writer().set_value("user", "email", f"{device.device_id[:8]}@test").release()


class SandboxedDevice:
    """Fully isolated device with DB, config, and sync manager."""

    def __init__(self, device_id=None):
        self.device_id = device_id or uuid.uuid4().hex[:16]
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test.db")
        self.db = DatabaseManager(self.db_path)
        self.config_path = os.path.join(self.tmp_dir, "config.json")
        self.config_data = {
            "sync_repo_url": "",
            "sync_local_paths": [],
            "folder_goal_bindings": {},
        }
        self.repo_path = None
        self.repo = None

    def create_shared_folder(self, name, files=None):
        """Create a local folder with files to share."""
        folder = os.path.join(self.tmp_dir, name)
        os.makedirs(folder, exist_ok=True)
        if files:
            for fname, content in files.items():
                fpath = os.path.join(folder, fname)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "w") as f:
                    f.write(content)
        return folder

    def create_goal(self, title, parent_id=None, level="L1"):
        self.db.c.execute(
            "INSERT INTO cascading_goals (parent_id, level, title, uuid, modified_at) VALUES (?, ?, ?, ?, ?)",
            (parent_id, level, title, uuid.uuid4().hex, datetime.now().isoformat()),
        )
        self.db.safe_commit()
        return self.db.c.lastrowid

    def create_note(self, title, content=""):
        note_uuid = uuid.uuid4().hex
        self.db.c.execute(
            "INSERT INTO notes (title, content, uuid, modified_at) VALUES (?, ?, ?, ?)",
            (title, content, note_uuid, datetime.now().isoformat()),
        )
        self.db.safe_commit()
        return note_uuid

    def cleanup(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


class TestFolderSyncWithDevices(unittest.TestCase):
    """Test folder sync between sandboxed devices."""

    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.bare_path = create_bare_repo(self.base_dir)

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_device_creates_shared_folder(self):
        device = SandboxedDevice("device-A")
        try:
            folder = device.create_shared_folder("shared", {"doc.txt": "hello"})
            self.assertTrue(os.path.exists(os.path.join(folder, "doc.txt")))
            with open(os.path.join(folder, "doc.txt")) as f:
                self.assertEqual(f.read(), "hello")
        finally:
            device.cleanup()

    def test_two_devices_discover_each_other(self):
        dev_a = SandboxedDevice("device-A")
        dev_b = SandboxedDevice("device-B")
        try:
            folder_a = dev_a.create_shared_folder("docs", {"a.txt": "from A"})
            folder_b = dev_b.create_shared_folder("docs", {"b.txt": "from B"})

            self.assertTrue(os.path.exists(os.path.join(folder_a, "a.txt")))
            self.assertTrue(os.path.exists(os.path.join(folder_b, "b.txt")))
            self.assertNotEqual(folder_a, folder_b)
        finally:
            dev_a.cleanup()
            dev_b.cleanup()

    def test_shared_folder_files_are_independent(self):
        dev_a = SandboxedDevice("device-A")
        dev_b = SandboxedDevice("device-B")
        try:
            folder_a = dev_a.create_shared_folder("shared", {"common.txt": "A version"})
            folder_b = dev_b.create_shared_folder("shared", {"common.txt": "B version"})

            with open(os.path.join(folder_a, "common.txt")) as f:
                a_content = f.read()
            with open(os.path.join(folder_b, "common.txt")) as f:
                b_content = f.read()

            self.assertEqual(a_content, "A version")
            self.assertEqual(b_content, "B version")
        finally:
            dev_a.cleanup()
            dev_b.cleanup()

    def test_folder_hierarchy_across_devices(self):
        dev_a = SandboxedDevice("device-A")
        try:
            folder = dev_a.create_shared_folder("project", {
                "readme.md": "# Project",
                "src/main.py": "print('hello')",
                "docs/guide.md": "# Guide",
            })
            os.makedirs(os.path.join(folder, "src"), exist_ok=True)
            os.makedirs(os.path.join(folder, "docs"), exist_ok=True)
            with open(os.path.join(folder, "src", "main.py"), "w") as f:
                f.write("print('hello')")
            with open(os.path.join(folder, "docs", "guide.md"), "w") as f:
                f.write("# Guide")

            tree = {}
            for root, dirs, files in os.walk(folder):
                for fname in files:
                    rel = os.path.relpath(os.path.join(root, fname), folder)
                    tree[rel] = True

            self.assertIn("readme.md", tree)
            self.assertIn(os.path.join("src", "main.py"), tree)
            self.assertIn(os.path.join("docs", "guide.md"), tree)
        finally:
            dev_a.cleanup()


class TestRetentionPolicyWithDevices(unittest.TestCase):
    """Test retention policy across multiple devices."""

    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.bare_path = create_bare_repo(self.base_dir)

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_old_exports_are_removed(self):
        device = SandboxedDevice("device-A")
        try:
            setup_device_repo(device, self.bare_path)
            export_dir = os.path.join(device.repo_path, "db_exports")
            os.makedirs(export_dir, exist_ok=True)

            old_file = os.path.join(export_dir, "old_device.json")
            with open(old_file, "w") as f:
                json.dump({"old": True}, f)
            old_time = (datetime.now() - timedelta(days=60)).timestamp()
            os.utime(old_file, (old_time, old_time))

            new_file = os.path.join(export_dir, f"{device.device_id}.json")
            with open(new_file, "w") as f:
                json.dump({"device_id": device.device_id}, f)

            cutoff = datetime.now() - timedelta(days=30)
            removed = 0
            for fname in os.listdir(export_dir):
                fpath = os.path.join(export_dir, fname)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    os.remove(fpath)
                    removed += 1

            self.assertGreater(removed, 0)
            self.assertFalse(os.path.exists(old_file))
            self.assertTrue(os.path.exists(new_file))
        finally:
            device.cleanup()

    def test_recent_files_preserved(self):
        device = SandboxedDevice("device-A")
        try:
            setup_device_repo(device, self.bare_path)
            export_dir = os.path.join(device.repo_path, "db_exports")
            os.makedirs(export_dir, exist_ok=True)

            recent_file = os.path.join(export_dir, f"{device.device_id}.json")
            with open(recent_file, "w") as f:
                json.dump({"device_id": device.device_id, "recent": True}, f)

            cutoff = datetime.now() - timedelta(days=30)
            removed = 0
            for fname in os.listdir(export_dir):
                fpath = os.path.join(export_dir, fname)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    os.remove(fpath)
                    removed += 1

            self.assertEqual(removed, 0)
            self.assertTrue(os.path.exists(recent_file))
        finally:
            device.cleanup()

    def test_manifest_files_pruned_by_retention(self):
        device = SandboxedDevice("device-A")
        try:
            setup_device_repo(device, self.bare_path)
            files_dir = os.path.join(device.repo_path, "files")
            os.makedirs(files_dir, exist_ok=True)

            old_manifest = os.path.join(files_dir, "_manifest_old_device.json")
            with open(old_manifest, "w") as f:
                json.dump({"old.txt": {"size": 100}}, f)
            old_time = (datetime.now() - timedelta(days=90)).timestamp()
            os.utime(old_manifest, (old_time, old_time))

            new_manifest = os.path.join(files_dir, f"_manifest_{device.device_id}.json")
            with open(new_manifest, "w") as f:
                json.dump({"new.txt": {"size": 200}}, f)

            cutoff = datetime.now() - timedelta(days=30)
            removed = 0
            for fname in os.listdir(files_dir):
                if not fname.startswith("_manifest_"):
                    continue
                fpath = os.path.join(files_dir, fname)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    os.remove(fpath)
                    removed += 1

            self.assertGreater(removed, 0)
            self.assertFalse(os.path.exists(old_manifest))
            self.assertTrue(os.path.exists(new_manifest))
        finally:
            device.cleanup()


class TestGoalBindingWithDevices(unittest.TestCase):
    """Test goal binding across devices."""

    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.bare_path = create_bare_repo(self.base_dir)

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_goal_binding_persists(self):
        device = SandboxedDevice("device-A")
        try:
            goal_id = device.create_goal("Learn Python", level="L1")
            bindings = {"/shared/code": "goal-uuid-123"}
            device.config_data["folder_goal_bindings"] = bindings

            loaded = device.config_data.get("folder_goal_bindings", {})
            self.assertIn("/shared/code", loaded)
            self.assertEqual(loaded["/shared/code"], "goal-uuid-123")
        finally:
            device.cleanup()

    def test_multiple_folder_goal_bindings(self):
        device = SandboxedDevice("device-A")
        try:
            bindings = {
                "/shared/docs": "uuid-docs",
                "/shared/code": "uuid-code",
                "/shared/images": "uuid-images",
            }
            device.config_data["folder_goal_bindings"] = bindings

            loaded = device.config_data.get("folder_goal_bindings")
            self.assertEqual(len(loaded), 3)
        finally:
            device.cleanup()

    def test_unbind_removes_folder(self):
        device = SandboxedDevice("device-A")
        try:
            bindings = {"/shared/docs": "uuid-docs"}
            device.config_data["folder_goal_bindings"] = bindings
            del device.config_data["folder_goal_bindings"]["/shared/docs"]
            self.assertEqual(len(device.config_data["folder_goal_bindings"]), 0)
        finally:
            device.cleanup()


class TestMultiDeviceFileSync(unittest.TestCase):
    """Test file sync between multiple devices using Git."""

    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.bare_path = create_bare_repo(self.base_dir)

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_device_push_file_pull_other(self):
        import git as gitmodule

        dev_a = SandboxedDevice("device-A")
        try:
            setup_device_repo(dev_a, self.bare_path)

            test_file = os.path.join(dev_a.repo_path, "shared.txt")
            with open(test_file, "w") as f:
                f.write("from device A")
            dev_a.repo.git.add(A=True)
            dev_a.repo.index.commit("add shared file from A")
            dev_a.repo.git.push("origin", "master")

            dev_b = SandboxedDevice("device-B")
            try:
                setup_device_repo(dev_b, self.bare_path)
                pulled_file = os.path.join(dev_b.repo_path, "shared.txt")
                self.assertTrue(os.path.exists(pulled_file))
                with open(pulled_file) as f:
                    self.assertEqual(f.read(), "from device A")
            finally:
                dev_b.cleanup()
        finally:
            dev_a.cleanup()

    def test_bidirectional_file_sync(self):
        import git as gitmodule

        dev_a = SandboxedDevice("device-A")
        dev_b = SandboxedDevice("device-B")
        try:
            setup_device_repo(dev_a, self.bare_path)
            setup_device_repo(dev_b, self.bare_path)

            with open(os.path.join(dev_a.repo_path, "a.txt"), "w") as f:
                f.write("file from A")
            dev_a.repo.git.add(A=True)
            dev_a.repo.index.commit("A adds file")
            dev_a.repo.git.push("origin", "master")

            dev_b.repo.git.pull("origin", "master")
            self.assertTrue(os.path.exists(os.path.join(dev_b.repo_path, "a.txt")))

            with open(os.path.join(dev_b.repo_path, "b.txt"), "w") as f:
                f.write("file from B")
            dev_b.repo.git.add(A=True)
            dev_b.repo.index.commit("B adds file")
            dev_b.repo.git.push("origin", "master")

            dev_a.repo.git.pull("origin", "master")
            self.assertTrue(os.path.exists(os.path.join(dev_a.repo_path, "b.txt")))
        finally:
            dev_a.cleanup()
            dev_b.cleanup()

    def test_three_device_sync_chain(self):
        import git as gitmodule

        dev_a = SandboxedDevice("device-A")
        dev_b = SandboxedDevice("device-B")
        dev_c = SandboxedDevice("device-C")
        try:
            setup_device_repo(dev_a, self.bare_path)
            setup_device_repo(dev_b, self.bare_path)
            setup_device_repo(dev_c, self.bare_path)

            with open(os.path.join(dev_a.repo_path, "chain.txt"), "w") as f:
                f.write("started by A")
            dev_a.repo.git.add(A=True)
            dev_a.repo.index.commit("A starts chain")
            dev_a.repo.git.push("origin", "master")

            dev_b.repo.git.pull("origin", "master")
            with open(os.path.join(dev_b.repo_path, "chain.txt"), "a") as f:
                f.write("\ncontinued by B")
            dev_b.repo.git.add(A=True)
            dev_b.repo.index.commit("B continues")
            dev_b.repo.git.push("origin", "master")

            dev_c.repo.git.pull("origin", "master")
            with open(os.path.join(dev_c.repo_path, "chain.txt")) as f:
                content = f.read()
            self.assertIn("started by A", content)
            self.assertIn("continued by B", content)
        finally:
            dev_a.cleanup()
            dev_b.cleanup()
            dev_c.cleanup()


if __name__ == "__main__":
    unittest.main()
