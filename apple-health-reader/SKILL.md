---
name: apple-health-reader
description: Parse and analyze Apple Health export data (HealthKit XML export). Use when the user shares an Apple Health export ZIP/XML and wants daily aggregates (steps, heart rate, sleep, calories, weight) merged into a local JSON database with a Markdown report.
---

# Apple Health Reader

Parses and analyzes Apple Health data from a HealthKit export.

## What This Skill Does

1. **Parses the Apple Health export** (both formats: full `export.xml` and clinical `export_cda.xml`)
2. **Aggregates data by day** (steps, heart rate, sleep, calories, weight, height)
3. **Saves to a local database** (`health_data.json`) for versioning and analysis
4. **Merges new imports** with existing data (never overwrites)
5. **Generates Markdown reports** for easy viewing

## Usage

### 1. Export data from iPhone

On iPhone:

1. Health app → Profile (icon in the bottom right)
2. Tap "Export Health Data"
3. Choose "All Data"
4. Send the ZIP archive to the chat

### 2. Process the archive

The archive contains two folders:

- `apple_health_export/export.xml` — **full data** (718k+ records, ~227 MB)
- `apple_health_export/export_cda.xml` — clinical report (heart rate/weight/height only, ~344 MB)

**Use the full export** (`export.xml`) — it contains everything.

### 3. Parsing

Run the script:

```bash
python parse_apple_health_full.py /path/to/export.xml
```

Or interactively:

```bash
python parse_apple_health_full.py
```

The script will:

- Parse the records
- Aggregate them by day
- Merge with the existing database
- Save to `health_data.json` and `health_data.md`

## Technical Details

### Dependencies

**No dependencies required.** Only Python's built-in libraries are used:

- `xml.etree.ElementTree` — XML parsing
- `json` — data storage
- `pathlib` — path handling
- `datetime` — date handling
- `collections` — data aggregation

## Data Format

**Output format (JSON):**

```json
{
  "2026-04-18": {
    "steps": 1961,
    "heart_rate": {
      "min": 50,
      "max": 117,
      "avg": 77.5
    },
    "sleep_hours": 7.9,
    "calories": 200.0,
    "weight": null,
    "height": null,
    "bmi": null
  }
}
```

## Security

- ✅ Data stored locally
- ✅ No external servers
- ✅ Versioned via JSON
- ✅ Merging prevents data loss
