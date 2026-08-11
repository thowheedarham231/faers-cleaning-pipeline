"""
Pulls raw adverse event reports from the openFDA FAERS API with genuine
coverage across all of 2023.

A single receivedate:[20230101 TO 20231231] query paginated via skip
returns results sorted by receivedate ascending, so taking the first
~5,000 records that way only covers the first few days of January. To get
real coverage across the year, this queries month-by-month instead: one
API call per calendar month, each requesting ~420 records (5000 / 12),
for a combined total spanning all 12 months.

Usage:
    python scripts/01_pull_data.py
"""

import calendar
import json
import time
from pathlib import Path

import requests

API_URL = "https://api.fda.gov/drug/event.json"
YEAR = 2023
RECORDS_PER_MONTH = 420  # ~5000 / 12 months
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_BACKOFF_SECONDS = 5
REQUEST_PAUSE_SECONDS = 0.5

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "raw" / "faers_raw.json"


def month_windows(year: int) -> list:
    windows = []
    for month in range(1, 13):
        last_day = calendar.monthrange(year, month)[1]
        start = f"{year}{month:02d}01"
        end = f"{year}{month:02d}{last_day:02d}"
        windows.append((month, start, end))
    return windows


def fetch_month(search_query: str, limit: int) -> dict:
    params = {
        "search": search_query,
        "limit": limit,
        "skip": 0,
    }
    last_error = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            response = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            print(f"  request failed (attempt {attempt}/{RETRY_COUNT}): {exc}")
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_BACKOFF_SECONDS)
    raise RuntimeError(f"Failed to fetch '{search_query}' after {RETRY_COUNT} attempts") from last_error


def pull_records() -> tuple:
    records = []
    month_summaries = []

    for month, start, end in month_windows(YEAR):
        search_query = f"receivedate:[{start} TO {end}]"
        print(f"Fetching {calendar.month_name[month]} {YEAR} ({search_query}), limit={RECORDS_PER_MONTH}")
        payload = fetch_month(search_query, RECORDS_PER_MONTH)
        month_results = payload.get("results", [])

        if not month_results:
            print("  no results returned for this month")
            month_summaries.append((month, 0, None, None))
            time.sleep(REQUEST_PAUSE_SECONDS)
            continue

        receivedates = [r["receivedate"] for r in month_results if r.get("receivedate")]
        actual_min = min(receivedates) if receivedates else None
        actual_max = max(receivedates) if receivedates else None

        records.extend(month_results)
        month_summaries.append((month, len(month_results), actual_min, actual_max))
        time.sleep(REQUEST_PAUSE_SECONDS)

    return records, month_summaries


def main():
    records, month_summaries = pull_records()

    print(f"\nCollected {len(records)} raw records total\n")
    print("Actual date range collected per month:")
    for month, count, actual_min, actual_max in month_summaries:
        label = calendar.month_name[month]
        if count:
            print(f"  {label:>10}: {count:4d} records, receivedate {actual_min} to {actual_max}")
        else:
            print(f"  {label:>10}: {count:4d} records")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    print(f"\nSaved raw JSON to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
