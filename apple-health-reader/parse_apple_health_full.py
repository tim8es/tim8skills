#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse Apple Health export.xml (full HealthKit data).
Saves aggregated daily data to JSON and markdown.
"""

import sys
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def parse_health_xml(xml_path):
    """Parse Apple Health export XML file."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        return root
    except Exception as e:
        print("ERROR parsing XML: {}".format(e))
        sys.exit(1)


def format_date(date_str):
    """Convert Apple Health date format (YYYY-MM-DD HH:MM:SS) to YYYY-MM-DD."""
    if not date_str:
        return None
    
    # Take first 10 chars (YYYY-MM-DD)
    return date_str[:10]


def aggregate_by_date(root):
    """Aggregate health records by date."""
    daily_data = defaultdict(lambda: {
        'steps': 0,
        'heart_rate': {'min': None, 'max': None, 'values': []},
        'sleep_hours': 0,
        'calories': 0,
        'weight': None,
        'height': None,
        'bmi': None,
    })

    # Find all Record elements
    records = root.findall('.//Record')
    print("Found {} records".format(len(records)))
    
    for record in records:
        try:
            record_type = record.get('type', '')
            value = record.get('value')
            start_date = record.get('startDate', '')
            end_date = record.get('endDate', '')
            
            if not start_date:
                continue
            
            # Format date to YYYY-MM-DD
            date_str = format_date(start_date)
            if not date_str:
                continue
            
            # Parse based on type
            if 'StepCount' in record_type and value:
                try:
                    daily_data[date_str]['steps'] += int(float(value))
                except (ValueError, TypeError):
                    pass
            
            elif 'HeartRate' in record_type and value:
                try:
                    hr_value = float(value)
                    daily_data[date_str]['heart_rate']['values'].append(hr_value)
                except (ValueError, TypeError):
                    pass
            
            elif 'ActiveEnergyBurned' in record_type and value:
                try:
                    daily_data[date_str]['calories'] += float(value)
                except (ValueError, TypeError):
                    pass
            
            elif 'BodyMass' in record_type and value:
                try:
                    daily_data[date_str]['weight'] = float(value)
                except (ValueError, TypeError):
                    pass
            
            elif 'Height' in record_type and value:
                try:
                    daily_data[date_str]['height'] = float(value)
                except (ValueError, TypeError):
                    pass
            
            elif 'BodyMassIndex' in record_type and value:
                try:
                    daily_data[date_str]['bmi'] = float(value)
                except (ValueError, TypeError):
                    pass
        
        except Exception:
            continue
    
    # Parse sleep from SleepAnalysis
    sleep_records = root.findall('.//Record[@type="HKCategoryTypeIdentifierSleepAnalysis"]')
    for record in sleep_records:
        try:
            start_date = record.get('startDate', '')
            end_date = record.get('endDate', '')
            
            if start_date and end_date:
                date_str = format_date(start_date)
                if date_str:
                    try:
                        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        sleep_duration = (end - start).total_seconds() / 3600
                        daily_data[date_str]['sleep_hours'] += sleep_duration
                    except (ValueError, TypeError):
                        pass
        except Exception:
            continue
    
    # Calculate heart rate stats
    for date_str in daily_data:
        hr_values = daily_data[date_str]['heart_rate']['values']
        if hr_values:
            daily_data[date_str]['heart_rate']['min'] = min(hr_values)
            daily_data[date_str]['heart_rate']['max'] = max(hr_values)
            daily_data[date_str]['heart_rate']['avg'] = sum(hr_values) / len(hr_values)
        del daily_data[date_str]['heart_rate']['values']
    
    return dict(daily_data)


def format_for_wiki(daily_data):
    """Format aggregated data for wiki storage."""
    if not daily_data:
        return "No health data found."
    
    # Sort by date
    sorted_dates = sorted(daily_data.keys(), reverse=True)
    
    # Generate markdown table for recent 30 days
    table_rows = []
    for date_str in sorted_dates[:30]:
        data = daily_data[date_str]
        steps = data.get('steps', 0)
        hr = data.get('heart_rate', {})
        hr_avg = "{:.0f}".format(hr.get('avg', 0)) if hr.get('avg') else "—"
        sleep = "{:.1f}h".format(data.get('sleep_hours', 0)) if data.get('sleep_hours') else "—"
        calories = "{:.0f}".format(data.get('calories', 0)) if data.get('calories') else "—"
        weight = "{:.1f}kg".format(data.get('weight', 0)) if data.get('weight') else "—"
        
        table_rows.append("| {} | {} | {} | {} | {} | {} |".format(date_str, steps, hr_avg, sleep, calories, weight))
    
    table = """| Date | Steps | HR Avg | Sleep | Calories | Weight |
|------|-------|--------|-------|----------|--------|
""" + "\n".join(table_rows)
    
    # JSON data block
    json_data = json.dumps(daily_data, indent=2, ensure_ascii=False)
    
    content = """# Health Data

Last updated: {}

Total days: {}

## Recent 30 Days

{}

## Raw Data

```json
{}
```
""".format(datetime.now().isoformat(), len(daily_data), table, json_data)
    return content


def main():
    if len(sys.argv) < 2:
        xml_path = input("Enter path to Apple Health export XML: ").strip()
    else:
        xml_path = sys.argv[1]
    
    xml_path = Path(xml_path)
    if not xml_path.exists():
        print("ERROR: File not found: {}".format(xml_path))
        sys.exit(1)
    
    # Load existing data for merging
    script_dir = Path(__file__).parent
    json_path = script_dir / "health_data.json"
    existing_data = {}
    if json_path.exists():
        try:
            existing_data = json.loads(json_path.read_text(encoding='utf-8'))
            print("[INFO] Loaded {} existing days for merging".format(len(existing_data)))
        except Exception as e:
            print("[WARN] Could not load existing data: {}".format(e))

    print("Parsing {}...".format(xml_path.name))
    root = parse_health_xml(str(xml_path))
    print("[OK] XML loaded")
    
    print("Aggregating by date...")
    new_data = aggregate_by_date(root)
    print("[OK] Parsed {} days from XML".format(len(new_data)))
    
    # Merge data
    merged_data = existing_data.copy()
    for date, metrics in new_data.items():
        if date in merged_data:
            # Update metrics (new overwrites old for the same date)
            merged_data[date].update(metrics)
        else:
            merged_data[date] = metrics
    
    print("[OK] Merged into {} total days".format(len(merged_data)))
    
    print("Formatting for wiki...")
    wiki_content = format_for_wiki(merged_data)
    
    # Save to skill directory
    output_path = script_dir / "health_data.md"
    output_path.write_text(wiki_content, encoding='utf-8')
    print("[OK] Saved to {}".format(output_path))
    
    # Save raw JSON
    json_path.write_text(json.dumps(merged_data, indent=2, ensure_ascii=False), encoding='utf-8')
    print("[OK] Saved JSON to {}".format(json_path))
    
    print("\n[DONE] Health database updated. Total days: {}".format(len(merged_data)))


if __name__ == '__main__':
    main()
