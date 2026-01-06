# Snappic Help Scraper

## Goal
Scrape "Updates" and "Changelog" articles from [help.snappic.com](https://help.snappic.com) and sync them to a Notion database.

## Prerequisites
- `NOTION_API_KEY`: Must be set in `.env`.
- `NOTION_SNAPPIC_DATABASE_ID`: (Optional) The target database ID. If not set, the script will search for a database named 'Snappic' or 'Updates'.

## Usage
Run the script using Python:

```bash
python src/scripts/scrape_snappic_help.py
```

## Behavior
1.  **Discovery**: Scrapes the "Updates" and "New Features" collections on help.snappic.com.
2.  **Processing**: Fetches each article's content.
3.  **Sync**: 
    - Checks if the article URL already exists in the target Notion database.
    - If new, creates a page with the Title, URL, and a snippet of the content.

## Troubleshooting
- **Notion 400 Errors**: Usually mean the database schema doesn't match the script (script expects properties 'Name' (title) and 'URL' (url)).
- **No Database Found**: Ensure a database with 'Snappic' in the title exists and the integration has access to it.
