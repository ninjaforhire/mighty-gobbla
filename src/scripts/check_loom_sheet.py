from src.scripts.gsheets_client import GSheetsClient
import json

def check_sheet():
    client = GSheetsClient()
    # Assuming "Sheet1" and columns A, B, C as per directive (Title, Category, URL)
    data = client.get_sheet_data('Sheet1!A:C')
    print(f"Total rows in sheet: {len(data)}")
    if len(data) > 1:
        print("First few rows:")
        for row in data[:5]:
            print(row)
    
    # Check if there's a "Loom" or "Video" related header
    headers = data[0] if data else []
    print(f"Headers: {headers}")

if __name__ == '__main__':
    check_sheet()
