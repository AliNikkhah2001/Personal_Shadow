"""End-to-end init pipeline + time-based regression tests for the dashboard bridge.

Verifies the exact bug fixed in bridge/runtime.py: ``get_heatmap_data`` was
referenced by ``_handle_init`` but never defined, which made the whole init
payload return ``{"error": ...}`` and blanked goals/habits across the UI.

These tests run the REAL mixin code used by ``SystemBridge`` (the same code the
frontend calls through QWebChannel), against an isolated temp SQLite database,
with dates frozen so the time-based logic is deterministic.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime as _real_datetime, timedelta
from unittest.mock import patch

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from bridge.actions import DashboardActionsMixin
from bridge.runtime import RuntimeServicesMixin

import bridge.runtime as runtime_mod
import bridge.actions as actions_mod

NOW_STR = _real_datetime.now().isoformat()


class FrozenDateTime(_real_datetime):
    """datetime stub freezing now() at a fixed date for deterministic time tests."""

    frozen = None

    @classmethod
    def now(cls, tz=None):
        assert cls.frozen is not None, "FrozenDateTime.frozen not set"
        return cls.frozen.replace(tzinfo=tz)


class TestDonorDb(unittest.TestCase):
    """Shared temp DB + bridge stub used by the end-to-end tests."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="mp_init_e2e_")
        from core_sys import DatabaseManager

        self.db = DatabaseManager(os.path.join(self._tmp, "test.db"))

        class StubBridge(DashboardActionsMixin, RuntimeServicesMixin):
            sync_manager = None
            repo_path = self._tmp

        self.bridge = StubBridge()

        for mod_name in (runtime_mod, actions_mod):
            patcher = patch.object(mod_name, "db", self.db)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def seed_goal(self, title, target=100.0, parent_id=None):
        self.db.c.execute(
            "INSERT INTO cascading_goals (parent_id, title, target_hours, deadline, uuid, modified_at) "
            "VALUES (?, ?, ?, '2026-09-01 10:00', ?, ?)",
            (parent_id, title, target, f"uuid_{title}", NOW_STR),
        )
        self.db.safe_commit()

    def seed_habit(self, name, type_="Positive"):
        self.db.c.execute(
            "INSERT INTO habits (name, type, uuid, modified_at) VALUES (?, ?, ?, ?)",
            (name, type_, f"uuid_{name}", NOW_STR),
        )
        self.db.safe_commit()

    def seed_session(self, course, minutes, timestamp):
        self.db.c.execute(
            "INSERT INTO pomodoro_sessions (course, duration, actual_duration, timestamp, type, uuid, modified_at) "
            "VALUES (?, ?, ?, ?, 'Work', ?, ?)",
            (course, minutes, minutes, timestamp, f"uuid_{course}_{timestamp}", NOW_STR),
        )
        self.db.safe_commit()


class TestInitPayload(TestDonorDb):
    """End-to-end: the exact init payload the frontend receives."""

    def test_init_returns_no_error_key(self):
        """Regression for the AttributeError bug: init must not return {'error': ...}."""
        self.seed_goal("Apex")
        self.seed_goal("Sub Goal", parent_id=None)
        self.seed_habit("Habit One")
        self.seed_habit("Habit Two")
        self.db.c.execute(
            "INSERT INTO habit_logs (habit_id, date, status, uuid, modified_at) VALUES (1, 'Sun, 8/16', 1, ?, ?)",
            ("hl_1", NOW_STR),
        )
        self.db.safe_commit()
        resp = json.loads(self.bridge._handle_init({}))
        self.assertNotIn("error", resp, f"init returned error: {resp.get('error')}")

    def test_init_contains_goals_habits_and_heatmap(self):
        self.seed_goal("Apex")
        self.seed_goal("Sub Goal", parent_id=None)
        self.seed_habit("Habit One")
        self.seed_habit("Habit Two")
        resp = json.loads(self.bridge._handle_init({}))
        titles = [g["title"] for g in resp.get("goals", [])]
        self.assertIn("Apex", titles)
        self.assertIn("Sub Goal", titles)
        names = [h["name"] for h in resp.get("habits", [])]
        self.assertIn("Habit One", names)
        self.assertIn("Habit Two", names)
        self.assertIn("heatmap", resp)
        self.assertEqual(len(resp["heatmap"]), 28)
        self.assertTrue(all(len(row) == 7 for row in resp["heatmap"]))
        self.assertIn("flat_goals", resp)
        self.assertIn("studied_hours", resp)

    def test_heatmap_is_28x7_matrix(self):
        matrix = self.bridge.get_heatmap_data()
        self.assertEqual(len(matrix), 28)
        self.assertTrue(all(len(row) == 7 for row in matrix))


class TestPerGoalStudiedHours(TestDonorDb):
    """Time-based: per-goal studied hours aggregate descendants and honour date filters."""

    def setUp(self):
        super().setUp()
        self.seed_goal("Apex")
        self.seed_goal("Sub Goal", parent_id=1)
        self.seed_session("Apex", 60, "2026-08-15 10:00:00")
        self.seed_session("Sub Goal", 120, "2026-08-16 10:00:00")
        self.seed_session("Unrelated Course", 30, "2026-08-15 10:00:00")

    def test_aggregates_descendant_goal_hours(self):
        """Hours from a child goal must roll up into the parent goal total."""
        result = self.bridge.get_studied_hours_per_goal(date_filter="2026-08-15")
        self.assertEqual(result["Apex"], 1.0)
        self.assertEqual(result["Sub Goal"], 0.0)
        self.assertEqual(result["Unrelated Course"], 0.5)

    def test_date_filter_limits_by_day(self):
        all_days = self.bridge.get_studied_hours_per_goal()
        today_only = self.bridge.get_studied_hours_per_goal(date_filter="2026-08-16")
        self.assertEqual(all_days["Sub Goal"], 2.0)
        self.assertEqual(today_only["Sub Goal"], 2.0)
        self.assertEqual(today_only["Apex"], 2.0)
        self.assertNotIn("Unrelated Course", today_only)


class TestHeatmapTimeBuckets(TestDonorDb):
    """Time-based: heatmap cell intensity scales with hours logged on a day."""

    FROZEN_DATE = _real_datetime(2026, 8, 16, 12, 0, 0)

    def setUp(self):
        super().setUp()
        FrozenDateTime.frozen = self.FROZEN_DATE
        patcher = patch.object(runtime_mod, "datetime", FrozenDateTime)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _cell_for_days_back(self, days_back):
        """Return (week_index, day_index) for a session N days before frozen today."""
        matrix = self.bridge.get_heatmap_data()
        # matrix[week][day]; for the final week (week=27), day = 6 -> today.
        week = 27 - (days_back // 7)
        day = 6 - (days_back % 7)
        return matrix[week][day]

    def seed_sessions(self, hours, days_back):
        minutes = int(hours * 60)
        target_date = (self.FROZEN_DATE.date() - timedelta(days=days_back)).isoformat()
        self.seed_session("Course", minutes, f"{target_date} 10:00:00")

    def test_no_sessions_is_all_zeros(self):
        matrix = self.bridge.get_heatmap_data()
        self.assertEqual(sum(map(sum, matrix)), 0)

    def test_small_volume_sets_first_intensity(self):
        self.seed_sessions(1, days_back=0)
        self.assertGreaterEqual(self._cell_for_days_back(0), 1)

    def test_large_volume_sets_high_intensity(self):
        self.seed_sessions(7, days_back=1)
        self.assertEqual(self._cell_for_days_back(1), 4)

    def test_week_ago_lands_in_previous_week_column(self):
        self.seed_sessions(3, days_back=6)
        self.assertGreaterEqual(self._cell_for_days_back(6), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)