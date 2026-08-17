"""Filesharing handler unit tests.

Tests FileSharingHandler with MockBridge, covering folder hierarchy,
changelog, goal binding, and retention policy actions.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.filesharing import FileSharingHandler


class MockSyncManager:
    """Mock SyncManager for handler tests."""

    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.db_sync_dir = "db_exports"
        self.files_dir = "files"
        self.device_id = "test-device-001"


class MockBridge:
    """Mock SystemBridge for handler tests."""

    def __init__(self, repo_path):
        self.sync_manager = MockSyncManager(repo_path)


class TestFolderHierarchy(unittest.TestCase):
    """Test get_folder_hierarchy action."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmp_dir, "repo")
        os.makedirs(self.repo_path)
        self.bridge = MockBridge(self.repo_path)
        self.handler = FileSharingHandler(self.bridge)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_hierarchy_empty_folder(self):
        folder = os.path.join(self.tmp_dir, "empty")
        os.makedirs(folder)
        result = json.loads(self.handler.get_folder_hierarchy({"path": folder}))
        self.assertIn("tree", result)
        self.assertEqual(result["tree"]["name"], "empty")
        self.assertEqual(result["tree"]["type"], "directory")
        self.assertEqual(result["tree"]["children"], [])

    def test_hierarchy_with_files(self):
        folder = os.path.join(self.tmp_dir, "docs")
        os.makedirs(folder)
        for name in ["file1.txt", "file2.md", "image.png"]:
            with open(os.path.join(folder, name), "w") as f:
                f.write("content")
        result = json.loads(self.handler.get_folder_hierarchy({"path": folder}))
        tree = result["tree"]
        self.assertEqual(len(tree["children"]), 3)
        names = [c["name"] for c in tree["children"]]
        self.assertIn("file1.txt", names)
        self.assertIn("file2.md", names)
        self.assertIn("image.png", names)

    def test_hierarchy_nested_directories(self):
        folder = os.path.join(self.tmp_dir, "nested")
        sub = os.path.join(folder, "subdir")
        os.makedirs(sub)
        with open(os.path.join(sub, "deep.txt"), "w") as f:
            f.write("deep")
        result = json.loads(self.handler.get_folder_hierarchy({"path": folder}))
        tree = result["tree"]
        self.assertEqual(len(tree["children"]), 1)
        self.assertEqual(tree["children"][0]["name"], "subdir")
        self.assertEqual(tree["children"][0]["type"], "directory")
        self.assertEqual(len(tree["children"][0]["children"]), 1)
        self.assertEqual(tree["children"][0]["children"][0]["name"], "deep.txt")

    def test_hierarchy_nonexistent_path(self):
        result = json.loads(self.handler.get_folder_hierarchy({"path": "/nonexistent/path"}))
        self.assertIn("error", result)
        self.assertIsNone(result["tree"])

    def test_hierarchy_empty_path(self):
        result = json.loads(self.handler.get_folder_hierarchy({"path": ""}))
        self.assertIn("error", result)

    def test_hierarchy_file_size(self):
        folder = os.path.join(self.tmp_dir, "sized")
        os.makedirs(folder)
        filepath = os.path.join(folder, "data.txt")
        with open(filepath, "w") as f:
            f.write("x" * 1000)
        result = json.loads(self.handler.get_folder_hierarchy({"path": folder}))
        file_node = result["tree"]["children"][0]
        self.assertEqual(file_node["size"], 1000)
        self.assertEqual(file_node["type"], "file")

    def test_hierarchy_hides_dotfiles(self):
        folder = os.path.join(self.tmp_dir, "dotfiles")
        os.makedirs(folder)
        with open(os.path.join(folder, ".hidden"), "w") as f:
            f.write("")
        with open(os.path.join(folder, "visible.txt"), "w") as f:
            f.write("")
        result = json.loads(self.handler.get_folder_hierarchy({"path": folder}))
        names = [c["name"] for c in result["tree"]["children"]]
        self.assertNotIn(".hidden", names)
        self.assertIn("visible.txt", names)

    def test_hierarchy_hides_pycache(self):
        folder = os.path.join(self.tmp_dir, "pycache")
        os.makedirs(os.path.join(folder, "__pycache__"))
        with open(os.path.join(folder, "__pycache__", "mod.pyc"), "w") as f:
            f.write("")
        with open(os.path.join(folder, "main.py"), "w") as f:
            f.write("")
        result = json.loads(self.handler.get_folder_hierarchy({"path": folder}))
        names = [c["name"] for c in result["tree"]["children"]]
        self.assertNotIn("__pycache__", names)
        self.assertIn("main.py", names)

    def test_hierarchy_path_preserved(self):
        folder = os.path.join(self.tmp_dir, "pathtest")
        os.makedirs(folder)
        with open(os.path.join(folder, "file.txt"), "w") as f:
            f.write("")
        result = json.loads(self.handler.get_folder_hierarchy({"path": folder}))
        self.assertEqual(result["tree"]["path"], folder)
        self.assertEqual(result["tree"]["children"][0]["path"], os.path.join(folder, "file.txt"))


class TestGoalBinding(unittest.TestCase):
    """Test bind_folder_goal and get_goal_folder_bindings actions."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmp_dir, "repo")
        os.makedirs(self.repo_path)
        self.bridge = MockBridge(self.repo_path)
        self.handler = FileSharingHandler(self.bridge)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch("handlers.filesharing.config")
    def test_bind_goal(self, mock_config):
        mock_config.get.return_value = {}
        result = json.loads(self.handler.bind_folder_goal({
            "folder": "/shared/docs",
            "goal_uuid": "goal-123",
        }))
        self.assertEqual(result["status"], "success")
        mock_config.set.assert_called_once_with("folder_goal_bindings", {"/shared/docs": "goal-123"})

    @patch("handlers.filesharing.config")
    def test_unbind_goal(self, mock_config):
        mock_config.get.return_value = {"/shared/docs": "goal-123"}
        result = json.loads(self.handler.bind_folder_goal({
            "folder": "/shared/docs",
            "goal_uuid": "",
        }))
        self.assertEqual(result["status"], "success")
        mock_config.set.assert_called_once_with("folder_goal_bindings", {})

    @patch("handlers.filesharing.config")
    def test_get_bindings(self, mock_config):
        mock_config.get.return_value = {"/a": "uuid-1", "/b": "uuid-2"}
        result = json.loads(self.handler.get_goal_folder_bindings({}))
        self.assertEqual(result["bindings"], {"/a": "uuid-1", "/b": "uuid-2"})

    @patch("handlers.filesharing.config")
    def test_get_bindings_empty(self, mock_config):
        mock_config.get.return_value = {}
        result = json.loads(self.handler.get_goal_folder_bindings({}))
        self.assertEqual(result["bindings"], {})

    @patch("handlers.filesharing.config")
    def test_rebind_goal(self, mock_config):
        mock_config.get.return_value = {"/shared/docs": "goal-123"}
        self.handler.bind_folder_goal({"folder": "/shared/docs", "goal_uuid": "goal-999"})
        mock_config.set.assert_called_with("folder_goal_bindings", {"/shared/docs": "goal-999"})


class TestChangelog(unittest.TestCase):
    """Test get_folder_changelog action."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmp_dir, "repo")
        os.makedirs(self.repo_path)
        self.bridge = MockBridge(self.repo_path)
        self.handler = FileSharingHandler(self.bridge)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_changelog_no_repo(self):
        handler = FileSharingHandler(MockBridge("/nonexistent/repo"))
        result = json.loads(handler.get_folder_changelog({"path": "/some/path"}))
        self.assertEqual(result["changelog"], [])

    def test_changelog_empty_repo(self):
        result = json.loads(self.handler.get_folder_changelog({"path": self.tmp_dir}))
        self.assertEqual(result["changelog"], [])

    def test_changelog_with_git_commits(self):
        import git as gitmodule
        repo = gitmodule.Repo.init(self.repo_path)
        with open(os.path.join(self.repo_path, "test.txt"), "w") as f:
            f.write("v1")
        repo.git.add(A=True)
        repo.index.commit("add test file")

        with open(os.path.join(self.repo_path, "test.txt"), "w") as f:
            f.write("v2")
        repo.git.add(A=True)
        repo.index.commit("modify test file")

        result = json.loads(self.handler.get_folder_changelog({"path": self.tmp_dir, "days": 30}))
        self.assertGreaterEqual(len(result["changelog"]), 1)

    def test_changelog_respects_max_changes(self):
        import git as gitmodule
        repo = gitmodule.Repo.init(self.repo_path)
        for i in range(10):
            with open(os.path.join(self.repo_path, f"file{i}.txt"), "w") as f:
                f.write(f"content {i}")
            repo.git.add(A=True)
            repo.index.commit(f"add file{i}")

        result = json.loads(self.handler.get_folder_changelog({
            "path": self.tmp_dir, "days": 30, "max_changes": 3,
        }))
        self.assertLessEqual(len(result["changelog"]), 3)


class TestRetentionPolicy(unittest.TestCase):
    """Test apply_retention_policy action."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmp_dir, "repo")
        os.makedirs(self.repo_path)
        self.bridge = MockBridge(self.repo_path)
        self.handler = FileSharingHandler(self.bridge)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_retention_no_repo(self):
        handler = FileSharingHandler(MockBridge("/nonexistent/repo"))
        result = json.loads(handler.apply_retention_policy({"days": 30}))
        self.assertEqual(result["removed"], 0)

    def test_retention_removes_old_exports(self):
        export_dir = os.path.join(self.repo_path, "db_exports")
        os.makedirs(export_dir)
        old_file = os.path.join(export_dir, "old_device.json")
        with open(old_file, "w") as f:
            json.dump({"old": True}, f)
        old_time = (datetime.now() - timedelta(days=60)).timestamp()
        os.utime(old_file, (old_time, old_time))

        result = json.loads(self.handler.apply_retention_policy({"days": 30}))
        self.assertGreater(result["removed"], 0)
        self.assertFalse(os.path.exists(old_file))

    def test_retention_keeps_recent_files(self):
        export_dir = os.path.join(self.repo_path, "db_exports")
        os.makedirs(export_dir)
        recent_file = os.path.join(export_dir, "recent_device.json")
        with open(recent_file, "w") as f:
            json.dump({"recent": True}, f)

        result = json.loads(self.handler.apply_retention_policy({"days": 30}))
        self.assertTrue(os.path.exists(recent_file))

    def test_retention_removes_old_manifests(self):
        files_dir = os.path.join(self.repo_path, "files")
        os.makedirs(files_dir)
        old_manifest = os.path.join(files_dir, "_manifest_old_device.json")
        with open(old_manifest, "w") as f:
            json.dump({}, f)
        old_time = (datetime.now() - timedelta(days=90)).timestamp()
        os.utime(old_manifest, (old_time, old_time))

        result = json.loads(self.handler.apply_retention_policy({"days": 30}))
        self.assertGreater(result["removed"], 0)

    def test_retention_preserves_non_manifest_files(self):
        files_dir = os.path.join(self.repo_path, "files")
        os.makedirs(files_dir)
        data_file = os.path.join(files_dir, "actual_data.txt")
        with open(data_file, "w") as f:
            f.write("important")

        result = json.loads(self.handler.apply_retention_policy({"days": 30}))
        self.assertTrue(os.path.exists(data_file))


class TestHandlerDispatch(unittest.TestCase):
    """Test that FileSharingHandler correctly dispatches actions."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmp_dir, "repo")
        os.makedirs(self.repo_path)
        self.bridge = MockBridge(self.repo_path)
        self.handler = FileSharingHandler(self.bridge)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_known_actions_registered(self):
        expected = {
            "get_folder_hierarchy",
            "get_folder_changelog",
            "bind_folder_goal",
            "get_goal_folder_bindings",
            "apply_retention_policy",
        }
        self.assertEqual(set(self.handler.actions.keys()), expected)

    def test_unknown_action_returns_none(self):
        result = self.handler.handle("nonexistent_action", {})
        self.assertIsNone(result)

    def test_known_action_returns_result(self):
        result = self.handler.handle("get_goal_folder_bindings", {})
        self.assertIsNotNone(result)
        data = json.loads(result)
        self.assertIn("bindings", data)

    def test_handle_dispatches_to_correct_method(self):
        result = self.handler.handle("get_folder_hierarchy", {"path": ""})
        data = json.loads(result)
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
