# Sweep Loom Directive

This directive outlines the process for scanning the Loom video library and synchronization of the folder structure and video details to the designated Google Sheet.

## Overview

The `sweep loom` command is used to ensure the Google Sheet is up to date with the latest Loom video library state. It identifies new videos, assigns them to categories based on their Loom folder, and marks them for Notion import.

## Triggering the Sweep

The command is triggered manually by the user or an agent by saying:
- `sweep loom`
- `sweep the loom library`

## Process Flow

1. **Extraction**:
   - The system fetches all videos and folders from Loom.
   - It recursive-scans all subfolders to reconstruct the hierarchy.
   - It captures: Video Title, Category (Parent Folder Name), and Video URL.

2. **Deduplication**:
   - The system reads the existing Google Sheet ([Loom Master Sheet](https://docs.google.com/spreadsheets/d/1nikwHHkeeaikq_CdIrRZKYqBfj4cW_mgitO_9WUlGXM/edit)).
   - It compares the Loom URL list against the Sheet's URL column.

3. **Sync**:
   - New videos are appended to the sheet.
   - Existing video categories are updated if the folder has changed in Loom.
   - A column "Notion Import Status" is set to `Pending` for all new additions.

4. **Reporting**:
   - The system reports the total number of videos found (Target: 281).
   - It lists how many new videos were added.

## Tools to Use

- `src/scripts/sweep_loom_orchestrator.py`: The main execution script.
- `src/scripts/loom_client.py`: Handles Loom data retrieval.
- `src/scripts/gsheets_client.py`: Handles Google Sheet updates.

## Expected Accuracy

- Every single video must be accounted for.
- Total count should match the workspace count (currently 281).
- No duplicates based on the Video URL.
