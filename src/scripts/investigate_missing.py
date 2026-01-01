import json
import os

history_path = os.path.expanduser("~/.mighty_gobbla_history.json")
print(f"Reading history from: {history_path}")

try:
    with open(history_path, 'r') as f:
        history = json.load(f)
        print(f"Found {len(history)} entries.")
        for item in history[:10]: # First 10 (most recent)
            print(f"  {item['filename']} | {item.get('directory')} | New: {item.get('details', {}).get('new_name')}") # new_name isn't stored in details, check structure
            # main.py stored: add_history_entry(new_name, processed_info, directory=root)
            # So 'filename' IS the new name.
            # We don't verify the OLD name in history unless we check 'results' return, which isn't saved to history file.
            # Wait, main.py: results.append({"original": filename, "new": new_name...})
            # But history only stores 'new_name'.
            pass
except Exception as e:
    print(f"Error reading history: {e}")

# Check G Drive paths
paths = [
    r"G:\My Drive\[99] MIGHTY Private\FINANCE\2025\SEMRush",
    r"G:\My Drive\[99] MIGHTY Private\FINANCE\2024\SEMRush"
]

for p in paths:
    print(f"\nChecking path: {p}")
    if os.path.exists(p):
        try:
            files = os.listdir(p)
            print(f"  Found {len(files)} files:")
            for f in files:
                print(f"    {f}")
        except Exception as e:
            print(f"  Error listing: {e}")
    else:
        print("  Path does not exist.")
