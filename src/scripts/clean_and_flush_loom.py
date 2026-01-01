import json
import os
import sys
# Ensure src module is found
sys.path.append(os.getcwd())
from src.scripts.gsheets_client import GSheetsClient

def clean_and_flush():
    client = GSheetsClient()
    
    # 1. Load UNIQUE scraped data
    # We will use a dictionary: folder_url -> {set of unique video URLs}
    # Then map back to video objects to keep titles.
    
    unique_videos_map = {} # folder_url -> { video_url -> video_obj }
    
    files = ['scraped_batch_1.json', 'scraped_batch_2.json', 'scraped_batch_3.json', 'scraped_batch_4.json', 'scraped_batch_5.json', 'scraped_recovery_1.json', 'scraped_recovery_2.json']
    
    print("Loading scraped data...")
    for f in files:
        if os.path.exists(f):
            try:
                with open(f, 'r', encoding='utf-8') as json_file:
                    batch = json.load(json_file)
                    
                    # CASE 1: List (Standard Batches)
                    if isinstance(batch, list):
                        for item in batch:
                            f_url = item.get('folder_url')
                            if not f_url: continue
                            
                            if f_url not in unique_videos_map:
                                unique_videos_map[f_url] = {}
                                
                            videos = item.get('videos', [])
                            for v in videos:
                                v_url = v.get('url') or v.get('URL')
                                if v_url:
                                    unique_videos_map[f_url][v_url] = v

                    # CASE 2: Dict (Recovery Files)
                    elif isinstance(batch, dict):
                        # Recursive helper to extract videos from nested structure
                        def extract_from_node(node, parent_url=None):
                            # If node has 'url' and 'videos' (list), it's a folder container
                            if isinstance(node, dict):
                                current_url = node.get('url')
                                
                                # Determine the target URL for these videos.
                                # If this folder IS NOT the root parent (has a parent_url passed down),
                                # we might want to merge it into the parent if we suspect it doesn't have its own row.
                                # For EA Tasks/Tool Training subfolders, we want to merge into the top-level parent.
                                # Logic: If parent_url is set, use it. Otherwise use current_url.
                                target_url = parent_url if parent_url else current_url
                                
                                # Check for direct video list
                                if 'videos' in node and isinstance(node['videos'], list):
                                    if target_url:
                                        if target_url not in unique_videos_map: unique_videos_map[target_url] = {}
                                        
                                        # Determine if we need to prefix the title (if we are merging into a parent)
                                        # We merge if target_url != current_url (meaning we are in a subfolder using parent's slot)
                                        is_merged = (target_url != current_url) and current_url
                                        prefix = f"{node.get('name', 'Subfolder')}: " if is_merged else ""
                                        
                                        for v in node['videos']:
                                            v_url = v.get('url') or v.get('URL')
                                            if v_url: 
                                                # Clone v to avoid mutating original if reused (unlikely)
                                                v_copy = v.copy()
                                                if prefix:
                                                    v_copy['title'] = prefix + v_copy.get('title', 'Untitled')
                                                unique_videos_map[target_url][v_url] = v_copy
                                
                                # Check for keys that look like URLs (Daily Loom style)
                                for k, v in node.items():
                                    if isinstance(k, str) and "loom.com" in k and isinstance(v, dict):
                                        f_url = k
                                        if f_url not in unique_videos_map: unique_videos_map[f_url] = {}
                                        for vid in v.get('videos', []):
                                            v_url = vid.get('url') or vid.get('URL')
                                            if v_url: unique_videos_map[f_url][v_url] = vid
                                    
                                    # Recurse into values
                                    # For EA Tasks/Tool Training, the 'subfolders' list contains dicts.
                                    # We want to pass the current_url (if it's a root) as parent_url to children.
                                    # If we are already in a subfolder (parent_url is set), we keep passing the SAME parent_url.
                                    # so all descendants go to the Top Root.
                                    if k in ['subfolders', 'nested_folders'] and isinstance(v, list):
                                        next_parent = parent_url if parent_url else current_url
                                        extract_from_node(v, next_parent)
                                    elif isinstance(v, (dict, list)) and k not in ['videos']: # Don't recurse into video objects
                                        # For other keys like "EA Tasks" (top level), we recurse but verify if they have URL
                                        # If "EA Tasks" has a URL, valid.
                                        extract_from_node(v, parent_url) # Pass current parent_url context if any (usually None at top)
                            
                            elif isinstance(node, list):
                                for item in node:
                                    extract_from_node(item, parent_url)

                        extract_from_node(batch)
                                    
            except Exception as e:
                print(f"Error loading {f}: {e}")

    print(f"Loaded data for {len(unique_videos_map)} folders.")

    # 2. Read current sheet to get the skeleton (Folders)
    print("Reading current sheet structure...")
    current_rows = client.get_sheet_data('Sheet1!A:Z')
    if not current_rows:
        print("No data found in sheet.")
        return

    clean_rows = []
    
    # Identify Folder Rows
    # A folder row usually has a URL in col D (index 3) that matches a folder URL (contains /looms/videos/ or /share/folder/)
    # And crucially, it does NOT have "↳" in the Name column (index 1).
    
    for row in current_rows:
        if not row: continue
        
        # Check if it's a folder row
        is_folder = False
        
        # Simplest check: Column A is Path, Column B is Name.
        # If Column B does NOT start with '  ↳ ' and Col D is present.
        name_col = row[1] if len(row) > 1 else ""
        url_col = row[3] if len(row) > 3 else ""
        
        # Heuristic: If it has a "Video Count" in col C (index 2), it's a folder row from the original populate script.
        # Or if the name doesn't start with the indent.
        if "Video Count" in row: # Header row
            clean_rows.append(row)
            continue
            
        is_indented = name_col.strip().startswith('↳') or '↳' in name_col
        
        if not is_indented and url_col:
            # It's a folder row! Keep it.
            clean_rows.append(row)
            
            # Now, if we have scraped data for this folder, insert the UNIQUE videos immediately after.
            if url_col in unique_videos_map:
                videos_dict = unique_videos_map[url_col]
                # Sort videos by title for tidiness
                sorted_videos = sorted(videos_dict.values(), key=lambda x: (x.get('title') or x.get('Title') or "").lower())
                
                print(f"  Adding {len(sorted_videos)} videos for {name_col}")
                
                folder_path = row[0] if len(row) > 0 else ""
                
                for vid in sorted_videos:
                    title_raw = vid.get('title') or vid.get('Title')
                    v_url = vid.get('url') or vid.get('URL') or ""
                    
                    if not title_raw or title_raw == "Untitled":
                        # Try to prettify from URL
                        # Format: .../share/some-title-slug-ID
                        if "/share/" in v_url:
                            try:
                                slug = v_url.split("/share/")[-1]
                                # Slug is usually name-of-video-id
                                # We can split by - and try to drop the last ID part if it looks like a hash or ID
                                parts = slug.split('-')
                                if len(parts) > 1 and len(parts[-1]) > 8: # likely an ID
                                    clean_parts = parts[:-1]
                                else:
                                    clean_parts = parts
                                title = ' '.join(clean_parts).title()
                            except:
                                title = "Untitled Video"
                        else:
                             title = "Untitled Video"
                    else:
                        title = title_raw
                    
                    # Create clean video row
                    video_row = [
                        folder_path,
                        f"  ↳ {title}",
                        "", # No count
                        v_url
                    ]
                    clean_rows.append(video_row)
            else:
                 pass
                 # print(f"  No scraped videos found for {name_col} ({url_col})")

    # 3. Write back the clean list
    print(f"Writing {len(clean_rows)} clean rows to sheet...")
    client.clear_sheet('Sheet1!A:Z')
    client.update_rows(clean_rows, 'Sheet1!A:Z')
    print("Cleanup Complete!")

if __name__ == "__main__":
    clean_and_flush()
