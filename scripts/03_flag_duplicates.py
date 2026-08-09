"""
Creates two versions of the cleaned FAERS dataset based on the FAERS-native
'duplicate' self-flag:
  1. full     -- all records retained, with the duplicate flag preserved
                 (plus an explicit boolean is_potential_duplicate column)
  2. deduped  -- records where duplicate == '1' (FAERS-flagged potential
                 duplicates) excluded

Reads interim/faers_missing_handled.pkl, writes:
  interim/faers_full_with_duplicate_flag.pkl
  interim/faers_deduplicated.pkl

Usage:
    python scripts/03_flag_duplicates.py
"""

from pathlib import Path

import pandas as pd

INPUT_PATH = Path(__file__).resolve().parent.parent / "interim" / "faers_missing_handled.pkl"
FULL_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "interim" / "faers_full_with_duplicate_flag.pkl"
DEDUPED_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "interim" / "faers_deduplicated.pkl"

DUPLICATE_FLAG_VALUE = "1"


def load_input() -> pd.DataFrame:
    return pd.read_pickle(INPUT_PATH)


def build_full_version(df: pd.DataFrame) -> pd.DataFrame:
    full = df.copy()
    full["is_potential_duplicate"] = full["duplicate"] == DUPLICATE_FLAG_VALUE
    return full


def build_deduped_version(full: pd.DataFrame) -> pd.DataFrame:
    return full.loc[~full["is_potential_duplicate"]].drop(columns=["is_potential_duplicate"])


def main():
    df = load_input()

    full = build_full_version(df)
    deduped = build_deduped_version(full)

    n_flagged = int(full["is_potential_duplicate"].sum())

    print(f"Full dataset (duplicate flag preserved): {len(full)} records")
    print(f"  of which flagged as potential duplicates (duplicate == '1'): {n_flagged}")
    print(f"Deduplicated dataset (flagged duplicates excluded): {len(deduped)} records")

    FULL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    full.to_pickle(FULL_OUTPUT_PATH)
    deduped.to_pickle(DEDUPED_OUTPUT_PATH)

    print(f"\nSaved full version to {FULL_OUTPUT_PATH}")
    print(f"Saved deduplicated version to {DEDUPED_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
