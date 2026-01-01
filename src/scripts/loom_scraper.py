import asyncio
from playwright.async_api import async_playwright
import time
import re

async def scrape_folder(url):
    """
    Scrapes a Loom folder for video titles and URLs.
    """
    # Convert private/internal URL to public share folder URL if needed
    # Format: https://www.loom.com/looms/videos/Name-ID
    # Target: https://www.loom.com/share/folder/ID
    
    if "looms/videos" in url:
        # Extract ID (32 hex chars at the end)
        match = re.search(r'([a-f0-9]{32})$', url)
        if match:
            loom_id = match.group(1)
            url = f"https://www.loom.com/share/folder/{loom_id}"
            print(f"Converted ID to public URL: {url}")
    
    print(f"Scraping folder: {url}")
    videos = []
    
    async with async_playwright() as p:
        # Launch with specific user agent AND stealth args
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Hardcoded cookies (extracted from valid session)
        cookie_string = "loom_anon_comment=0a86898f154c434680eba4dd98ffc0ed; ajs_anonymous_id=%2280338d60-0a3a-4151-8b56-e4b3f267016c%22; loom_referral_video=09b1aa507cb846138847bf8e98b56a71; _otPreferencesSynced=; _mkto_trk=id:594-ATC-127&token:_mch-loom.com-e1ee9e7342de371ad0366ba8d664b13a; atlCohort={\"bucketAll\":{\"bucketedAtUTC\":\"2025-12-29T18:06:23.079Z\",\"version\":\"2\",\"index\":34,\"bucketId\":0}}; _gcl_au=1.1.83730036.1767031584; _fs_sample_user=true; atl_xid.ts=1767031584946; atl_xid.current=%5B%7B%22type%22%3A%22xc%22%2C%22value%22%3A%226ec6c53e-7419-4a91-ae3c-456161606a11%22%2C%22createdAt%22%3A%222025-12-29T18%3A06%3A24.938Z%22%7D%5D; _rdt_uuid=1767031587180.9d656a5b-f175-4389-9470-2bee3b253b0e; _ga=GA1.1.99912645.1767031587; _fbp=fb.1.1767031587907.337935983869267733; _tt_enable_cookie=1; _ttp=01KDNMMHP5ARDHZZ6WZJ2DC39R_.tt.1; _uetsid=19322c30e4e111f0a1c9572f066c1d62; _uetvid=19323ec0e4e111f0857fa1cdefa3107c; _clck=obbwfl%5E2%5Eg29%5E0%5E2189; __hstc=185935670.58ad5369d44ee01906cf87305372e9b8.1767031593181.1767031593181.1767031593181.1; hubspotutk=58ad5369d44ee01906cf87305372e9b8; __hssrc=1; ttcsid=1767031588553::9ayc8fQchjZcoLwULyG5.1.1767031598571.0; ttcsid_CGUEF63C77U3HDTUG46G=1767031588552::dJ5oW4HEc7bEhn-6cima.1.1767031598572.1; loom_anon_id=80338d60-0a3a-4151-8b56-e4b3f267016c; loom_app_source=website; loom_anon_id=; loom_anon_comment=; loom_anon_comment_name=; ajs_user_id=30927302; __stripe_mid=e23a2575-a752-46f5-bdc6-5d41e28451e8b18267; OptanonConsent=isGpcEnabled=0&datestamp=Mon+Dec+29+2025+12%3A47%3A43+GMT-0600+(Central+Standard+Time)&version=202503.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=b8ba4565-045c-4aac-b812-47f2f60c7a43&interactionCount=1&isAnonUser=1&landingPath=https%3A%2F%2Fwww.loom.com%2F&groups=1%3A1%2C2%3A1%2C3%3A1%2CBG36%3A1%2C4%3A1; _ga_H93TGDH6MB=GS2.1.s1767034063$o2$g0$t1767034063$j60$l0$h0; _clsk=1udd58b%5E1767034063705%5E1%5E1%5Ei.clarity.ms%2Fcollect; __stripe_sid=00e2795e-b02b-43fd-9135-1153a5b039f828750a; ajs_anonymous_id=80338d60-0a3a-4151-8b56-e4b3f267016c; _dd_s=aid=5a212cb5-1b73-4daa-a4af-24fa18f588a9&logs=1&id=54657981-5393-49fa-b645-7678b6cce04a&created=1767031577598&expire=1767044498847&rum=0"
        
        cookies = []
        for pair in cookie_string.split(';'):
            if '=' in pair:
                name, value = pair.strip().split('=', 1)
                cookies.append({'name': name, 'value': value, 'domain': '.loom.com', 'path': '/'})

        # Create context with user agent and viewport AND COOKIES
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        await context.add_cookies(cookies)
        
        page = await context.new_page()
        
        try:
            await page.goto(url, timeout=60000)
            # await page.wait_for_load_state('networkidle') # Sometimes flaky
            print("Page loaded, waiting for dynamic content...")
            await page.wait_for_timeout(5000)
            
            # Debug: Start
            title = await page.title()
            current_url = page.url
            print(f"Page title: {title}")
            print(f"Current URL: {current_url}")
            # Debug: End

            # Handle infinite scroll
            last_height = await page.evaluate("document.body.scrollHeight")
            while True:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000) # Wait for load
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Loom structure often has links in <a> tags with specific classes or structure
            # We'll look for generic video links first. Logic might need tuning based on actual DOM.
            # Assuming grid of videos.
            
            # Extract video elements using verified selectors from browser subagent
            # Container: article[class*="video-card_videoCard"]
            # Link: a[class*="video-card_videoCardLink"]
            # Title: h3
            
            links = await page.evaluate("""() => {
                const containers = document.querySelectorAll('article[class*="video-card_videoCard"]');
                return Array.from(containers).map(c => {
                    const link = c.querySelector('a[class*="video-card_videoCardLink"]');
                    const titleEl = c.querySelector('h3');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : "Untitled",
                        url: link ? link.href : ""
                    };
                });
            }""")
            
            # Fallback for old layout if new one fails (optional, but good for robustness)
            if not links:
                 print("New selectors failed, trying legacy fallback...")
                 links = await page.evaluate("""() => {
                    const anchors = Array.from(document.querySelectorAll('a[href^="/share/"], a[href^="https://www.loom.com/share/"]'));
                    return anchors.map(a => ({
                        title: a.textContent.trim() || a.getAttribute('aria-label') || "Untitled",
                        url: a.href
                    }));
                }""")
            
            if not links:
                print("STILL 0 videos found. Dumping debug info...")
                await page.screenshot(path=".tmp/debug_scraper.png")
                content = await page.content()
                with open(".tmp/debug_scraper.html", "w", encoding="utf-8") as f:
                    f.write(content)


            # Deduplicate by URL
            seen_urls = set()
            for link in links:
                if link['url'] not in seen_urls:
                    # Clean up URL to standard share format if needed
                    # Loom often has https://www.loom.com/share/ID
                    clean_url = link['url'].split('?')[0] # Remove query params
                    
                    # Improve title extraction if it captured garbage
                    title = link['title']
                    if not title:
                         title = "Untitled Video"
                         
                    videos.append({'title': title, 'url': clean_url})
                    seen_urls.add(link['url'])
            
            print(f"Found {len(videos)} videos in {url}")
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
        finally:
            await browser.close()
            
    return videos

if __name__ == "__main__":
    # Test run
    test_url = "https://www.loom.com/looms/videos/Printer-Training-57e428c1428240208b1bcab863c80f4a" 
    asyncio.run(scrape_folder(test_url))
