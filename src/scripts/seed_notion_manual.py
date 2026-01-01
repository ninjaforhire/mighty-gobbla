
import os
import json
import requests
import time
import sys
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_COMPETITORS_DATABASE_ID")

COMPETITORS = [
    {"name": "Picture Perfect PhotoBooth Rental Dallas", "url": "https://www.theknot.com/marketplace/picture-perfect-photobooth-rental-dallas-dallas-tx-965825"},
    {"name": "The Social Production", "url": "https://www.socialprophotobooth.com/"},
    {"name": "SelfieBooth Co.", "url": "https://selfieboothco.com/"},
    {"name": "Mighty Photo Booths", "url": "https://mightyphotobooths.com/"},
    {"name": "Proparazzi Photo Booths", "url": "https://www.proparazziphotobooths.com/"},
    {"name": "The Photo Bus DFW", "url": "https://www.thephotobusdfw.com/"},
    {"name": "Photo Booth Dallas", "url": "https://www.photoboothdallas.org/"},
    {"name": "LIT Lenz Photo", "url": "https://litlenz.com/"},
    {"name": "Marky Booth Dallas", "url": "https://www.markybooth.com/"},
    {"name": "LOL Photo Booths & Events", "url": "https://lolphotobooth.com/"},
    {"name": "Red Photo Booths", "url": "https://www.redphotobooths.com/"},
    {"name": "Dallas Social Booth", "url": "https://dallassocialbooth.com/"},
    {"name": "The LAB Photo Booth", "url": "https://thelabphotobooth.com/"},
    {"name": "Hipstr", "url": "https://hipstr.com/"},
    {"name": "Infinity Media Dallas", "url": "https://infinitymediadallas.com/"},
    {"name": "Pixster Photobooth", "url": "https://www.pixsterphotobooth.com/"},
    {"name": "Eternal Sunshine Photobus", "url": "https://eternalsunshinephotobus.com/"},
    {"name": "Palm and Pine Photo Truck", "url": "https://palmandpinephototruck.com/"},
    {"name": "Star Of Texas Photobooth", "url": "https://staroftexasphotobooth.com/"},
    {"name": "iHart Photo Booth", "url": "https://ihartphotobooth.com/"},
    {"name": "Miroir Miroir Photo Booth", "url": "https://miroirmiroirphotobooth.com/"},
    {"name": "360 Party Machine", "url": "https://360partymachine.com/"},
    {"name": "Interactive Dallas", "url": "https://interactivedallas.com/"},
    {"name": "Luxe Booth", "url": "https://luxebooth.com/photo-booth-rental-dallas/"}
]

def get_headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

def find_entry(website_url):
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "Website",
            "url": {
                "equals": website_url
            }
        }
    }
    try:
        response = requests.post(url, headers=get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        results = response.json().get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"Error searching Notion for {website_url}: {e}")
        return None

def create_entry(info):
    url = "https://api.notion.com/v1/pages"
    
    properties = {
        "Competitor Name": {
            "title": [{"text": {"content": info['name']}}]
        },
        "Website": {
            "url": info['url']
        }
    }
    
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties
    }
    
    try:
        response = requests.post(url, headers=get_headers(), json=payload, timeout=10)
        response.raise_for_status()
        print(f"Created Notion entry for {info['name']}")
        return response.json()
    except Exception as e:
        print(f"Error creating Notion entry for {info['name']}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Server Response: {e.response.text}")
        return None

def main():
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        print("Missing Notion API Key or Database ID.")
        return

    print(f"Seeding {len(COMPETITORS)} competitors into Notion...")
    sys.stdout.flush()
    
    for comp in COMPETITORS:
        existing = find_entry(comp['url'])
        if existing:
            print(f"Skipping existing: {comp['name']}")
        else:
            create_entry(comp)
            # Polite rate limit prevention
            time.sleep(0.3)
        sys.stdout.flush()
            
    print("Seeding complete.")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
