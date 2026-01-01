import os
import sys
import json
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

# Reuse same logging and basic setup
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_CLIENTS_DATABASE_ID")
OPENPHONE_API_KEY = os.getenv("OPENPHONE_API_KEY")
NOTION_VERSION = "2022-06-28"

def get_headers_notion():
    return {"Authorization": f"Bearer {NOTION_API_KEY}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"}

def get_headers_openphone():
    return {"Authorization": OPENPHONE_API_KEY, "Content-Type": "application/json"}

# --- Notion Helpers ---

def search_notion_client(phone_number: str):
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    payload = {"filter": {"property": "Phone", "phone_number": {"equals": phone_number}}}
    response = requests.post(url, headers=get_headers_notion(), json=payload)
    if response.status_code == 200:
        results = response.json().get("results", [])
        return results[0] if results else None
    return None

def create_notion_client(phone_number: str, contact_data: dict):
    url = "https://api.notion.com/v1/pages"
    full_name = f"{contact_data.get('firstName', '')} {contact_data.get('lastName', '')}".strip()
    if not full_name: full_name = f"Unknown {phone_number}"
    
    props = {
        "TITLE": {"title": [{"text": {"content": full_name}}]},
        "Phone": {"phone_number": phone_number},
        "Status": {"status": {"name": "New Import"}}
    }
    if contact_data.get("firstName"): props["First Name"] = {"rich_text": [{"text": {"content": contact_data["firstName"]}}]}
    if contact_data.get("lastName"): props["Last Name"] = {"rich_text": [{"text": {"content": contact_data["lastName"]}}]}
    if contact_data.get("email"): props["Email"] = {"email": contact_data["email"]}
    if contact_data.get("role"): props["Role"] = {"rich_text": [{"text": {"content": contact_data["role"]}}]}
    if contact_data.get("tags"): props["Tags"] = {"multi_select": [{"name": t} for t in contact_data["tags"]]}
    
    payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": props}
    res = requests.post(url, headers=get_headers_notion(), json=payload)
    return res.json()

def update_notion_client(page_id: str, existing_props: dict, contact_data: dict):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    props = {}
    
    # Update title if unknown
    title_list = existing_props.get("TITLE", {}).get("title", [])
    current_title = title_list[0].get("plain_text", "") if title_list else ""
    full_name = f"{contact_data.get('firstName', '')} {contact_data.get('lastName', '')}".strip()
    if full_name and ("Unknown" in current_title or not current_title):
        props["TITLE"] = {"title": [{"text": {"content": full_name}}]}

    # Other fields only if empty
    if contact_data.get("email") and not existing_props.get("Email", {}).get("email"):
        props["Email"] = {"email": contact_data["email"]}
    if contact_data.get("role") and not existing_props.get("Role", {}).get("rich_text"):
        props["Role"] = {"rich_text": [{"text": {"content": contact_data["role"]}}]}
    if contact_data.get("firstName") and not existing_props.get("First Name", {}).get("rich_text"):
        props["First Name"] = {"rich_text": [{"text": {"content": contact_data["firstName"]}}]}
    if contact_data.get("lastName") and not existing_props.get("Last Name", {}).get("rich_text"):
        props["Last Name"] = {"rich_text": [{"text": {"content": contact_data["lastName"]}}]}
        
    # Merge Tags
    if contact_data.get("tags"):
        existing_tags = [t["name"] for t in existing_props.get("Tags", {}).get("multi_select", [])]
        merged = list(set(existing_tags) | set(contact_data["tags"]))
        if len(merged) > len(existing_tags):
            props["Tags"] = {"multi_select": [{"name": t} for t in merged]}

    if not props: return None
    res = requests.patch(url, headers=get_headers_notion(), json={"properties": props})
    return res.json()

# --- Quo Helpers ---

def get_all_quo_contacts():
    url = "https://api.openphone.com/v1/contacts"
    contacts = []
    next_token = None
    
    while True:
        params = {"maxResults": 50}
        if next_token: params["pageToken"] = next_token
        
        logger.info(f"Fetching Quo contacts (token: {next_token})...")
        response = requests.get(url, headers=get_headers_openphone(), params=params)
        if response.status_code != 200:
            logger.error(f"Quo API Error: {response.status_code} - {response.text}")
            response.raise_for_status()
        
        data = response.json()
        logger.debug(f"Response Data Keys: {list(data.keys())}")
        
        new_contacts = data.get("data", [])
        contacts.extend(new_contacts)
        
        prev_token = next_token
        next_token = data.get("nextPageToken")
        
        if not next_token or next_token == prev_token:
            break
            
    return contacts

def parse_quo_contact(contact: dict):
    fields = contact.get("defaultFields", {})
    phones = [p.get("value") for p in fields.get("phoneNumbers", []) if p.get("value")]
    emails = fields.get("emails", [])
    email = emails[0].get("value") if emails else None
    
    tags = []
    for cf in contact.get("customFields", []):
        if cf.get("name") == "Tags" and cf.get("type") == "multi-select":
            tags = cf.get("value", [])
            break
            
    return {
        "phone": phones[0] if phones else None,
        "firstName": fields.get("firstName", ""),
        "lastName": fields.get("lastName", ""),
        "company": fields.get("company", ""),
        "email": email,
        "role": fields.get("role", ""),
        "tags": tags,
        "createdAt": contact.get("createdAt")
    }

def main():
    logger.info("Starting Massive Quo to Notion Sync (Full Year 2025)...")
    logger.info("Criteria: Must have BOTH First and Last Name logged.")
    
    dry_run = "--run" not in sys.argv
    if dry_run:
        logger.info("DRY RUN MODE. Use --run to commit changes.")

    all_raw = get_all_quo_contacts()
    logger.info(f"Retrieved {len(all_raw)} total contacts from Quo.")

    seen_phones = set()
    targets = []
    for raw in all_raw:
        parsed = parse_quo_contact(raw)
        if not parsed["phone"]: continue
        if parsed["phone"] in seen_phones: continue
        
        # Filter for Full Year 2025 & REQUIRE First + Last Name
        created_at = parsed["createdAt"]
        first_name = (parsed["firstName"] or "").strip()
        last_name = (parsed["lastName"] or "").strip()
        
        has_full_name = bool(first_name) and bool(last_name)
        is_2025 = created_at and "2025" in created_at
        
        if is_2025 and has_full_name:
            targets.append(parsed)
            seen_phones.add(parsed["phone"])

    logger.info(f"Found {len(targets)} valid 2025 contacts with full names.")

    count = 0
    for contact in targets:
        count += 1
        phone = contact["phone"]
        logger.info(f"[{count}/{len(targets)}] Syncing {phone} ({contact['firstName']} {contact['lastName']})...")
        
        if dry_run:
            continue
            
        existing = search_notion_client(phone)
        if existing:
            update_notion_client(existing["id"], existing["properties"], contact)
            logger.info("Updated existing record.")
        else:
            create_notion_client(phone, contact)
            logger.info("Created new record.")

    logger.info("Massive sync complete.")

if __name__ == "__main__":
    main()
