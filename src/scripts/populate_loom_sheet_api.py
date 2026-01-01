from src.scripts.gsheets_client import GSheetsClient
import json

def populate_sheet():
    client = GSheetsClient()
    
    # Define headers
    headers = ["Folder Path", "Folder Name", "Video Count", "URL"]
    
    # Define data (33 folders)
    folders = [
      {"path": "Videos > Reels", "name": "Reels", "video_count": 1, "url": "https://www.loom.com/looms/videos/Reels-16b48faa971244c0ae3b46bcd422d3ec"},
      {"path": "Videos > Mighty Photo Booth", "name": "Mighty Photo Booth", "video_count": 12, "url": "https://www.loom.com/looms/videos/Mighty-Photo-Booth-d5d535dfff164731b8a7caae1944659f"},
      {"path": "Videos > Delivery Team", "name": "Delivery Team", "video_count": 52, "url": "https://www.loom.com/looms/videos/Delivery-Team-c616adeb0d974e858a9994af6b786541"},
      {"path": "Videos > Delivery Team > Ring Roamer", "name": "Ring Roamer", "video_count": 2, "url": "https://www.loom.com/looms/videos/Ring-Roamer-ea8ef09053274c659c27df50f1f0e0b5"},
      {"path": "Videos > Delivery Team > Venue Intel", "name": "Venue Intel", "video_count": 1, "url": "https://www.loom.com/looms/videos/Venue-Intel-3f8f1dc9680448758d4d6f51779da3af"},
      {"path": "Videos > Delivery Team > Delivery Team Folder", "name": "Delivery Team Folder", "video_count": 1, "url": "https://www.loom.com/looms/videos/Delivery-Team-Folder-5935da77cb4c4fa0bf6829500b06bd01"},
      {"path": "Videos > Delivery Team > QR Sharing", "name": "QR Sharing", "video_count": 2, "url": "https://www.loom.com/looms/videos/QR-Sharing-d1bb41d4f69743b39cf15c53d1113d1b"},
      {"path": "Videos > Delivery Team > Event Roamer", "name": "Event Roamer", "video_count": 8, "url": "https://www.loom.com/looms/videos/Event-Roamer-22a661dbcf6a4889bbbc935d543dea89"},
      {"path": "Videos > Delivery Team > Props", "name": "Props", "video_count": 5, "url": "https://www.loom.com/looms/videos/Props-d40b643b411a4762bab82c79ae14f699"},
      {"path": "Videos > Delivery Team > Event Review", "name": "Event Review", "video_count": 6, "url": "https://www.loom.com/looms/videos/Event-Review-8c5133c4ea264384ad932191d97d4661"},
      {"path": "Videos > Delivery Team > Backdrops", "name": "Backdrops", "video_count": 2, "url": "https://www.loom.com/looms/videos/Backdrops-4d6658f8473f46d9a98aa80b29f2bad3"},
      {"path": "Videos > Delivery Team > 360 Setup", "name": "360 Setup", "video_count": 3, "url": "https://www.loom.com/looms/videos/360-Setup-f83c1440076c43f5baa182f964f50537"},
      {"path": "Videos > Delivery Team > Sharing Station", "name": "Sharing Station", "video_count": 2, "url": "https://www.loom.com/looms/videos/Sharing-Station-51b978f0dce44dbf9f0cf78e6dd745ac"},
      {"path": "Videos > Delivery Team > Printer Training", "name": "Printer Training", "video_count": 2, "url": "https://www.loom.com/looms/videos/Printer-Training-57e428c1428240208b1bcab863c80f4a"},
      {"path": "Videos > Delivery Team > Photo Booth Breakdown", "name": "Photo Booth Breakdown", "video_count": 5, "url": "https://www.loom.com/looms/videos/Photo-Booth-Breakdown-20923e4ca17f4ff08b98166c3a070eb0"},
      {"path": "Videos > Delivery Team > Photo Booth Setup", "name": "Photo Booth Setup", "video_count": 13, "url": "https://www.loom.com/looms/videos/Photo-Booth-Setup-b8dc955902bb441188e1531ef2727ec5"},
      {"path": "Videos > Back-Office Team", "name": "Back-Office Team", "video_count": 127, "url": "https://www.loom.com/looms/videos/Back-Office-Team-747b836e4bb3485a8c9b1a817f0f4938"},
      {"path": "Videos > Back-Office Team > Feedbacks & Suggestions", "name": "Feedbacks & Suggestions", "video_count": 3, "url": "https://www.loom.com/looms/videos/Feedbacks-and-Suggestions-a80e0c9fb4ca4925b2c3ce693e010481"},
      {"path": "Videos > Back-Office Team > Concept - Presentation", "name": "Concept - Presentation", "video_count": 2, "url": "https://www.loom.com/looms/videos/Concept-Presentation-85627211cba44c399e21afa6408b7348"},
      {"path": "Videos > Back-Office Team > Clean Up", "name": "Clean Up", "video_count": 2, "url": "https://www.loom.com/looms/videos/Clean-Up-b5a9bc3dbaf34acfb5b93bc2de34bd23"},
      {"path": "Videos > Back-Office Team > Graphic Design", "name": "Graphic Design", "video_count": 9, "url": "https://www.loom.com/looms/videos/Graphic-Design-2ece16abb8a3491b876c7d3b461e0e40"},
      {"path": "Videos > Back-Office Team > Interviews", "name": "Interviews", "video_count": 1, "url": "https://www.loom.com/looms/videos/Interviews-93a731957c464cf39f0d4777b9f4ea3e"},
      {"path": "Videos > Back-Office Team > Sales Trainings", "name": "Sales Trainings", "video_count": 15, "url": "https://www.loom.com/looms/videos/Sales-Trainings-9db2eba9b1634be0b3defee9be17312c"},
      {"path": "Videos > Back-Office Team > EA Tasks", "name": "EA Tasks", "video_count": 15, "url": "https://www.loom.com/looms/videos/EA-Tasks-822008cb85b4408eb28c82b9fe0f2848"},
      {"path": "Videos > Back-Office Team > Daily Loom", "name": "Daily Loom", "video_count": 28, "url": "https://www.loom.com/looms/videos/Daily-Loom-5bfbf264ff9f48ecb256b211f1d9a584"},
      {"path": "Videos > Back-Office Team > Tool Training", "name": "Tool Training", "video_count": 18, "url": "https://www.loom.com/looms/videos/Tool-Training-be701d9f70724bb2870b01af9fbb2a9c"},
      {"path": "Videos > Back-Office Team > Website", "name": "Website", "video_count": 1, "url": "https://www.loom.com/looms/videos/Website-7856a0d9aeca491680fce570dca9229e"},
      {"path": "Videos > Back-Office Team > Misc Tasks", "name": "Misc Tasks", "video_count": 8, "url": "https://www.loom.com/looms/videos/Misc-Tasks-4e359a753f704875ae5a48dfc1efabe3"},
      {"path": "Videos > Back-Office Team > All about Notion", "name": "All about Notion", "video_count": 10, "url": "https://www.loom.com/looms/videos/All-about-Notion-992d06b2f91745dfb4ca0a32e5715f65"},
      {"path": "Videos > Back-Office Team > Snappic", "name": "Snappic", "video_count": 15, "url": "https://www.loom.com/looms/videos/Snappic-3b4774fc6bcd44edbaffd0ed96b280fc"},
      {"path": "Videos > Andrew Stuffs", "name": "Andrew Stuffs", "video_count": 11, "url": "https://www.loom.com/looms/videos/Andrew-Stuffs-dfd8bda1d46e405a9c64917364a97a79"},
      {"path": "Videos > Andrew Stuffs > Collaboration", "name": "Collaboration", "video_count": 1, "url": "https://www.loom.com/looms/videos/Collaboration-79f845d97dac4119b697558da5dd53c4"},
      {"path": "Videos > Andrew Stuffs > Eyes", "name": "Eyes", "video_count": 4, "url": "https://www.loom.com/looms/videos/Eyes-d49ab7454ec44e17be953357b10f565c"}
    ]
    
    # Transform to list of lists
    values = [headers]
    for folder in folders:
        values.append([
            folder["path"],
            folder["name"],
            folder["video_count"],
            folder["url"]
        ])
    
    print(f"Updating sheet with {len(values)} rows (including header)...")
    
    # Clear content effectively by updating from A1 with new content
    # The GSheetsClient.update_rows uses 'user entered' option, which is good.
    # We will simply overwrite.
    result = client.update_rows(values, 'Sheet1!A1')
    
    if result:
        print("Successfully updated sheet.")
    else:
        print("Failed to update sheet.")

if __name__ == "__main__":
    populate_sheet()
