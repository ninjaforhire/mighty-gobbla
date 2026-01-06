# Snappic Integration Directive

## Goal
Interact with Snappic (Photo Booth Software) to [User to define: e.g., download media, sync events, etc.].

## Context
Snappic does not appear to have public API documentation.
Authentication is likely via:
1.  **Hidden API**: Usage of `X-Api-Key` or similar if discovered.
2.  **Browser Identity**: Logging in via web and scraping/automating.

## Inputs
- Snappic Credentials (Email/Password) OR API Key
- target_event_id (if applicable)

## Approaches

### Option A: Browser Automation (Recommended if no API key)
Use the browser tool to:
1.  Navigate to `https://www.snappic.com/login` (or equivalent).
2.  Log in.
3.  Navigate to the specific event/media page.
4.  Scrape data or perform actions.

### Option B: Private API
If an API Key is provided:
1.  Base URL: Likely `https://api.snappic.com` or similar (needs verification).
2.  Headers: `X-Api-Key: <key>`
3.  Endpoints: Need to be discovered or provided.

## Next Steps
1.  [ ] Determine specific user goal (Download media? Create event?).
2.  [ ] specific method of authentication.
3.  [ ] Create `src/scripts/snappic_tool.py`.
