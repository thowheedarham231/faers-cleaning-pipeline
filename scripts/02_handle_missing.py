"""
Drops high-missingness columns from the flattened FAERS raw data and flags
signal loss on columns that are retained despite sparse coverage.

Reads raw/faers_raw.json, writes interim/faers_missing_handled.pkl for
downstream pipeline steps (pickled to preserve nested list/dict columns
like patient.drug and patient.reaction).

Usage:
    python scripts/02_handle_missing.py
"""

import json
from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).resolve().parent.parent / "raw" / "faers_raw.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "interim" / "faers_missing_handled.pkl"

MISSING_THRESHOLD = 0.90

# reportduplicate is inconsistently shaped across records (dict on some,
# list of dicts on others, absent on most), so it fragments into these
# three columns when flattened. None of the three individually clears the
# 90% threshold (~88-89% each), but together they represent one low-signal
# duplicate-tracking field, so all three are dropped explicitly.
EXPLICIT_DROP_COLUMNS = [
    "reportduplicate",
    "reportduplicate.duplicatesource",
    "reportduplicate.duplicatenumb",
]

# Kept despite high missingness -- flagged, not dropped.
FLAG_COLUMNS = [
    "patient.patientweight",
    "patient.patientagegroup",
    "patient.summary",
]


def load_raw() -> list:
    with open(RAW_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_frame(records: list) -> pd.DataFrame:
    df = pd.json_normalize(records, max_level=1)
    df = df.replace("", pd.NA)
    return df


def drop_high_missingness(df: pd.DataFrame) -> pd.DataFrame:
    missing_frac = df.isna().mean()

    over_threshold = set(missing_frac[missing_frac > MISSING_THRESHOLD].index)
    explicit = set(EXPLICIT_DROP_COLUMNS) & set(df.columns)
    to_drop = sorted(over_threshold | explicit)

    print("Columns dropped:")
    for col in to_drop:
        reason = (
            f"> {MISSING_THRESHOLD*100:.0f}% missing"
            if col in over_threshold
            else "explicit (reportduplicate group, ~88-89% missing individually)"
        )
        print(f"  {col}: {missing_frac[col]*100:.2f}% missing [{reason}]")

    return df.drop(columns=to_drop)


def flag_sparse_columns(df: pd.DataFrame):
    print("\nRetained columns with significant missingness (flagged, not dropped):")
    for col in FLAG_COLUMNS:
        if col not in df.columns:
            continue
        n_present = int(df[col].notna().sum())
        n_missing = len(df) - n_present
        pct_missing = n_missing / len(df) * 100
        print(
            f"  {col}: {pct_missing:.2f}% missing "
            f"({n_present} of {len(df)} records carry a value; "
            f"any analysis keyed on this field loses signal on the other "
            f"{n_missing} records)"
        )


def main():
    records = load_raw()
    df = build_frame(records)

    n_cols_before = df.shape[1]
    print(f"Column count before: {n_cols_before}")

    df = drop_high_missingness(df)

    n_cols_after = df.shape[1]
    print(f"\nColumn count after: {n_cols_after} (dropped {n_cols_before - n_cols_after})")

    flag_sparse_columns(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(OUTPUT_PATH)
    print(f"\nSaved column-pruned frame to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
