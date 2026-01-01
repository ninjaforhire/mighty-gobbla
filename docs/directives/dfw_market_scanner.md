# Tool 1: DFW Market Scanner

## 1. Objective

Identify every unique photo booth rental company operating in the Dallas-Fort Worth (DFW) Metroplex. Create a clean list of unique domain URLs and basic business metadata to be used as the trigger for Tool 2.

## 2. Search Strategy (The "Wide Net")

**Directive:** "Perform a deep-crawl search using multiple search operators to identify photo booth rental businesses. Use the following geographic modifiers: Dallas, Fort Worth, Arlington, Plano, Irving, Frisco, McKinney, Grapevine, and 'DFW Metroplex'."

### Primary Search Queries
* `"photo booth rental" + [City Name]`
* `"360 photo booth" + [City Name]`
* `"luxury photo booth Dallas"`
* `"wedding photo booth rentals DFW"`

### Source Priority
1.  Google Search results (Organic).
2.  Google Maps / Local Pack listings.
3.  Directories: The Knot, WeddingWire, and Yelp (extract company names and website links only).

## 3. Extraction & Deduplication Logic

**Directive:** "From every search result found, extract the following data points. If a company appears multiple times, merge the records into a single unique entry based on the Website URL."

### Fields to Extract
* `Business Name`
* `Website URL` (Clean the URL: remove `utm` parameters and ensure it starts with `https://`)
* `Source Location` (Which city or directory it was found in)
* `Google Rating` (If available via search snippet)

## 4. Verification Filtering

**Directive:** "Perform a 'sanity check' on discovered URLs. If a URL leads to a dead link, a domain parking page, or a generic marketplace (like Amazon or Etsy), discard it. Only keep domains that appear to be dedicated business websites."

## 5. Integration with Notion (DFW COMPETITORS)

**Output Directive:** "Format the final verified list into a table. For each entry, check the **DFW COMPETITORS** Notion database. If the Website URL does not exist, create a new record with the Title as [Business Name] and the Website property as [URL]. Set the 'Status' property to 'Discovered - Awaiting Deep Scan'."

### Required Notion Properties
1. **Name** (Title)
2. **Website** (URL)
3. **Status** (Select: Discovered, Audited, Deep Scanned)
4. **Source** (Text - e.g., "Google Maps", "The Knot")

## 6. Future Scope: Directory Enrichment
While the primary scanner filters out directory sites (The Knot, Yelp) to find direct business URLs, these platforms contain valuable metadata (pricing, reviews, feature lists).
*   **Future Tool**: A specific "Directory Scraper" should be built to revisit these ignored domains.
*   **Goal**: Extract metadata and append it to the existing competitor records in Notion.

## 7. Execution
Run via `src/scripts/dfw_market_scanner.py`.
Ensure `NOTION_API_KEY` and `NOTION_COMPETITORS_DATABASE_ID` are set in `.env`.
