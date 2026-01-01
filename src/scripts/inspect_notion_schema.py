import requests
import json
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Credentials
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "YOUR_TOKEN_HERE")
DATABASE_ID = os.getenv("NOTION_DB_ID", "YOUR_DB_ID_HERE")

def inspect_schema():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        with open("src/scripts/schema_dump.txt", "w", encoding="utf-8") as f:
            try:
                title_len = len(data.get('title', []))
                f.write(f"Database Title (len): {title_len}\n")
            except:
                pass
            f.write("\nPROPERTIES FOUND:\n")
            props = data.get('properties', {})
            for name, details in props.items():
                f.write(f"- {name} ({details['type']})\n")
    else:
        with open("src/scripts/schema_dump.txt", "w", encoding="utf-8") as f:
            f.write(f"Error {resp.status_code}: {resp.text}")
        print(f"Error {resp.status_code}: {resp.text}")

if __name__ == "__main__":
    inspect_schema()
