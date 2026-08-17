"""Filesharing integration tests.

End-to-end tests for the full filesharing pipeline: folder mapping,
hierarchy building, goal binding, changelog generation, and retention.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.filesharing import FileSharingHandler
from core_sys import DatabaseManager


class MockSyncManager:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.db_sync_dir = "db_exports"
        self.files_dir = "files"
        self.device_id = "integration-test-device"


class MockBridge:
    def __init__(self, repo_path, config_data=None):
        self.sync_manager = MockSyncManager(repo_path)
        self.config_data = config_data or {}


class TestEndToEndFolderWorkflow(unittest.TestCase):
    """Test complete folder mapping -> hierarchy -> goal binding workflow."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmp_dir, "sync_repo")
        os.makedirs(os.path.join(self.repo_path, "db_exports"), exist_ok=True)
        os.makedirs(os.path.join(self.repo_path, "files"), exist_ok=True)

        self.bridge = MockBridge(self.repo_path)
        self.handler = FileSharingHandler(self.bridge)

        self.shared_folder = os.path.join(self.tmp_dir, "shared_data")
        os.makedirs(os.path.join(self.shared_folder, "documents"))
        os.makedirs(os.path.join(self.shared_folder, "code"))
        os.makedirs(os.path.join(self.shared_folder, "images"))

        for subdir, files in [
            ("documents", {"readme.md": "# Project Docs", "guide.txt": "User guide"}),
            ("code", {"main.py": "print('hello')", "utils.py": "def helper(): pass"}),
            ("images", {"photo1.jpg": "fake jpg", "logo.png": "fake png"}),
        ]:
            for fname, content in files.items():
                with open(os.path.join(self.shared_folder, subdir, fname), "w") as f:
                    f.write(content)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch("handlers.filesharing.config")
    def test_full_workflow(self, mock_config):
        mock_config.get.return_value = {}
        mock_config.set = MagicMock(side_effect=lambda k, v: mock_config.get.return_value.update({k: v}) or mock_config.cfg.__setitem__(k, v))

        hierarchy = json.loads(self.handler.get_folder_hierarchy({"path": self.shared_folder}))
        self.assertIn("tree", hierarchy)
        tree = hierarchy["tree"]
        self.assertEqual(tree["type"], "directory")
        self.assertEqual(len(tree["children"]), 3)
        child_names = {c["name"] for c in tree["children"]}
        self.assertEqual(child_names, {"documents", "code", "images"})

        docs_node = next(c for c in tree["children"] if c["name"] == "documents")
        self.assertEqual(len(docs_node["children"]), 2)

        bind_result = json.loads(self.handler.bind_folder_goal({
            "folder": self.shared_folder,
            "goal_uuid": "goal-uuid-abc",
        }))
        self.assertEqual(bind_result["status"], "success")

        bindings = json.loads(self.handler.get_goal_folder_bindings({}))
        self.assertIn(self.shared_folder, bindings["bindings"])

    def test_hierarchy_file_sizes(self):
        hierarchy = json.loads(self.handler.get_folder_hierarchy({"path": self.shared_folder}))
        tree = hierarchy["tree"]

        code_node = next(c for c in tree["children"] if c["name"] == "code")
        for child in code_node["children"]:
            self.assertIn("size", child)
            self.assertGreater(child["size"], 0)

    def test_hierarchy_paths_are_absolute(self):
        hierarchy = json.loads(self.handler.get_folder_hierarchy({"path": self.shared_folder}))
        tree = hierarchy["tree"]

        self.assertTrue(os.path.isabs(tree["path"]))
        for child in tree["children"]:
            self.assertTrue(os.path.isabs(child["path"]))


class TestChangelogWithCommits(unittest.TestCase):
    """Test changelog generation with actual Git commits."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmp_dir, "sync_repo")

        import git as gitmodule
        self.repo = gitmodule.Repo.init(self.repo_path)
        self.repo.config_writer().set_value("user", "name", "Test").release()
        self.repo.config_writer().set_value("user", "email", "test@test").release()

        os.makedirs(os.path.join(self.repo_path, "db_exports"), exist_ok=True)
        os.makedirs(os.path.join(self.repo_path, "files"), exist_ok=True)

        self.bridge = MockBridge(self.repo_path)
        self.handler = FileSharingHandler(self.bridge)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_changelog_after_commits(self):
        for i in range(5):
            with open(os.path.join(self.repo_path, f"file{i}.txt"), "w") as f:
                f.write(f"content {i}")
            self.repo.git.add(A=True)
            self.repo.index.commit(f"add file{i}")

        result = json.loads(self.handler.get_folder_changelog({
            "path": self.tmp_dir,
            "days": 30,
        }))
        self.assertGreaterEqual(len(result["changelog"]), 5)

    def test_changelog_respects_days_filter(self):
        for i in range(3):
            with open(os.path.join(self.repo_path, f"recent{i}.txt"), "w") as f:
                f.write(f"recent {i}")
            self.repo.git.add(A=True)
            self.repo.index.commit(f"add recent{i}")

        result = json.loads(self.handler.get_folder_changelog({
            "path": self.tmp_dir,
            "days": 1,
        }))
        self.assertGreaterEqual(len(result["changelog"]), 1)

    def test_changelog_entry_structure(self):
        with open(os.path.join(self.repo_path, "test.txt"), "w") as f:
            f.write("test")
        self.repo.git.add(A=True)
        self.repo.index.commit("add test file")

        result = json.loads(self.handler.get_folder_changelog({
            "path": self.tmp_dir,
            "days": 30,
        }))
        entry = result["changelog"][-1]
        self.assertIn("commit", entry)
        self.assertIn("timestamp", entry)
        self.assertIn("device_id", entry)
        self.assertIn("action", entry)
        self.assertIn("file_path", entry)


class TestRetentionEndToEnd(unittest.TestCase):
    """Test retention policy end-to-end."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmp_dir, "sync_repo")
        os.makedirs(os.path.join(self.repo_path, "db_exports"), exist_ok=True)
        os.makedirs(os.path.join(self.repo_path, "files"), exist_ok=True)

        self.bridge = MockBridge(self.repo_path)
        self.handler = FileSharingHandler(self.bridge)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_retention_removes_old_keeps_new(self):
        export_dir = os.path.join(self.repo_path, "db_exports")

        old_file = os.path.join(export_dir, "old_device.json")
        with open(old_file, "w") as f:
            json.dump({"old": True}, f)
        old_time = (datetime.now() - timedelta(days=60)).timestamp()
        os.utime(old_file, (old_time, old_time))

        new_file = os.path.join(export_dir, "new_device.json")
        with open(new_file, "w") as f:
            json.dump({"new": True}, f)

        result = json.loads(self.handler.apply_retention_policy({"days": 30}))
        self.assertGreater(result["removed"], 0)
        self.assertFalse(os.path.exists(old_file))
        self.assertTrue(os.path.exists(new_file))

    def test_retention_preserves_manifest_files(self):
        files_dir = os.path.join(self.repo_path, "files")
        data_file = os.path.join(files_dir, "important_data.txt")
        with open(data_file, "w") as f:
            f.write("important")

        result = json.loads(self.handler.apply_retention_policy({"days": 30}))
        self.assertTrue(os.path.exists(data_file))

    def test_retention_with_various_ages(self):
        export_dir = os.path.join(self.repo_path, "db_exports")
        ages_days = [1, 10, 30, 31, 60, 90]
        for age in ages_days:
            fname = f"device_{age}d.json"
            fpath = os.path.join(export_dir, fname)
            with open(fpath, "w") as f:
                json.dump({"age": age}, f)
            age_time = (datetime.now() - timedelta(days=age)).timestamp()
            os.utime(fpath, (age_time, age_time))

        result = json.loads(self.handler.apply_retention_policy({"days": 30}))
        remaining = os.listdir(export_dir)
        self.assertIn("device_1d.json", remaining)
        self.assertIn("device_10d.json", remaining)
        self.assertIn("device_30d.json", remaining)
        self.assertNotIn("device_31d.json", remaining)
        self.assertNotIn("device_60d.json", remaining)
        self.assertNotIn("device_90d.json", remaining)


class TestSyntheticDeviceScenario(unittest.TestCase):
    """Test with synthetic device data simulating real usage."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmp_dir, "sync_repo")
        os.makedirs(os.path.join(self.repo_path, "db_exports"), exist_ok=True)
        os.makedirs(os.path.join(self.repo_path, "files"), exist_ok=True)

        self.bridge = MockBridge(self.repo_path)
        self.handler = FileSharingHandler(self.bridge)

        for device_name, files in [
            ("device_laptop", {"notes.txt": "laptop notes", "todo.md": "laptop todo"}),
            ("device_phone", {"photos.jpg": "phone photos", "voice.mp3": "voice memo"}),
            ("device_desktop", {"project.py": "desktop code", "data.csv": "csv data"}),
        ]:
            folder = os.path.join(self.tmp_dir, device_name)
            os.makedirs(folder, exist_ok=True)
            for fname, content in files.items():
                with open(os.path.join(folder, fname), "w") as f:
                    f.write(content)

            manifest = os.path.join(self.repo_path, "files", f"_manifest_{device_name}.json")
            with open(manifest, "w") as f:
                json.dump({fname: {"size": len(content)} for fname, content in files.items()}, f)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_all_device_folders_are_discoverable(self):
        for device_name in ["device_laptop", "device_phone", "device_desktop"]:
            folder = os.path.join(self.tmp_dir, device_name)
            self.assertTrue(os.path.exists(folder))
            self.assertTrue(len(os.listdir(folder)) > 0)

    def test_all_device_manifests_exist(self):
        files_dir = os.path.join(self.repo_path, "files")
        for device_name in ["device_laptop", "device_phone", "device_desktop"]:
            manifest = os.path.join(files_dir, f"_manifest_{device_name}.json")
            self.assertTrue(os.path.exists(manifest))
            with open(manifest) as f:
                data = json.load(f)
                self.assertGreater(len(data), 0)

    def test_hierarchy_of_all_devices(self):
        for device_name in ["device_laptop", "device_phone", "device_desktop"]:
            folder = os.path.join(self.tmp_dir, device_name)
            result = json.loads(self.handler.get_folder_hierarchy({"path": folder}))
            tree = result["tree"]
            self.assertEqual(tree["type"], "directory")
            self.assertGreater(len(tree["children"]), 0)

    def test_retention_affects_old_device_manifests(self):
        files_dir = os.path.join(self.repo_path, "files")
        old_manifest = os.path.join(files_dir, "_manifest_old_device.json")
        with open(old_manifest, "w") as f:
            json.dump({"old.txt": {"size": 10}}, f)
        old_time = (datetime.now() - timedelta(days=60)).timestamp()
        os.utime(old_manifest, (old_time, old_time))

        result = json.loads(self.handler.apply_retention_policy({"days": 30}))
        self.assertGreater(result["removed"], 0)
        self.assertFalse(os.path.exists(old_manifest))

        for device_name in ["device_laptop", "device_phone", "device_desktop"]:
            manifest = os.path.join(files_dir, f"_manifest_{device_name}.json")
            self.assertTrue(os.path.exists(manifest))


if __name__ == "__main__":
    unittest.main()
