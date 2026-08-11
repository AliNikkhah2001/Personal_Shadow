"""Quick startup test for Mind Palace OS."""

import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from core_sys import db
from system_bridge import SystemBridge

app = QApplication(sys.argv)
bridge = SystemBridge()

print("Mind Palace OS - Backend initialized successfully")
print(f"Device ID: {bridge.sync_manager.device_id}")

tables = db.c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"Database tables: {len(tables)}")
for t in tables:
    print(f"  - {t[0]}")

print("\nAll systems operational!")
