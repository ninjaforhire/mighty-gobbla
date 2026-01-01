import json
import os
from src.scripts.gsheets_client import GSheetsClient

def flush_data():
    client = GSheetsClient()
    
    # Load scraped data
    scraped_data = {}
    
    files = ['scraped_batch_1.json', 'scraped_batch_2.json', 'scraped_batch_3.json', 'scraped_batch_4.json']
    for f in files:
        if os.path.exists(f):
            print(f"Loading {f}...")
            try:
                with open(f, 'r', encoding='utf-8') as json_file:
                    batch = json.load(json_file)
                    # batch is a list of objects {folder_url: ..., videos: [...]}
                    # OR a dict {url: [videos]} depending on how previous tools output it.
                    # Looking at write_to_file calls:
                    # Batch 1 was list of objects: [{"folder_url": "...", "videos": [...]}]
                    # Batch 2 was list of objects as well.
                    
                    if isinstance(batch, list):
                        for item in batch:
                            scraped_data[item['folder_url']] = item['videos']
                    elif isinstance(batch, dict):
                        scraped_data.update(batch)
            except Exception as e:
                print(f"Error loading {f}: {e}")

    print(f"Loaded data for {len(scraped_data)} folders.")

    # Read current sheet
    print("Reading current sheet data...")
    current_rows = client.get_sheet_data('Sheet1!A:Z')
    if not current_rows:
        print("No data found in sheet.")
        return

    new_rows = []
    
    # Process rows
    for row in current_rows:
        new_rows.append(row)
        
        # Check if this row is a folder we have data for
        # Assuming URL is in 4th column (index 3)
        if len(row) > 3:
            url = row[3]
            if url in scraped_data:
                videos = scraped_data[url]
                print(f"Found match for {url}: {len(videos)} videos")
                
                # Check current indentation/path to create video rows
                # Folder Path is row[0], Folder Name is row[1]
                folder_path = row[0] if len(row) > 0 else ""
                
                for video in videos:
                    # Create a row for the video
                    # Schema: [Path, Video Name, "", Video URL]
                    # We might want to indent or mark it.
                    # Based on user request: "Insert new entries... under the appropriate folder"
                    
                    # Try to handle title format
                    title = video.get('title') or video.get('Title') or "Untitled"
                    vid_url = video.get('url') or video.get('URL') or ""
                    
                    video_row = [
                        folder_path, # Keep same path context
                        f"  ↳ {title}", # Indent name slightly for visibility
                        "", # No video count
                        vid_url
                    ]
                    new_rows.append(video_row)

    # Write back
    print(f"Writing {len(new_rows)} rows to sheet...")
    client.clear_sheet('Sheet1!A:Z')
    client.update_rows(new_rows, 'Sheet1!A:Z')
    print("Done.")

if __name__ == "__main__":
    flush_data()
