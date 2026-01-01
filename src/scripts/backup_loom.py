import asyncio
import os
import json
from src.scripts.gsheets_client import GSheetsClient
from src.scripts.loom_scraper import scrape_folder

# Define column indices (assuming standard layout from populate_loom_sheet_api.py)
# Headers: ["Folder Path", "Folder Name", "Video Count", "URL"]
COL_FOLDER_PATH = 0
COL_NAME = 1
COL_COUNT = 2
COL_URL = 3

async def backup_loom():
    client = GSheetsClient()
    # Read wider range to get URL (Col D)
    rows = client.get_sheet_data('Sheet1!A:Z')
    
    if not rows:
        print("No data found in sheet.")
        return

    headers = rows[0]
    data_rows = rows[1:]
    
    output_rows = [headers]
    
    print(f"Processing {len(data_rows)} rows...")
    
    for i, row in enumerate(data_rows):
        # Ensure row has enough columns
        while len(row) < 4:
            row.append("")
            
        folder_path = row[COL_FOLDER_PATH]
        name = row[COL_NAME]
        url = row[COL_URL]
        
        # Add the folder row itself
        output_rows.append(row)
        
        if not url:
            continue

        # Check if this is a Loom folder URL
        if "loom.com/share/folder" in url or "loom.com/looms/videos" in url:
            print(f"Scraping folder: {name} ({url})")
            
            # Scrape
            try:
                videos = await scrape_folder(url)
                
                for video in videos:
                    # Construct video row
                    # Format: [Folder Path, Video Title, "Video", Video URL]
                    video_row = [
                        folder_path,          # Folder Path (Matching parent)
                        video['title'],       # Name (Title)
                        "Video",              # Video Count (Used as Type marker)
                        video['url']          # URL
                    ]
                    output_rows.append(video_row)
                    
            except Exception as e:
                print(f"Failed to scrape {name}: {e}")
                
    # Write backup locally first
    with open(".tmp/loom_backup_data.json", "w") as f:
        json.dump(output_rows, f, indent=2)
        
    print("Writing to Google Sheet...")
    # Clear and update
    client.clear_sheet()
    client.update_rows(output_rows, 'Sheet1!A:Z')
    print("Done!")

if __name__ == "__main__":
    asyncio.run(backup_loom())
