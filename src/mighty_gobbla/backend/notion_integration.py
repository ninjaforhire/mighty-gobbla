import os
import requests
import json
import logging
from datetime import datetime
from settings import get_setting

logger = logging.getLogger("MightyGobbla.Notion")

def add_to_notion_expenses(file_data):
    """
    Adds an entry to the Notion Expenses database.
    Values retrieved from settings.py
    """
    token = get_setting("notion_token")
    db_id = get_setting("notion_db_id")
    
    if not token or not db_id:
        logger.error("Notion Token or Database ID missing in settings.")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    # 1. Check for duplicates
    # We query for an entry with the same Date and same Name (Filename) or Store + Amount
    # For now, let's use the Filename as the unique identifier "Name"
    
    query_url = f"https://api.notion.com/v1/databases/{db_id}/query"
    
    # Safe date parsing
    try:
        raw_date = file_data.get('date', '')
        if len(raw_date) == 6:
            dt = datetime.strptime(raw_date, "%y%m%d")
            iso_date = dt.strftime("%Y-%m-%d")
        else:
            iso_date = datetime.now().strftime("%Y-%m-%d")
    except:
        iso_date = datetime.now().strftime("%Y-%m-%d")

    amount = file_data.get('amount', 0.0)
    store = file_data.get('store', 'Unknown')
    filename = file_data.get('filename')
    payment_raw = file_data.get('payment', 'Unknown')
    
    # Parse Payment Details
    # payment_raw ex: "Card-1234", "PayPal", "Check-101"
    payment_method = "Other"
    payment_type = "Credit Card" # Default assumption for cards
    last_4 = ""
    
    if "Card" in payment_raw:
        payment_type = "Credit Card"
        if "-" in payment_raw:
            last_4 = payment_raw.split("-")[1]
            if last_4 == "XXXX": last_4 = ""
            
    elif "PayPal" in payment_raw:
        payment_method = "Other" # PayPal isn't in strict options list seen, maybe 'Other'?
        payment_type = "Credit Card" # Often backed by card? Or leave empty? 
        # Actually schema 'Payment Method' has 'Square', 'Venmo', 'Zelle'... no PayPal. 'Other' is safest.
        
    elif "Check" in payment_raw:
        payment_method = "Check"
        payment_type = "Check"
        if "-" in payment_raw:
            last_4 = payment_raw.split("-")[1] # Check number
            
    elif "Cash" in payment_raw:
        payment_method = "Cash"
        payment_type = "Cash"

    # Construct Payload
    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Expense Description": {
                "title": [{"text": {"content": filename}}]
            },
            "Vendor/Supplier": {
                "rich_text": [{"text": {"content": store}}]
            },
            "Vendor/Supplier": {
                "rich_text": [{"text": {"content": store}}]
            },
            "Date Paid": {
                "date": {"start": iso_date}
            },
            "Subtotal": {
                "number": amount
            },
            # Optional fields if we mapped them
            "Payment Type": {
                "select": {"name": payment_type} 
            }
        }
    }
    
    # Add optional fields only if they have values or match known options
    if payment_method != "Other":
        payload["properties"]["Payment Method"] = {"select": {"name": payment_method}}
        
    if last_4:
        payload["properties"]["Last 4 of Card"] = {"rich_text": [{"text": {"content": last_4}}]}

    # Check for duplicates (Broadened: Date Paid only, then filter in Python)
    # We query all entries for this Date.
    query_payload = {
        "filter": {
            "property": "Date Paid",
            "date": {"equals": iso_date}
        }
    }
    
    try:
        dup_check = requests.post(query_url, headers=headers, json=query_payload)
        search_results = []
        if dup_check.status_code == 200:
            search_results = dup_check.json().get('results', [])

        # Python-side filtering for fuzzy matching
        for item in search_results:
            # Check Title
            props = item.get('properties', {})
            
            # Get Title
            # Title prop name is "Expense Description" based on schema
            existing_title = ""
            title_list = props.get("Expense Description", {}).get("title", [])
            if title_list: existing_title = title_list[0].get("plain_text", "").lower()
            
            # Get Vendor
            existing_vendor = ""
            vendor_list = props.get("Vendor/Supplier", {}).get("rich_text", [])
            if vendor_list: existing_vendor = vendor_list[0].get("plain_text", "").lower()
            
            # Get Subtotal & Tax
            existing_subtotal = props.get("Subtotal", {}).get("number") or 0.0
            existing_tax = props.get("Tax Amount", {}).get("number") or 0.0
            existing_total_calc = existing_subtotal + existing_tax
            
            # CHECK MATCH
            match_reason = []
            
            # 1. Store/Title Match
            store_lower = store.lower()
            if store_lower != "unknown" and (store_lower in existing_title or store_lower in existing_vendor):
                match_reason.append("Store Name")
                
            # 2. Strict Title Match
            if filename.lower() == existing_title:
                match_reason.append("Exact Filename")
                
            # 3. Amount Logic (Strict Tax Check)
            # Case A: Exact Subtotal match
            if abs(existing_subtotal - amount) < 0.01:
                match_reason.append("Exact Subtotal Match")
            # Case B: Calculated Total match (Subtotal + Tax vs Amount)
            elif abs(existing_total_calc - amount) < 0.01:
                match_reason.append("Matches Existing Total (Subtotal + Tax)")
            # Case C: Fuzzy check for fallback (if tax isn't entered in Notion yet)
            elif amount > 0 and existing_subtotal > 0:
                diff = abs(existing_subtotal - amount)
                higher = max(existing_subtotal, amount)
                if (diff / higher) < 0.20:
                     match_reason.append(f"Similar Amount (Possible Tax Diff)")
            
            # DECISION: If Date matches (implicit) AND (Store matched OR Amount matched)
            if match_reason:
                logger.info(f"Duplicate suspected: {match_reason}")
                existing_url = item.get('url', 'unknown')
                return {
                    "status": "duplicate_suspected",
                    "message": f"Potential Duplicate: {', '.join(match_reason)}.", 
                    "existing_url": existing_url,
                    "details": f"Found entry on {iso_date}:\nTitle: {existing_title}\nSubtotal: ${existing_subtotal} (+${existing_tax} Tax)\n(Your file: {store} | ${amount})"
                }
                
        # Create Page
        create_url = "https://api.notion.com/v1/pages"
        resp = requests.post(create_url, headers=headers, json=payload)
        
        if resp.status_code == 200:
            logger.info("Successfully added to Notion!")
            return {"status": "success", "url": resp.json().get('url')}
        else:
            logger.error(f"Notion Error {resp.status_code}: {resp.text}")
            return {"status": "error", "message": f"API Error: {resp.text}"}
            
    except Exception as e:
        logger.error(f"Notion Exception: {e}")
        return {"status": "error", "message": str(e)}
