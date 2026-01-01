from src.scripts.gsheets_client import GSheetsClient

client = GSheetsClient()
rows = client.get_sheet_data('Sheet1!A1:E500')
if rows:
    print(f"Total rows: {len(rows)}")
    for i, row in enumerate(rows[:20]): # Print first 20 rows
        print(f"Row {i}: {row}")
else:
    print("No data found.")
