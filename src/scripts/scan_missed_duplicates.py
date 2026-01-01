import os
import sys
import json
import logging
import requests
import re
from time import sleep
from dotenv import load_dotenv

# Configure logging
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_CLIENTS_DATABASE_ID")
NOTION_VERSION = "2022-06-28"

def get_headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

def fetch_all_pages():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    pages = []
    has_more = True
    next_cursor = None
    
    while has_more:
        payload = {"page_size": 100}
        if next_cursor:
            payload["start_cursor"] = next_cursor
            
        logger.info(f"Fetching pages (cursor: {next_cursor})...")
        res = requests.post(url, headers=get_headers(), json=payload)
        res.raise_for_status()
        data = res.json()
        
        results = data.get("results", [])
        pages.extend(results)
        has_more = data.get("has_more")
        next_cursor = data.get("next_cursor")
        
    return pages

def normalize_phone(p):
    if not p: return ""
    return re.sub(r'\D', '', p)

def get_prop_text(page, prop_name):
    props = page.get("properties", {})
    prop = props.get(prop_name, {})
    p_type = prop.get("type")
    
    if p_type == "rich_text" or p_type == "title":
        parts = prop.get(p_type, [])
        return "".join([p.get("plain_text", "") for p in parts]).strip().lower()
    elif p_type == "phone_number":
        return prop.get("phone_number", "")
    elif p_type == "email":
        return (prop.get("email") or "").lower()
    return ""

def main():
    pages = fetch_all_pages()
    total = len(pages)
    logger.info(f"Total pages retrieved for scan: {total}")

    groups = {} # Key -> List of Page IDs
    
    for p in pages:
        page_id = p["id"]
        # Extract keys
        raw_phone = get_prop_text(p, "Phone")
        norm_phone = normalize_phone(raw_phone)
        email = get_prop_text(p, "Email")
        first = get_prop_text(p, "First Name")
        last = get_prop_text(p, "Last Name")
        full_name = f"{first}|{last}" if (first and last) else ""
        
        # We check keys in priority
        potential_keys = []
        if norm_phone and len(norm_phone) >= 10: potential_keys.append(f"PH:{norm_phone}")
        if email: potential_keys.append(f"EM:{email}")
        if full_name: potential_keys.append(f"NM:{full_name}")
        
        # Assign to first valid key to avoid double counting across types 
        # (but this script prioritizes phone -> email -> name)
        assigned = False
        for key in potential_keys:
            if key not in groups:
                 groups[key] = []
            groups[key].append(p)
            assigned = True
            break # Once assigned to a group, don't put in another (for now)

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
    
    print("\n" + "="*50)
    print(f"EXPANDED SCAN RESULTS ({total} pages scanned)")
    print(f"Duplicates Groups Found: {len(duplicate_groups)}")
    print("="*50)
    
    total_redundant = 0
    for k, v in duplicate_groups.items():
        total_redundant += (len(v) - 1)
        # Sample log
        title = get_prop_text(v[0], "TITLE")
        # Find master (one with content/title preferred)
        print(f"GROUP {k} ({title}): {len(v)} records")
        
    print(f"\nTotal Redundant Records Found: {total_redundant}")

if __name__ == "__main__":
    main()
