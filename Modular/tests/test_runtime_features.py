"""Regression tests for timer, food vision, wallpaper, and sync behavior."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import cv2
import numpy as np

from core_sys import DatabaseManager, config
from handlers import wallpaper as wallpaper_module
from handlers.food_detection import FoodDetectionHandler
from sync_manager import SyncManager
from system_bridge import SystemBridge


class TimerDouble:
    def __init__(self):
        self.is_running = True
        self.current_att = True
        self.distractions = 0
        self.distraction_markers = []
        self.total_time = 10
        self.time_left = 5
        self.was_distracted = False
        self.distraction_log = []
        self.distraction_start = 0
        self.distraction_type_current = "Manual"

    def push_state(self, mode):
        self.pushed = (mode, self.time_left)


def test_timer_tick_decrements_and_emits_state():
    timer = TimerDouble()
    original_monitoring = config.get("app_monitoring_enabled", False)
    config.cfg["app_monitoring_enabled"] = False
    try:
        SystemBridge.tick(timer)
    finally:
        config.cfg["app_monitoring_enabled"] = original_monitoring
    assert timer.time_left == 4
    assert timer.pushed == ("None", 4)


def test_food_detection_returns_annotated_image():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(image, (180, 140), (360, 300), (0, 200, 0), -1)
    success, encoded = cv2.imencode(".jpg", image)
    assert success
    payload = base64.b64encode(encoded).decode("ascii")
    result = json.loads(FoodDetectionHandler(None).detect_food({"image_base64": payload}))
    assert result["annotated_image"]
    assert result["detections"]
    assert result["detections"][0]["estimated_calories"] > 0


def test_wallpaper_blob_round_trip(tmp_path: Path, monkeypatch):
    local_db = DatabaseManager(str(tmp_path / "wallpaper.db"))

    class ConfigDouble:
        def __init__(self):
            self.values = {"bg_image_path": ""}

        def get(self, key, default=None):
            return self.values.get(key, default)

        def set(self, key, value):
            self.values[key] = value

    monkeypatch.setattr(wallpaper_module, "db", local_db)
    monkeypatch.setattr(wallpaper_module, "config", ConfigDouble())
    image_path = tmp_path / "wallpaper.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nwallpaper-test")
    handler = wallpaper_module.WallpaperHandler(None)
    result = json.loads(handler.save_wallpaper({"path": str(image_path)}))
    assert result["data_url"].startswith("data:image/png;base64,")


def test_sync_blob_encoding_round_trip():
    value = b"wallpaper-bytes"
    encoded = SyncManager._encode_json_value(value)
    assert SyncManager._decode_json_value(encoded) == value
