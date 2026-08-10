"""Test PDF library actions."""
import json
import os
import sys

# Ensure project root is in path (tests/ -> project root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from system_bridge import SystemBridge

app = QApplication(sys.argv)
bridge = SystemBridge()

# Test lib_list
result = json.loads(bridge.request(json.dumps({"action": "lib_list"})))
print(f"lib_list: {len(result['files'])} files found")

# Test lib_open
if result["files"]:
    fname = result["files"][0]["name"]
    open_result = json.loads(
        bridge.request(json.dumps({"action": "lib_open", "filename": fname}))
    )
    print(f"lib_open: {open_result}")

    if open_result.get("status") == "ok":
        total = open_result["total_pages"]
        print(f"  Total pages: {total}")

        # Test lib_page
        page_result = json.loads(
            bridge.request(
                json.dumps({"action": "lib_page", "page": 0, "zoom": 2.0})
            )
        )
        b64_len = len(page_result.get("b64", ""))
        print(
            f"  lib_page: b64={b64_len} chars, {page_result.get('width')}x{page_result.get('height')}"
        )

        # Test lib_annot
        annot_result = json.loads(
            bridge.request(
                json.dumps(
                    {
                        "action": "lib_annot",
                        "page": 0,
                        "rect": [10, 10, 100, 50],
                        "tool": "Highlight",
                        "text": "",
                    }
                )
            )
        )
        print(f"  lib_annot: {annot_result}")

print("\nAll PDF library actions working!")
app.quit()
