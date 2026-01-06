import os
import sys
import json
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

# --- Configuration ---
# You can set this in .env or pass it relies on auto-discovery
NOTION_DB_ENV_VAR = "NOTION_SNAPPIC_DATABASE_ID"

# Fallback environment variables from other scripts
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_VERSION = "2022-06-28"

BASE_URL = "https://help.snappic.com"
UPDATES_COLLECTION_URL = "https://help.snappic.com/en/collections/318671-updates"
NEW_FEATURES_COLLECTION_URL = "https://help.snappic.com/en/collections/16751111-new-features-release"

def get_headers_notion() -> Dict[str, str]:
    if not NOTION_API_KEY:
        print("Error: NOTION_API_KEY not found in environment variables.")
        sys.exit(1)
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

def search_database_by_name(name_query: str) -> Optional[str]:
    """Searches for a database by name and returns its ID."""
    url = "https://api.notion.com/v1/search"
    payload = {
        "query": name_query,
        "filter": {
            "value": "database",
            "property": "object"
        }
    }
    try:
        response = requests.post(url, headers=get_headers_notion(), json=payload)
        response.raise_for_status()
        results = response.json().get("results", [])
        if results:
            print(f"Found database matching '{name_query}': {results[0]['title'][0]['plain_text']} ({results[0]['id']})")
            return results[0]['id']
    except Exception as e:
        print(f"Warning: Failed to search for database '{name_query}': {e}")
    return None

def get_target_database_id() -> str:
    """Gets DB ID from env var or attempts to find one."""
    # 1. Check specific env var
    db_id = os.getenv(NOTION_DB_ENV_VAR)
    if db_id:
        return db_id
    
    # 2. Try to find a likely candidate
    print("NOTION_SNAPPIC_DATABASE_ID not set. Searching for a 'Snappic' database...")
    db_id = search_database_by_name("Snappic")
    if db_id:
        return db_id
    
    db_id = search_database_by_name("Updates")
    if db_id:
        return db_id
        
    print("Error: Could not find a target Notion database. Please set NOTION_SNAPPIC_DATABASE_ID.")
    sys.exit(1)

def scrape_articles_from_collection(collection_url: str):
    """Scrapes article URLs from a collection page."""
    print(f"Fetching collection: {collection_url}")
    try:
        response = requests.get(collection_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Intercom help centers usually have links like <a href="/en/articles/...">
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if "/en/articles/" in href:
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                links.append(full_url)
        
        # Deduplicate
        return list(set(links))
    except Exception as e:
        print(f"Error scraping collection {collection_url}: {e}")
        return []

def scrape_article_content(article_url: str) -> Optional[Dict[str, Any]]:
    """Fetches and parses a single article."""
    print(f"Scraping article: {article_url}")
    try:
        response = requests.get(article_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extraction logic depends on Intercom template
        # Title usually in h1
        title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "Untitled"
        
        # Date often in a meta tag or specific class. Intercom articles usually don't have a clear date in meta,
        # but sometimes in .article__meta or similar. We'll default to Now if missing.
        # Check for 'Updated over a week ago' etc text? 
        # For simplicity, we'll just grab the content.
        
        # body content
        article_body = soup.find('article') or soup.find('div', class_='article__body') or soup.body
        content_text = article_body.get_text(separator="\n", strip=True) if article_body else ""
        
        # Truncate content for Notion text block limit (2000 chars per block usually)
        # We'll just store the first 2000 chars in the main text block or snippet.
        
        return {
            "title": title,
            "url": article_url,
            "content": content_text,
            "scraped_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error scraping article {article_url}: {e}")
        return None

def get_database_properties(db_id: str) -> Dict[str, str]:
    """
    Fetches the database schema to map property names.
    Returns a dict like {'title': 'Name', 'url': 'URL', 'date': 'Date'}
    """
    url = f"https://api.notion.com/v1/databases/{db_id}"
    try:
        response = requests.get(url, headers=get_headers_notion())
        response.raise_for_status()
        data = response.json()
        properties = data.get("properties", {})
        
        mapping = {}
        for name, prop in properties.items():
            if prop['type'] == 'title':
                mapping['title'] = name
            elif prop['type'] == 'url':
                mapping['url'] = name
            elif prop['type'] == 'date':
                mapping['date'] = name
            elif prop['type'] == 'rich_text' and 'content' in name.lower():
                mapping['content'] = name # Optional content field
        
        print(f"Discovered Schema Mapping: {mapping}")
        return mapping
    except Exception as e:
        print(f"Error fetching schema: {e}")
        return {}

def check_if_exists_in_notion(db_id: str, url: str, url_prop_name: str) -> bool:
    """Checks if the URL already exists in the database."""
    if not url_prop_name:
        return False # Can't check if we don't know the URL field
        
    search_url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {
        "filter": {
            "property": url_prop_name,
            "url": {
                "equals": url
            }
        }
    }
    try:
        response = requests.post(search_url, headers=get_headers_notion(), json=payload)
        if response.status_code == 400:
            return False
            
        response.raise_for_status()
        results = response.json().get("results", [])
        return len(results) > 0
    except Exception:
        return False

def add_to_notion(db_id: str, article: Dict[str, Any], mapping: Dict[str, str]):
    """Adds a new page to the Notion DB using dynamic property names."""
    url = "https://api.notion.com/v1/pages"
    
    title_prop = mapping.get('title', 'Name')
    url_prop = mapping.get('url', 'URL')
    date_prop = mapping.get('date') # Optional
    
    properties = {
        title_prop: {
            "title": [{"text": {"content": article['title']}}]
        }
    }
    
    if url_prop:
        properties[url_prop] = {"url": article['url']}
        
    if date_prop:
        properties[date_prop] = {"date": {"start": datetime.now().isoformat()}}
    
    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"text": {"content": article['content'][:1900]}}
                ]
            }
        }
    ]
    
    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
        "children": children
    }
    
    try:
        response = requests.post(url, headers=get_headers_notion(), json=payload)
        if response.status_code == 400:
            print(f"Failed to add {article['title']}. Notion 400 Error: {response.text}")
        else:
            response.raise_for_status()
            print(f"Successfully added: {article['title']}")
    except Exception as e:
        print(f"Error adding to Notion: {e}")

def main():
    # 0. Load env
    try:
        from dotenv import load_dotenv
        # Try loading from current directory explicitly
        env_path = os.path.join(os.getcwd(), '.env')
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)
        else:
            # Fallback to default search
            load_dotenv()
    except ImportError:
        print("Warning: python-dotenv not installed. Relying on system env vars.")

    # Re-fetch vars after loading
    global NOTION_API_KEY
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    
    if not NOTION_API_KEY:
        print("Error: NOTION_API_KEY not found. Please ensure .env exists or vars are exported.")
        sys.exit(1)

    # 1. Get DB ID
    db_id = get_target_database_id()
    print(f"Targeting Database ID: {db_id}")
    
    # 2. Get Schema
    mapping = get_database_properties(db_id)
    if 'title' not in mapping:
        print("Error: Could not find a 'title' property in the database. Cannot continue.")
        sys.exit(1)
    
    # 3. Scrape Collections
    all_links = []
    all_links.extend(scrape_articles_from_collection(UPDATES_COLLECTION_URL))
    all_links.extend(scrape_articles_from_collection(NEW_FEATURES_COLLECTION_URL))
    
    print(f"Found {len(all_links)} total articles.")
    
    # 4. Process Articles
    for link in all_links:
        if check_if_exists_in_notion(db_id, link, mapping.get('url')):
            print(f"Skipping (already exists): {link}")
            continue
            
        article_data = scrape_article_content(link)
        if article_data:
            add_to_notion(db_id, article_data, mapping)
            time.sleep(0.5) # Rate limit politeness

if __name__ == "__main__":
    main()
