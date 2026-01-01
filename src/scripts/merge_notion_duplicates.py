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
        
        pages.extend(data.get("results", []))
        has_more = data.get("has_more")
        next_cursor = data.get("next_cursor")
        
    return pages

def get_page_blocks(page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    blocks = []
    has_more = True
    next_cursor = None
    
    while has_more:
        params = {"page_size": 100}
        if next_cursor:
            params["start_cursor"] = next_cursor
            
        res = requests.get(url, headers=get_headers(), params=params)
        res.raise_for_status()
        data = res.json()
        
        blocks.extend(data.get("results", []))
        has_more = data.get("has_more")
        next_cursor = data.get("next_cursor")
        
    # Clean blocks for appending (remove id, parent, etc.)
    cleaned = []
    for b in blocks:
        block_type = b.get("type")
        if not block_type: continue
        
        # Only keep the relevant part of the block
        content = b.get(block_type)
        cleaned.append({
            "object": "block",
            "type": block_type,
            block_type: content
        })
    return cleaned

def count_filled_props(page):
    props = page.get("properties", {})
    count = 0
    for name, data in props.items():
        # Check if property is non-empty based on type
        p_type = data.get("type")
        val = data.get(p_type)
        if p_type == "title" or p_type == "rich_text":
            if val: count += 1
        elif p_type == "email" or p_type == "phone_number":
            if val: count += 1
        elif p_type == "multi_select" or p_type == "relation":
            if val: count += 1
    return count

def merge_records(master_page, duplicates, modes=["properties", "content", "archive"]):
    master_id = master_page["id"]
    master_props = master_page["properties"]
    
    updates = {}
    blocks_to_append = []
    
    for dup in duplicates:
        dup_props = dup["properties"]
        
        # Properties Merge
        for name, data in dup_props.items():
            p_type = data.get("type")
            # If master is empty, take from duplicate
            if not master_props.get(name, {}).get(p_type):
                updates[name] = data
            
            # Special case for Multi-select (Tags)
            if p_type == "multi_select":
                master_tags = [t["name"] for t in master_props.get(name, {}).get("multi_select", [])]
                dup_tags = [t["name"] for t in data.get("multi_select", [])]
                merged_tags = list(set(master_tags) | set(dup_tags))
                if len(merged_tags) > len(master_tags):
                    updates[name] = {"multi_select": [{"name": t} for t in merged_tags]}

        # Content Fetch
        if "content" in modes:
            logger.info(f"Fetching blocks from duplicate {dup['id']}...")
            blocks = get_page_blocks(dup["id"])
            if blocks:
                blocks_to_append.append({
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                })
                blocks_to_append.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": f"Merged from duplicate record ({dup['id']}):"}}, {"text": {"content": "\n", "link": None}}]}
                })
                blocks_to_append.extend(blocks)

    # 1. Update Master Properties
    if updates and "properties" in modes:
        logger.info(f"Updating master record {master_id} properties...")
        res = requests.patch(f"https://api.notion.com/v1/pages/{master_id}", headers=get_headers(), json={"properties": updates})
        res.raise_for_status()

    # 2. Append Content to Master
    if blocks_to_append and "content" in modes:
        logger.info(f"Appending {len(blocks_to_append)} blocks to master...")
        # Notion allows max 100 blocks per request
        for i in range(0, len(blocks_to_append), 100):
            chunk = blocks_to_append[i:i+100]
            res = requests.patch(f"https://api.notion.com/v1/blocks/{master_id}/children", headers=get_headers(), json={"children": chunk})
            res.raise_for_status()

    # 3. Archive Duplicates
    if "archive" in modes:
        for dup in duplicates:
            logger.info(f"Archiving duplicate {dup['id']}...")
            res = requests.patch(f"https://api.notion.com/v1/pages/{dup['id']}", headers=get_headers(), json={"archived": True})
            res.raise_for_status()

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
        return prop.get("phone_number", "") or ""
    elif p_type == "email":
        return (prop.get("email") or "").lower()
    return ""

def main():
    analyze = "--merge" not in sys.argv
    if analyze:
        logger.info("ANALYSIS MODE (Dry Run). Use --merge to execute changes.")
    else:
        logger.info("MERGE MODE. Executing changes.")

    all_pages = fetch_all_pages()
    logger.info(f"Total pages fetched: {len(all_pages)}")

    groups = {} # Key -> List of Pages
    
    for p in all_pages:
        # Generate potential keys in order of reliability
        raw_phone = get_prop_text(p, "Phone")
        norm_phone = normalize_phone(raw_phone)
        email = get_prop_text(p, "Email")
        first = get_prop_text(p, "First Name")
        last = get_prop_text(p, "Last Name")
        full_name = f"{first}|{last}" if (first and last) else ""
        
        potential_keys = []
        if norm_phone and len(norm_phone) >= 10: potential_keys.append(f"PH:{norm_phone}")
        if email: potential_keys.append(f"EM:{email}")
        if full_name: potential_keys.append(f"NM:{full_name}")
        
        # Priority grouping
        assigned = False
        for key in potential_keys:
            if key not in groups:
                 groups[key] = []
            groups[key].append(p)
            assigned = True
            break # Once assigned to a group, don't put in another
            
    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
    
    if not duplicate_groups:
        logger.info("No duplicates found.")
        return

    logger.info(f"Found {len(duplicate_groups)} groups of duplicates.")
    
    for phone, pages in duplicate_groups.items():
        # Pick master (most properties filled)
        sorted_pages = sorted(pages, key=lambda p: count_filled_props(p), reverse=True)
        master = sorted_pages[0]
        duplicates = sorted_pages[1:]
        
        try:
            title_prop = master["properties"].get("TITLE", {}).get("title", [])
            master_title = title_prop[0].get("plain_text", "Untitled") if title_prop else "Untitled"
            
            logger.info(f"\nGroup for {phone} ({master_title}):")
            logger.info(f"  Master Page ID: {master['id']} (Filled props: {count_filled_props(master)})")
            for d in duplicates:
                logger.info(f"  Duplicate ID: {d['id']} (Filled props: {count_filled_props(d)})")
        except Exception as e:
            logger.warning(f"Error printing group details for {phone}: {e}")

        if not analyze:
            try:
                merge_records(master, duplicates)
                logger.info(f"  SUCCESS: Merged {len(duplicates)} duplicates into master.")
            except Exception as e:
                logger.error(f"  FAILED to merge {phone}: {e}")

    logger.info("\nProcess complete.")

if __name__ == "__main__":
    main()
