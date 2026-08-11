"""
Explodes drug_names (a JOIN_SEP-joined string of medicinalproduct values, see
06_finalize_clean.py) into one row per drug mention, keeping the report-level
identifying/context columns alongside each exploded drug.

Reads clean/faers_full_clean.csv, writes:
  clean/faers_2023_drug_level.csv

Usage:
    python scripts/07_drug_level_export.py
"""

from pathlib import Path

import pandas as pd

CLEAN_DIR = Path(__file__).resolve().parent.parent / "clean"
INPUT_PATH = CLEAN_DIR / "faers_full_clean.csv"
OUTPUT_PATH = CLEAN_DIR / "faers_2023_drug_level.csv"

JOIN_SEP = "; "

REPORT_COLUMNS = [
    "safetyreportid",
    "receivedate",
    "occurcountry",
    "serious",
    "is_potential_duplicate",
]


def explode_drug_names(df: pd.DataFrame) -> pd.DataFrame:
    exploded = df[REPORT_COLUMNS + ["drug_names"]].copy()
    exploded["drug_names"] = exploded["drug_names"].str.split(JOIN_SEP)
    exploded = exploded.explode("drug_names", ignore_index=True)
    exploded = exploded.rename(columns={"drug_names": "drug_name"})
    exploded = exploded[exploded["drug_name"].notna() & (exploded["drug_name"] != "")]
    return exploded


def main():
    df = pd.read_csv(INPUT_PATH)
    n_reports = len(df)

    drug_level = explode_drug_names(df)
    n_drug_rows = len(drug_level)

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    drug_level.to_csv(OUTPUT_PATH, index=False)

    print(f"Original reports: {n_reports}")
    print(f"Drug-mention rows: {n_drug_rows}")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
