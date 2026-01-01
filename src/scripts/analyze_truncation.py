import json
import os

def analyze_counts():
    files = ['scraped_batch_1.json', 'scraped_batch_2.json', 'scraped_batch_3.json', 'scraped_batch_4.json']
    truncated_folders = []
    
    total_videos = 0
    
    for f in files:
        if os.path.exists(f):
            try:
                with open(f, 'r', encoding='utf-8') as json_file:
                    batch = json.load(json_file)
                    print(f"--- {f} ---")
                    for item in batch:
                        url = item.get('folder_url')
                        videos = item.get('videos', [])
                        count = len(videos)
                        total_videos += count
                        name = url.split('/')[-1] if url else "Unknown"
                        
                        print(f"{count:4d} vids | {name}")
                        
                        if count >= 10:
                            truncated_folders.append(url)
            except Exception as e:
                print(f"Error {f}: {e}")

    print(f"\nTotal Videos Found: {total_videos}")
    print(f"Folders hitting limit (>=10): {len(truncated_folders)}")
    for tf in truncated_folders:
        print(f"RE-SCRAPE: {tf}")

if __name__ == "__main__":
    analyze_counts()
