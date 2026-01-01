import os
import sys
import json
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote
from typing import List, Dict, Set, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Load Environment Variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_COMPETITORS_DATABASE_ID")

# Constants
CITIES = [
    "Dallas"
]
BASE_QUERIES = [
    "photo booth rental",
    "360 photo booth",
    "luxury photo booth",
    "wedding photo booth rentals"
]

IGNORED_DOMAINS = {
    "amazon.com", "ebay.com", "etsy.com", "yelp.com", "theknot.com", 
    "weddingwire.com", "thumbtack.com", "yellowpages.com", "facebook.com", 
    "instagram.com", "pinterest.com", "linkedin.com", "youtube.com", 
    "tiktok.com", "twitter.com", "mapquest.com", "tripadvisor.com",
    "bbb.org", "groupon.com", "snappr.com", "peerspace.com", "gigsalad.com"
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

class NotionSync:
    def __init__(self, api_key, database_id):
        self.api_key = api_key
        self.database_id = database_id
        if not self.api_key or not self.database_id:
            logger.warning("Notion API Key or Database ID missing. Sync will be skipped.")

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

    def find_entry(self, website_url):
        if not self.database_id: return None
        
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload = {
            "filter": {
                "property": "Website",
                "url": {
                    "equals": website_url
                }
            }
        }
        try:
            response = requests.post(url, headers=self.get_headers(), json=payload, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Error searching Notion for {website_url}: {e}")
            return None

    def create_entry(self, info: Dict):
        if not self.database_id: return None
        
        url = "https://api.notion.com/v1/pages"
        
        properties = {
            "Competitor Name": {
                "title": [{"text": {"content": info['name']}}]
            },
            "Website": {
                "url": info['url']
            },
            "Status": {
                "select": {"name": "Discovered - Awaiting Deep Scan"}
            },
            "Source": {
                "rich_text": [{"text": {"content": info['source_query']}}]
            }
        }
        
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": properties
        }
        
        try:
            response = requests.post(url, headers=self.get_headers(), json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Created Notion entry for {info['name']}")
            return response.json()
        except Exception as e:
            logger.error(f"Error creating Notion entry for {info['name']}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Notion Error: {e.response.text}")
            return None

class MarketScanner:
    def __init__(self):
        self.session = requests.Session()
        self.results = {} # URL -> info dict

    def clean_url(self, url):
        try:
            # Decode URL first
            url = unquote(url)
            # Remove google redirect wrapper if present
            if "/url?q=" in url:
                parsed = parse_qs(urlparse(url).query)
                if 'q' in parsed:
                    url = parsed['q'][0]
            
            parsed = urlparse(url)
            # Ensure scheme
            scheme = parsed.scheme if parsed.scheme else "https"
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            
            # Reconstruct base URL
            clean = f"{scheme}://{netloc}"
            return clean, netloc
        except Exception:
            return None, None

    def is_valid_candidate(self, url):
        clean, domain = self.clean_url(url)
        if not clean or not domain:
            return False
        
        # Check ignored domains
        for ignored in IGNORED_DOMAINS:
            if domain == ignored or domain.endswith("." + ignored):
                return False
        
        return True

    def search_duckduckgo(self, query):
        logger.info(f"Searching DuckDuckGo for: {query}")
        search_url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": random.choice(USER_AGENTS)
        }
        data = {
            "q": query,
            "kl": "us-en" # Region: US
        }
        
        try:
            # Sleep briefly to be polite even to DDG
            time.sleep(random.uniform(1.5, 3.0))
            
            response = self.session.post(search_url, headers=headers, data=data, timeout=15)
            if response.status_code == 429:
                logger.warning("DDG Rate limit hit. Waiting 60 seconds...")
                time.sleep(60)
                return []
            
            response.raise_for_status()
            return self.parse_ddg_results(response.text, query)
            
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []

    def parse_ddg_results(self, html, query):
        soup = BeautifulSoup(html, 'html.parser')
        found = []
        
        # DDG HTML Structure
        results = soup.select('.result')
        logger.info(f"raw results found: {len(results)}")
        
        for res in results:
            link_tag = res.select_one('.result__a')
            if not link_tag:
                 logger.debug("Skipping result: no link tag")
                 continue
            
            raw_url = link_tag.get('href')
            if not raw_url: continue
            
            clean, domain = self.clean_url(raw_url)
            if not clean:
                logger.debug(f"Skipping result: failed to clean {raw_url}")
                continue

            if not self.is_valid_candidate(clean):
                logger.debug(f"Skipping candidate: {clean} (Domain: {domain})")
                continue
                
            title = link_tag.get_text()
            
            item = {
                "name": title,
                "url": clean,
                "domain": domain,
                "source_query": query,
                "original_url": raw_url
            }
            found.append(item)
            
        return found

    def verify_site(self, url):
        """Head request to verify site is active."""
        try:
            # We use a proper user agent
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            resp = self.session.head(url, headers=headers, timeout=5, allow_redirects=True)
            if resp.status_code < 400:
                return True
            # Fallback to GET if HEAD fails (some servers block HEAD)
            if resp.status_code == 405: # Method Not Allowed
                resp = self.session.get(url, headers=headers, timeout=5, stream=True)
                return resp.status_code < 400
            return False
        except:
            return False

    def run(self):
        all_candidates = {} # Key: Clean URL, Value: Info Dict
        
        # 1. Broad Search
        for city in CITIES:
            for base_q in BASE_QUERIES:
                query = f"{base_q} {city}"
                items = self.search_duckduckgo(query)
                
                for item in items:
                    url = item['url']
                    if url not in all_candidates:
                        all_candidates[url] = item
                    else:
                        # Append source info maybe?
                        pass
                
                # Polite delay
                delay = random.uniform(2, 5)
                time.sleep(delay)
        
        logger.info(f"Found {len(all_candidates)} unique candidates. Verifying...")
        
        # 2. Verify & Filter
        verified_candidates = []
        for url, info in all_candidates.items():
            if self.verify_site(url):
                verified_candidates.append(info)
            else:
                logger.info(f"Discarding dead/inaccessible link: {url}")
        
        return verified_candidates

def main():
    if not NOTION_API_KEY:
        logger.error("NOTION_API_KEY not found in environment.")
        # Proceed with dry run or exit? User implies execution.
        # We will proceed but skip Notion sync
    
    if not NOTION_DATABASE_ID:
        logger.error("NOTION_COMPETITORS_DATABASE_ID not found in environment. Notion sync will list but not write.")

    scanner = MarketScanner()
    notion = NotionSync(NOTION_API_KEY, NOTION_DATABASE_ID)
    
    candidates = scanner.run()
    logger.info(f"Scanned complete. Found {len(candidates)} active competitors.")
    
    # Sync
    for item in candidates:
        # Check existence
        existing = notion.find_entry(item['url'])
        if existing:
            logger.info(f"Skipping existing: {item['name']} ({item['url']})")
        else:
            notion.create_entry(item)
            # Notion rate limit safety
            time.sleep(0.4)

if __name__ == "__main__":
    main()
