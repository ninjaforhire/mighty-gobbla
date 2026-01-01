import os
import sys
import json
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logging
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Error log for critical issues
ERROR_LOG_PATH = ".tmp/sync_errors.log"
os.makedirs(".tmp", exist_ok=True)
error_handler = logging.FileHandler(ERROR_LOG_PATH)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(error_handler)

import time
from functools import wraps

def retry_request(max_retries=3, backoff=2):
    """Decorator to retry requests on 429 and 5xx errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    response = func(*args, **kwargs)
                    if response.status_code == 429:
                        wait = backoff ** (retries + 1)
                        logger.warning(f"Rate limited (429). Retrying in {wait}s...")
                        time.sleep(wait)
                        retries += 1
                        continue
                    if 500 <= response.status_code < 600:
                        logger.warning(f"Server error ({response.status_code}). Retrying...")
                        time.sleep(backoff)
                        retries += 1
                        continue
                    return response
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request exception: {e}")
                    retries += 1
                    time.sleep(backoff)
            return func(*args, **kwargs) # Local call to trigger final error
        return wrapper
    return decorator

@retry_request()
def safe_post(url, **kwargs):
    return requests.post(url, **kwargs)

@retry_request()
def safe_get(url, **kwargs):
    return requests.get(url, **kwargs)

@retry_request()
def safe_patch(url, **kwargs):
    return requests.patch(url, **kwargs)

# Load Environment Variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_CLIENTS_DATABASE_ID")
OPENPHONE_API_KEY = os.getenv("OPENPHONE_API_KEY") # This is likely a Bearer token or similar key

# Notion API Version
NOTION_VERSION = "2022-06-28"

def get_headers_notion() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

def get_headers_openphone() -> Dict[str, str]:
    # OpenPhone API typically uses header "Authorization: key_..."
    # Verify exact format in docs, usually just the key string if it's not Bearer
    # If the key itself doesn't contain 'Bearer', we might need to add it. 
    # Based on many modern APIs, it's often passed directly or as Bearer. 
    # We will assume it's passed as is or user provided 'Bearer ...' if needed, 
    # but safer to standard header format.
    return {
        "Authorization": OPENPHONE_API_KEY, 
        "Content-Type": "application/json"
    }

def search_notion_client(phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Search for a client in Notion by phone number.
    Tries multiple formats for robustness.
    """
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    
    # Clean phone number (digits only) for alternate searches if needed
    clean_phone = "".join(filter(str.isdigit, phone_number))
    
    # We'll try exact match first as it's most efficient
    formats_to_try = [phone_number]
    if clean_phone and clean_phone != phone_number:
        formats_to_try.append(clean_phone)
        if not clean_phone.startswith("1") and len(clean_phone) == 10:
             formats_to_try.append(f"1{clean_phone}")
             formats_to_try.append(f"+1{clean_phone}")

    for fmt in formats_to_try:
        payload = {
            "filter": {
                "property": "Phone",
                "phone_number": {
                    "equals": fmt
                }
            }
        }
        
        try:
            response = safe_post(url, headers=get_headers_notion(), json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            if results:
                logger.info(f"Found Notion record using format: {fmt}")
                return results[0]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching Notion with format {fmt}: {e}")
    
    return None

def fetch_openphone_contact(phone_number: str) -> Dict[str, Any]:
    """
    Attempt to fetch contact details from OpenPhone.
    Returns a dict with found info (name, email, company, etc.)
    """
    if not OPENPHONE_API_KEY:
        logger.warning("OPENPHONE_API_KEY not set. Skipping contact enrichment.")
        return {}

    # OpenPhone API is technically 'Quo' now but endpoints usually remain similar or redirect.
    # We'll use the standard v1 endpoint for contacts search if available, 
    # or list contacts with filter.
    # Note: The exact endpoint might need adjustment based on latest Quo docs.
    # Assuming standard structure: GET /v1/contacts?phoneNumbers=...
    
    # We'll try to sanitize the phone number for search (e.g. +1...)
    encoded_phone = requests.utils.quote(phone_number)
    url = f"https://api.openphone.com/v1/contacts?phoneNumbers={encoded_phone}" 
    # Update URL to Quo if different, but usually legacy URLs work.

    try:
        response = safe_get(url, headers=get_headers_openphone(), timeout=10)
        # If 401/403, might be key issue. If 404, just no contact.
        if response.status_code == 404:
            return {}
        
        response.raise_for_status()
        data = response.json()
        
        # Structure depends on API output. 
        # Typically returns a list 'data' or 'items'.
        items = data.get("data", [])
        for contact in items:
            # Extract fields from defaultFields
            fields = contact.get("defaultFields", {})
            phone_list = fields.get("phoneNumbers", [])
            
            # Check if this contact actually has the number we searched for
            has_match = False
            for p in phone_list:
                # Compare normalized (digits only) or exact. 
                # E.164 is safer.
                if p.get("value") == phone_number:
                    has_match = True
                    break
            
            if not has_match:
                continue

            # Emails are often a list of objects like [{"value": "...", "name": "..."}]
            emails = fields.get("emails", [])
            email = emails[0].get("value") if emails else None
            
            # Extract tags from customFields
            tags = []
            custom_fields = contact.get("customFields", [])
            for cf in custom_fields:
                if cf.get("name") == "Tags" and cf.get("type") == "multi-select":
                    tags = cf.get("value", [])
                    break

            return {
                "firstName": fields.get("firstName", ""),
                "lastName": fields.get("lastName", ""),
                "company": fields.get("company", ""),
                "email": email,
                "role": fields.get("role", ""),
                "tags": tags
            }
        
        logger.info(f"No strict match found in Quo for {phone_number} among {len(items)} results.")
            
    except Exception as e:
        logger.warning(f"Failed to fetch OpenPhone contact: {e}")
    
    return {}

def create_notion_client(phone_number: str, contact_data: Dict[str, Any], call_data: Dict[str, Any]):
    """Create a new page in Notion for the client."""
    url = "https://api.notion.com/v1/pages"
    
    # Construct Name
    first = contact_data.get("firstName", "")
    last = contact_data.get("lastName", "")
    full_name = f"{first} {last}".strip()
    if not full_name:
        full_name = f"Unknown {phone_number}"

    # Properties
    properties = {
        "TITLE": {
            "title": [{"text": {"content": full_name}}]
        },
        "Phone": {
            "phone_number": phone_number
        },
        "Status": {
            "status": {"name": "New Import"}
        },
        "Last Call": {
             "date": {"start": call_data.get("timestamp")}
        }
    }

    # Add optional fields if they exist
    if contact_data.get("firstName"):
        properties["First Name"] = {"rich_text": [{"text": {"content": contact_data["firstName"]}}]}
    if contact_data.get("lastName"):
        properties["Last Name"] = {"rich_text": [{"text": {"content": contact_data["lastName"]}}]}
    if contact_data.get("email"):
        properties["Email"] = {"email": contact_data["email"]}
    # Company Record is a relation, we cannot set it with just a string.
    # We'll skip it for now to avoid errors.
    # if contact_data.get("company"):
    #    properties["Company Record"] = ...
    if contact_data.get("role"):
        properties["Role"] = {"rich_text": [{"text": {"content": contact_data["role"]}}]}
    if contact_data.get("tags"):
        properties["Tags"] = {"multi_select": [{"name": t} for t in contact_data["tags"]]}

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
        # We can also add default page content (Initial call log)
        "children": [
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"text": {"content": "Interaction History"}}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"text": {"content": f"Initial {call_data['type']} recorded on {call_data['timestamp']}. Status: {call_data['status']}"}}
                    ]
                }
            }
        ]
        if not call_data.get("text") else [
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"text": {"content": "Interaction History"}}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"text": {"content": f"Initial {call_data['type']} on {call_data['timestamp']}\nContent: {call_data['text']}"}}
                    ]
                }
            }
        ]
    }

    try:
        response = safe_post(url, headers=get_headers_notion(), json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create Notion page: {e}")
        if hasattr(e, 'response') and e.response:
             logger.error(f"Notion Page Creation Error Details: {e.response.text}")
        raise

def update_notion_client(page_id: str, existing_props: Dict[str, Any], contact_data: Dict[str, Any], call_data: Dict[str, Any]):
    """Update existing Notion client with new call info and missing details."""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    
    properties = {
        "Last Call": {
             "date": {"start": call_data.get("timestamp")}
        }
    }
    
    # Merge logic: Only update if Notion is empty and we have data
    if contact_data.get("email") and not existing_props.get("Email", {}).get("email"):
        properties["Email"] = {"email": contact_data["email"]}
        
    # Update Title if it's currently "Unknown"
    title_list = existing_props.get("TITLE", {}).get("title", [])
    current_title = title_list[0].get("plain_text", "") if title_list else ""
    
    first = contact_data.get("firstName", "")
    last = contact_data.get("lastName", "")
    full_name = f"{first} {last}".strip()
    
    if full_name and ("Unknown" in current_title or not current_title):
        properties["TITLE"] = {"title": [{"text": {"content": full_name}}]}
        
    if contact_data.get("firstName") and not existing_props.get("First Name", {}).get("rich_text"):
        properties["First Name"] = {"rich_text": [{"text": {"content": contact_data["firstName"]}}]}

    if contact_data.get("lastName") and not existing_props.get("Last Name", {}).get("rich_text"):
        properties["Last Name"] = {"rich_text": [{"text": {"content": contact_data["lastName"]}}]}

    if contact_data.get("role") and not existing_props.get("Role", {}).get("rich_text"):
        properties["Role"] = {"rich_text": [{"text": {"content": contact_data["role"]}}]}
    
    # Merge Tags
    if contact_data.get("tags"):
        existing_tags = [t["name"] for t in existing_props.get("Tags", {}).get("multi_select", [])]
        new_tags = contact_data["tags"]
        # Union of tags, case-insensitive check
        merged_tags_set = set(existing_tags)
        for nt in new_tags:
            if nt.lower() not in [et.lower() for et in existing_tags]:
                merged_tags_set.add(nt)
        
        if len(merged_tags_set) > len(existing_tags):
            properties["Tags"] = {"multi_select": [{"name": t} for t in merged_tags_set]}
    
    payload = {"properties": properties}

    try:
        # 1. Update Properties
        response = safe_patch(url, headers=get_headers_notion(), json=payload, timeout=10)
        response.raise_for_status()
        
        # 2. Append Log to Page Content
        children_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        
        log_text = f"{call_data['type']} on {call_data['timestamp']} - {call_data['status']} - {call_data['direction']}"
        if call_data.get("text"):
            log_text += f"\nContent: {call_data['text']}"
            
        children_payload = {
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"text": {"content": log_text}}
                        ]
                    }
                }
            ]
        }
        safe_patch(children_url, headers=get_headers_notion(), json=children_payload, timeout=10)
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to update Notion page: {e}")
        raise

def main():
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        print(json.dumps({"status": "error", "message": "Missing Notion environment variables"}))
        sys.exit(1)

    # 1. Read Payload
    try:
        input_data = sys.stdin.read()
        if not input_data:
            print(json.dumps({"status": "error", "message": "No input received"}))
            sys.exit(1)
        
        payload = json.loads(input_data)
    except json.JSONDecodeError:
        print(json.dumps({"status": "error", "message": "Invalid JSON input"}))
        sys.exit(1)

    # 2. Extract Data
    # Supports flat structure or Quo's 'data' wrapper
    data_obj = payload.get("data", payload)
    event_type = payload.get("type", "call.completed") # Default to call if unknown
    
    if "object" in data_obj:
        obj = data_obj["object"]
    else:
        obj = data_obj

    # Handle different event types
    is_message = event_type.startswith("message.")
    
    direction = obj.get("direction", "incoming")
    status = obj.get("status", "completed")
    
    # Extraction logic for phone numbers
    participants_to_sync = []
    
    if is_message:
        # For messages, Quo usually provides a 'participants' list for group threads
        participants_data = obj.get("participants", [])
        if participants_data:
            # It's a group thread or has explicit participant list
            for p in participants_data:
                p_phone = p.get("userId") # OpenPhone sometimes uses userId or phoneNumber
                if not p_phone or "@" in str(p_phone): # Skip user IDs or emails if present
                    p_phone = p.get("phoneNumber")
                
                # Filter out the 'from' number (we handle it below) and business numbers
                if p_phone and p_phone != obj.get("from"):
                     participants_to_sync.append(p_phone)
        
        # Always include the primary 'from' or 'to' number
        primary_number = obj.get("from") if direction == "incoming" else obj.get("to")
        if primary_number and primary_number not in participants_to_sync:
            # We want to sync to both 'from' and 'to' if it's a text? 
            # Usually only sync to the EXTERNAL number.
            # In a group text, 'to' might be a user ID or a list.
            pass
            
        client_phone = primary_number
        message_text = obj.get("body", "[Media/Attachment]")
        interaction_type = "Group Message" if len(participants_to_sync) > 0 else "Message"
        timestamp = obj.get("createdAt", datetime.now().isoformat())
        
        # Add transcript/body context
        call_text = message_text
        if len(participants_to_sync) > 0:
            participant_names = []
            # We don't have their names yet, just numbers
            group_context = f"Group participants: {', '.join(participants_to_sync)}"
            call_text = f"{group_context}\n\nContent: {message_text}"
            
    else:
        client_phone = obj.get("from") if direction == "incoming" else obj.get("to")
        interaction_type = "Call"
        timestamp = obj.get("startedAt", datetime.now().isoformat())
        
        # Extract Transcript
        transcript_data = obj.get("transcription")
        if not transcript_data and obj.get("media"):
            # Try to find transcription in media array
            for m in obj.get("media", []):
                if m.get("type") == "transcription":
                    transcript_data = m.get("text")
                    break
        
        call_text = transcript_data if transcript_data else None
    
    # Define a list of all targets (for group texts, this is multiple people)
    targets = [client_phone] if not is_message else participants_to_sync
    # Ensure client_phone is included if it was the 'from' in an incoming text
    if is_message and direction == "incoming" and client_phone not in targets:
        targets.append(client_phone)
    # Ensure we don't sync to the business number (usually matches payload['data']['object']['phoneNumber'] or similar)
    business_number = obj.get("phoneNumber")
    targets = [t for t in targets if t and t != business_number]

    if not targets:
        logger.warning(f"No target phone numbers found to sync: {json.dumps(obj)}")
        print(json.dumps({"status": "skipped", "message": "No targets found"}))
        sys.exit(0)

    call_data = {
        "timestamp": timestamp,
        "status": status,
        "direction": direction,
        "type": interaction_type,
        "text": call_text,
        "duration": obj.get("duration", 0)
    }

    logger.info(f"Processing {interaction_type} {direction} for {len(targets)} targets: {targets}")

    results_summary = []
    
    for target_phone in targets:
        # 3. Enrich Data
        contact_data = fetch_openphone_contact(target_phone)
        logger.info(f"Enriched Data for {target_phone}: {contact_data}")

        # 4. Search Notion
        existing_page = search_notion_client(target_phone)
        
        if existing_page:
            logger.info(f"Found existing client {target_phone}: {existing_page['id']}")
            update_notion_client(existing_page['id'], existing_page['properties'], contact_data, call_data)
            results_summary.append({
                "phone": target_phone,
                "action": "updated",
                "notion_page_id": existing_page['id']
            })
        else:
            logger.info(f"Client {target_phone} not found. Creating new...")
            new_page = create_notion_client(target_phone, contact_data, call_data)
            results_summary.append({
                "phone": target_phone,
                "action": "created",
                "notion_page_id": new_page['id']
            })

    print(json.dumps({"status": "success", "synced": results_summary}))

if __name__ == "__main__":
    main()
