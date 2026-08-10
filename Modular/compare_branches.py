"""Compare old bugfix_sync branch with current main to find missing features."""
import subprocess
import re

# Get old system_bridge.py from bugfix_sync
result = subprocess.run(
    ["git", "show", "bugfix_sync:Modular/system_bridge.py"],
    capture_output=True, text=True, encoding="utf-8", errors="replace"
)
old_content = result.stdout

# Get current system_bridge.py
with open("system_bridge.py", "r") as f:
    new_content = f.read()

# Find actions in old version
old_actions = set(re.findall(r'action == "(\w+)"', old_content))
new_actions = set(re.findall(r'"(\w+)": self._handle_', new_content))

print(f"Actions in OLD system_bridge.py: {len(old_actions)}")
print(f"Actions in NEW system_bridge.py: {len(new_actions)}")
print()
print("Actions in OLD but not in NEW:")
for a in sorted(old_actions - new_actions):
    print(f"  - {a}")
print()
print("Actions in NEW but not in OLD:")
for a in sorted(new_actions - old_actions):
    print(f"  - {a}")

# Also check sync_manager.py
print("\n" + "=" * 60)
print("Checking sync_manager.py differences...")

result2 = subprocess.run(
    ["git", "show", "bugfix_sync:Modular/sync_manager.py"],
    capture_output=True, text=True, encoding="utf-8", errors="replace"
)
old_sync = result2.stdout

with open("sync_manager.py", "r") as f:
    new_sync = f.read()

# Find methods in old sync_manager
old_methods = set(re.findall(r'def (\w+)\(', old_sync))
new_methods = set(re.findall(r'def (\w+)\(', new_sync))

print(f"\nMethods in OLD sync_manager.py: {len(old_methods)}")
print(f"Methods in NEW sync_manager.py: {len(new_methods)}")
print()
print("Methods in OLD but not in NEW:")
for m in sorted(old_methods - new_methods):
    print(f"  - {m}")
print()
print("Methods in NEW but not in OLD:")
for m in sorted(new_methods - old_methods):
    print(f"  - {m}")

# Check for key sync-related functionality
print("\n" + "=" * 60)
print("Key sync functionality check:")
key_features = ["soft_delete", "master", "cluster", "merge", "conflict", "lww", "last_write"]
for feat in key_features:
    old_has = feat.lower() in old_sync.lower()
    new_has = feat.lower() in new_sync.lower()
    status = "OK" if (old_has and new_has) else "MISSING" if (old_has and not new_has) else "NEW"
    print(f"  {feat}: {status}")
