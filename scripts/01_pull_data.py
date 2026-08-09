"""
Pulls raw adverse event reports from the openFDA FAERS API for a fixed
receivedate window and dumps them to disk with no transformation.

Usage:
    python scripts/01_pull_data.py
"""

import json
import time
from pathlib import Path

import requests

API_URL = "https://api.fda.gov/drug/event.json"
SEARCH_QUERY = "receivedate:[20230101 TO 20231231]"
PAGE_LIMIT = 100          # openFDA max records per request
TARGET_RECORD_COUNT = 5000
MAX_SKIP = 25000          # openFDA hard limit on skip + limit
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_BACKOFF_SECONDS = 5
REQUEST_PAUSE_SECONDS = 0.5

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "raw" / "faers_raw.json"


def fetch_page(skip: int) -> dict:
    params = {
        "search": SEARCH_QUERY,
        "limit": PAGE_LIMIT,
        "skip": skip,
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
    raise RuntimeError(f"Failed to fetch skip={skip} after {RETRY_COUNT} attempts") from last_error


def pull_records() -> list:
    records = []
    skip = 0

    while len(records) < TARGET_RECORD_COUNT and skip <= MAX_SKIP:
        print(f"Fetching skip={skip}, limit={PAGE_LIMIT} ({len(records)}/{TARGET_RECORD_COUNT} collected)")
        payload = fetch_page(skip)
        page_results = payload.get("results", [])

        if not page_results:
            print("  no more results returned, stopping pagination")
            break

        records.extend(page_results)
        skip += PAGE_LIMIT
        time.sleep(REQUEST_PAUSE_SECONDS)

    return records[:TARGET_RECORD_COUNT]


def main():
    records = pull_records()
    print(f"Collected {len(records)} raw records")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    print(f"Saved raw JSON to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
