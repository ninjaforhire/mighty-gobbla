# Loom Backup Directive

This directive outlines the process for backing up the Loom video library to a Google Sheet.

## Overview
The goal is to crawl specific Loom folders listed in a Google Sheet and insert the videos found within them as new rows in that same sheet.

## Triggers
- Manual request: "Backup Loom library"
- Periodic maintenance.

## Process Flow
1. **Read Sheet**: The system reads the [Master Sheet](https://docs.google.com/spreadsheets/d/1nikwHHkeeaikq_CdIrRZKYqBfj4cW_mgitO_9WUlGXM).
2. **Identify Folders**: It looks for rows containing Loom folder URLs.
3. **Scrape**: It uses a headless browser (Playwright) to visit each folder, scroll to the bottom, and extract all video titles and URLs.
4. **Update Sheet**: It rewrites the sheet, inserting the found videos immediately below their parent folder row.

## Tools
- `src/scripts/backup_loom.py`: The main orchestrator.
- `src/scripts/loom_scraper.py`: The scraping logic.
- `src/scripts/gsheets_client.py`: Google Sheets interaction.

## Troubleshooting
- **Playwright Errors**: 
    - Ensure `pip install playwright` and `playwright install chromium` are run.
    - If timeouts occur, check internet connection or increase timeout in `loom_scraper.py`.
- **Sheet Errors**:
    - Ensure `credentials.json` is valid.
    - If "Quota exceeded", wait a minute and retry.
