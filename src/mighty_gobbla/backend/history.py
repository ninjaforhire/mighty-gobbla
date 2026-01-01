import json
import os
from datetime import datetime

# Save history in the user's home directory to ensure persistence across sessions/locations
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".mighty_gobbla_history.json")

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def add_history_entry(filename, details, directory=None):
    history = load_history()
    
    # Generate ID based on max existing ID + 1 to avoid collisions after deletion
    max_id = 0
    if history:
        max_id = max(item.get("id", 0) for item in history)
    
    entry = {
        "id": max_id + 1,
        "timestamp": datetime.now().isoformat(),
        "filename": filename,
        "directory": directory or "Upload",
        "details": details
    }
    
    # Add to beginning
    history.insert(0, entry)
    
    # Keep last 200
    if len(history) > 200:
        history = history[:200]
        
    save_history(history)

def get_history(page=1, limit=10):
    history = load_history()
    start = (page - 1) * limit
    end = start + limit
    
    return {
        "total": len(history),
        "page": page,
        "limit": limit,
        "items": history[start:end]
    }

def delete_entry(entry_id):
    history = load_history()
    # Filter out entry with matching ID
    new_history = [h for h in history if h.get("id") != entry_id]
    save_history(new_history)

def clear_history():
    save_history([])
