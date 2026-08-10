"""System Bridge Isolation Test Suite.

Tests the SystemBridge backend without requiring the full UI.
Verifies imports, database, and basic functionality.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

# Ensure the project root is in the path (tests/ -> project root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestImports(unittest.TestCase):
    """Test that all modules can be imported without errors."""

    def test_core_sys_import(self):
        from core_sys import config, db, get_color
        self.assertIsNotNone(config)
        self.assertIsNotNone(db)

    def test_handlers_import(self):
        from handlers import ActionHandler
        from handlers.nutrition import NutritionHandler
        from handlers.health import HealthHandler
        from handlers.habit import HabitHandler
        from handlers.flashcard import FlashcardHandler
        from handlers.goal import GoalHandler
        from handlers.note import NoteHandler
        from handlers.queue import QueueHandler
        from handlers.sync import SyncHandler
        self.assertTrue(hasattr(ActionHandler, "handle"))

    def test_ui_import(self):
        from ui import OverlayWidget, AdvancedPDFWindow, TimelapseDialog
        self.assertIsNotNone(OverlayWidget)
        self.assertIsNotNone(AdvancedPDFWindow)
        self.assertIsNotNone(TimelapseDialog)

    def test_vision_tracker_import(self):
        from vision_tracker import VisionTracker
        self.assertIsNotNone(VisionTracker)

    def test_sync_manager_import(self):
        from sync_manager import SyncManager
        self.assertIsNotNone(SyncManager)

    def test_horology_import(self):
        from horology import draw_clock_face, draw_clock_ticks_and_indices
        self.assertIsNotNone(draw_clock_face)
        self.assertIsNotNone(draw_clock_ticks_and_indices)


class TestDatabase(unittest.TestCase):
    """Test database operations."""

    def setUp(self):
        from core_sys import db
        self.db = db

    def test_db_connection(self):
        self.assertIsNotNone(self.db.conn)
        self.assertIsNotNone(self.db.c)

    def test_db_query(self):
        self.db.c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in self.db.c.fetchall()]
        self.assertIn("courses", tables)
        self.assertIn("pomodoro_sessions", tables)

    def test_db_write_and_read(self):
        import uuid
        from datetime import datetime

        test_uuid = uuid.uuid4().hex
        self.db.c.execute(
            "INSERT INTO courses (name, uuid, modified_at) VALUES (?, ?, ?)",
            (f"TestCourse_{test_uuid[:8]}", test_uuid, datetime.now().isoformat()),
        )
        self.db.safe_commit()

        self.db.c.execute("SELECT name FROM courses WHERE uuid = ?", (test_uuid,))
        result = self.db.c.fetchone()
        self.assertIsNotNone(result)
        self.assertIn("TestCourse_", result[0])

        # Cleanup
        self.db.c.execute("DELETE FROM courses WHERE uuid = ?", (test_uuid,))
        self.db.safe_commit()


class TestConfig(unittest.TestCase):
    """Test configuration management."""

    def setUp(self):
        from core_sys import config
        self.config = config

    def test_get_existing_key(self):
        font = self.config.get("font_family")
        self.assertIsNotNone(font)

    def test_get_with_default(self):
        value = self.config.get("nonexistent_key", "default_value")
        self.assertEqual(value, "default_value")

    def test_set_and_get(self):
        import uuid
        test_key = f"test_key_{uuid.uuid4().hex[:8]}"
        self.config.set(test_key, "test_value")
        value = self.config.get(test_key)
        self.assertEqual(value, "test_value")
        # Cleanup
        self.config.cfg.pop(test_key, None)
        self.config.set("dummy", "dummy")  # Trigger save

    def test_timeline_config_defaults(self):
        """Test that timeline configuration defaults are set."""
        start_hour = self.config.get("timeline_start_hour")
        end_hour = self.config.get("timeline_end_hour")
        pixel_per_hour = self.config.get("timeline_pixel_per_hour")
        
        self.assertEqual(start_hour, 0)
        self.assertEqual(end_hour, 24)
        self.assertEqual(pixel_per_hour, 120)

    def test_timeline_config_set_and_get(self):
        """Test setting and getting timeline configuration."""
        self.config.set("timeline_start_hour", 6)
        self.config.set("timeline_end_hour", 22)
        self.config.set("timeline_pixel_per_hour", 150)
        
        self.assertEqual(self.config.get("timeline_start_hour"), 6)
        self.assertEqual(self.config.get("timeline_end_hour"), 22)
        self.assertEqual(self.config.get("timeline_pixel_per_hour"), 150)
        
        # Cleanup - reset to defaults
        self.config.set("timeline_start_hour", 0)
        self.config.set("timeline_end_hour", 24)
        self.config.set("timeline_pixel_per_hour", 120)


class TestSystemBridgeDispatch(unittest.TestCase):
    """Test the SystemBridge request dispatcher."""

    def test_handler_dispatch_pattern(self):
        """Test that the handler dispatch pattern works correctly."""
        from handlers.flashcard import FlashcardHandler

        # Create a mock bridge
        class MockBridge:
            pass

        handler = FlashcardHandler(MockBridge())
        self.assertIn("manage_flashcard", handler.actions)
        self.assertIn("manage_quiz", handler.actions)


if __name__ == "__main__":
    # Use a simpler test runner that doesn't require PyQt
    print("=" * 50)
    print("Mind Palace OS - Test Suite")
    print("=" * 50)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestImports))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemBridgeDispatch))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
