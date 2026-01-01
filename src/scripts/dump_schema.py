import requests
import json
import sys
import io
import os

# Force UTF8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "YOUR_TOKEN_HERE")
DATABASE_ID = os.getenv("NOTION_DB_ID", "YOUR_DB_ID_HERE")

url = f"https://api.notion.com/v1/databases/{DATABASE_ID}"
headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28"}

try:
    resp = requests.get(url, headers=headers)
    print(json.dumps(resp.json(), indent=2))
except Exception as e:
    print(e)
