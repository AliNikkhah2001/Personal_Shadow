"""Filesharing frontend tests.

Tests JSX compilation of filesharing.js and component structure validation.
"""

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
FILESHARING_JS = os.path.join(FRONTEND_DIR, "scripts", "components", "filesharing.js")


class TestJSXCompilation(unittest.TestCase):
    """Test that filesharing.js compiles without syntax errors."""

    def test_filesharings_jsx_compiles(self):
        if not os.path.exists(FILESHARING_JS):
            self.skipTest("filesharing.js not found")

        babel_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "shadow_os_cache", "js", "babel.js",
        )
        if not os.path.exists(babel_path):
            self.skipTest("babel.js not found")

        babel_script = """
        var fs = require('fs');
        var babel = require('""" + babel_path.replace(os.sep, '/') + """');
        var code = fs.readFileSync('""" + FILESHARING_JS.replace(os.sep, '/').replace("'", "\\'") + """', 'utf8');
        try {
            var result = babel.transform(code, { presets: ['react'] });
            console.log('COMPILE_OK');
        } catch(e) {
            console.error('COMPILE_ERROR:', e.message);
            process.exit(1);
        }
        """
        result = subprocess.run(
            ["node", "-e", babel_script],
            capture_output=True, text=True, timeout=30,
            cwd=FRONTEND_DIR,
        )
        self.assertEqual(result.returncode, 0, f"Babel compilation failed: {result.stderr}")

    def test_filesharings_has_required_exports(self):
        if not os.path.exists(FILESHARING_JS):
            self.skipTest("filesharing.js not found")

        with open(FILESHARING_JS, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("FileSharingView", content)
        self.assertIn("React.memo", content)

    def test_filesharings_imports_backend(self):
        if not os.path.exists(FILESHARING_JS):
            self.skipTest("filesharing.js not found")

        with open(FILESHARING_JS, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("backend", content.lower())
        self.assertIn("request", content)

    def test_filesharings_has_action_calls(self):
        if not os.path.exists(FILESHARING_JS):
            self.skipTest("filesharing.js not found")

        with open(FILESHARING_JS, "r", encoding="utf-8") as f:
            content = f.read()

        expected_actions = [
            "get_mapped_folders",
            "map_folder",
            "unmap_folder",
            "get_folder_hierarchy",
            "get_folder_changelog",
            "bind_folder_goal",
            "get_goal_folder_bindings",
            "apply_retention_policy",
            "open_network_folder",
        ]
        for action in expected_actions:
            self.assertIn(action, content, f"Missing action: {action}")

    def test_filesharings_renders_device_colors(self):
        if not os.path.exists(FILESHARING_JS):
            self.skipTest("filesharing.js not found")

        with open(FILESHARING_JS, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("DEVICE_COLORS", content)
        self.assertIn("getDeviceColor", content)

    def test_filesharings_has_retention_ui(self):
        if not os.path.exists(FILESHARING_JS):
            self.skipTest("filesharing.js not found")

        with open(FILESHARING_JS, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("retentionDays", content)
        self.assertIn("retentionChanges", content)
        self.assertIn("Apply Retention", content)

    def test_filesharings_has_goal_binding(self):
        if not os.path.exists(FILESHARING_JS):
            self.skipTest("filesharing.js not found")

        with open(FILESHARING_JS, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("flatGoals", content)
        self.assertIn("Assign to Goal", content)

    def test_filesharings_has_tree_render(self):
        if not os.path.exists(FILESHARING_JS):
            self.skipTest("filesharing.js not found")

        with open(FILESHARING_JS, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("renderTreeNode", content)
        self.assertIn("folderTree", content)


class TestAppIntegration(unittest.TestCase):
    """Test that app.js includes filesharing routing."""

    def setUp(self):
        self.app_js = os.path.join(FRONTEND_DIR, "scripts", "app.js")

    def test_app_has_filesharing_nav(self):
        if not os.path.exists(self.app_js):
            self.skipTest("app.js not found")

        with open(self.app_js, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("filesharing", content)
        self.assertIn("File Sharing", content)

    def test_app_has_filesharing_route(self):
        if not os.path.exists(self.app_js):
            self.skipTest("app.js not found")

        with open(self.app_js, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("FileSharingView", content)
        self.assertIn("case 'filesharing'", content)

    def test_index_html_loads_filesharing(self):
        index_html = os.path.join(FRONTEND_DIR, "index.html")
        if not os.path.exists(index_html):
            self.skipTest("index.html not found")

        with open(index_html, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("filesharing.js", content)


class TestSettingsSyncCleanup(unittest.TestCase):
    """Test that K-Cluster and Master sections were removed from settings-sync.js."""

    def setUp(self):
        self.settings_sync = os.path.join(FRONTEND_DIR, "scripts", "components", "settings-sync.js")

    def test_k_cluster_removed(self):
        if not os.path.exists(self.settings_sync):
            self.skipTest("settings-sync.js not found")

        with open(self.settings_sync, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("K-Cluster", content)
        self.assertNotIn("Discovered Database Peer Nodes", content)

    def test_master_promote_removed(self):
        if not os.path.exists(self.settings_sync):
            self.skipTest("settings-sync.js not found")

        with open(self.settings_sync, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("Promote This PC to Master", content)
        self.assertNotIn("Cluster Master Authority", content)

    def test_cluster_topology_removed(self):
        if not os.path.exists(self.settings_sync):
            self.skipTest("settings-sync.js not found")

        with open(self.settings_sync, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("Cluster Topology & Sync", content)


class TestSystemBridgeRegistration(unittest.TestCase):
    """Test that FileSharingHandler is registered in system_bridge.py."""

    def setUp(self):
        self.bridge_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "system_bridge.py",
        )

    def test_import_exists(self):
        if not os.path.exists(self.bridge_file):
            self.skipTest("system_bridge.py not found")

        with open(self.bridge_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("from handlers.filesharing import FileSharingHandler", content)

    def test_handler_registered(self):
        if not os.path.exists(self.bridge_file):
            self.skipTest("system_bridge.py not found")

        with open(self.bridge_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("FileSharingHandler(self)", content)


if __name__ == "__main__":
    unittest.main()
