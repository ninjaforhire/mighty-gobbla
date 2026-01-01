---
description: Sync caller information from Quo (OpenPhone) to Notion Clients database
---

## Tool
**Script:** `src/scripts/sync_quo_to_notion.py`
**Usage:** Automatically adds or updates client records in Notion based on incoming call webhooks from Quo.

## Security & Authentication
- **Quo Webhook**: All incoming requests MUST be verified using HMAC-SHA256.
    - **Header**: `openphone-signature-hash`
    - **Secret**: `OPENPHONE_WEBHOOK_SECRET`
- **Notion API**:
    - **Header**: `Authorization: Bearer <NOTION_API_KEY>`
    - **Version**: `2022-06-28`

## Input Schema (Quo Webhook)
The payload must contain these minimum fields or the sync will be skipped:
```json
{
  "data": {
    "object": {
      "direction": "incoming" | "outgoing",
      "from": "+E164_NUMBER",
      "to": "+E164_NUMBER",
      "status": "completed" | "missed" | "voicemail"
    }
  }
}
```

## Data Hierarchy & Conflict Resolution
**Rule:** Notion is the ultimate source of truth.
1. **Existing Property**: Never overwrite a non-empty Notion property with data from Quo.
2. **Missing Property**: Only fill a Notion property if it is currently empty.
3. **Phone Number**: Always use the phone number from the call payload as the unique identifier for search.

## Process

1.  **Parse & Verify**
    - Validate the HMAC signature using `OPENPHONE_WEBHOOK_SECRET`.
    - **Identify Event**: Determine if it's a call or a message.
    - **Extract Participants**: For group messages, extract all phone numbers from the `participants` array. 
    - **Extract Transcript**: For calls, look for transcription text in the call object or associated media.

2.  **Enrich Data (Quo API)**
    - For each identified phone number, query `/v1/contacts`.
    - **Strict Match**: Only use details if the API record explicitly includes the searched phone number.
    - Extract: Name, Company, Email, Role, and **Tags** (from customFields).

3.  **Sync to Notion (Multi-Participant)**
    - Search Notion database by `Phone` for *each* participant.
    
    **Scenario A: Record Found**
    - Update `Last Call` timestamp.
    - Append interaction log to page content.
    - **Group Context**: For group texts, explicitly list all participants in the entry.
    - **Transcript**: Append call transcription if available.
    - **Tags Sync**: Merge tags from Quo into Notion's "Tags" multi-select. Existing tags in Notion are preserved.
    - Fill missing properties ONLY if empty in Notion.
    
    **Scenario B: No Record Found**
    - Create new page with `Status: New Import`.
    - Populate all available fields from Quo (including Tags).
    - Append initial interaction/transcript to page content.

## Output
Return a JSON object:
```json
{
  "status": "success",
  "action": "created" | "updated" | "skipped",
  "notion_page_id": "...",
  "client_name": "..."
}
```

## Error & Rate Limit SOPs
1. **Rate Limits (429)**: If Notion or Quo returns a 429, the script should wait (exponential backoff) and retry up to 3 times before failing.
2. **Notion Validation (400)**: Log the specific property that failed validation. Do not stop the entire sync if one optional field (like Company) fails; skip that field and proceed.
3. **Database Access (404/403)**: Log critical failure and notify via `.tmp/critical_errors.log`.

## Logging Standards
- All logs must be written to standard output for the `webhook_receiver` to capture.
- Critical errors must also be appended to `.tmp/sync_errors.log`.

## Verification Plan
After making changes, run:
1. `Get-Content .tmp/mock_quo_payload.json | python src/scripts/sync_quo_to_notion.py`
2. Verify in Notion that a new record appeared or the existing one was updated without overwriting your manual notes.
3. Check `.tmp/sync_errors.log` for any warnings.
