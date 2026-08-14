import json
import sys
import traceback

from PyQt6.QtWidgets import QApplication

# Import the actual bridge from your app
from system_bridge import SystemBridge


def run_bridge_test():
    print("\n" + "="*50)
    print(" 🕵️‍♂️ SYSTEM BRIDGE ISOLATION TEST")
    print("="*50)

    # QApplication is strictly required before instantiating any PyQt QObjects/QWidgets
    app = QApplication(sys.argv)

    try:
        print("[*] 1. Instantiating SystemBridge...")
        bridge = SystemBridge()
        print("  ✅ SystemBridge instantiated successfully!")

        print("\n[*] 2. Simulating React 'init' request...")
        init_payload = json.dumps({"action": "init"})
        init_response = bridge.request(init_payload)

        # Parse and preview the response
        init_data = json.loads(init_response)
        print("  ✅ 'init' processed successfully!")
        print(f"     -> Found {len(init_data.get('courses', []))} courses.")

        print("\n[*] 3. Simulating React 'start_timer' request...")
        start_payload = json.dumps({
            "action": "start_timer",
            "duration": 25,
            "course": "Diagnostics",
            "type": "Work"
        })
        start_response = bridge.request(start_payload)
        print(f"  ✅ Timer started successfully: {start_response}")
        print(f"     -> Bridge is_running state: {bridge.is_running}")
        print(f"     -> Vision Tracker state: {bridge.vision.tmr.isActive()}")

        print("\n[*] 4. Simulating React 'stop_timer' request...")
        stop_payload = json.dumps({"action": "stop_timer"})
        stop_response = bridge.request(stop_payload)
        print(f"  ✅ Timer stopped successfully: {stop_response}")

        print("\n" + "="*50)
        print(" 🎉 ALL BRIDGE TESTS PASSED FLAWLESSLY!")
        print("="*50 + "\n")

        # We exit safely without launching the main event loop
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ BRIDGE TEST FAILED: {type(e).__name__} - {e!s}")
        print("-" * 40)
        traceback.print_exc()
        print("-" * 40)
        sys.exit(1)

if __name__ == "__main__":
    run_bridge_test()
