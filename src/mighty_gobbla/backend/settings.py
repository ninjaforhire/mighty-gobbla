import json
import os

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".mighty_gobbla_settings.json")

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {"notion_enabled": False}
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"notion_enabled": False}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def get_setting(key, default=None):
    settings = load_settings()
    return settings.get(key, default)

def set_setting(key, value):
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
