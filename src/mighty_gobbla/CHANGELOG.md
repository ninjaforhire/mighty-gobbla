# Changelog

## [1.0.0] - 2025-12-31

### Added
- **Unified Gobble Interface**: Combined "Single File" and "Folder" processing into a single, streamlined dashboard.
- **Enhanced Duplicate Detection**: Advanced logic to detect duplicate Notion entries based on Date, Store, and Amount (including Tax variations).
- **Conditional History Logging**: History entries are now only created *after* successful integration with Notion (if enabled).
- **Settings Toggle**: specific "Gobble to Notion?" toggle in the UI.

### Changed
- **Renaming Logic**: Local files are processed and renamed in-place.
- **Removed Drag & Drop**: Removed browser-based upload to focus on robust local file system operations (fixing security limitations regarding file renaming).
- **UI Update**: Renamed "Settings" to "Cooking Settings 🧑‍🍳" and updated visual layout.
- **Version Bump**: Official release 1.0.

### Fixed
- **Notion Schema Alignment**: Corrected property names ("Amount" -> "Subtotal", "Billing Date" -> "Date Paid") to match the actual Notion database schema.
- **History Sync**: Fixed issue where rejected duplicates were still being logged to history.
