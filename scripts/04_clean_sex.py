"""
Recodes patient.patientsex from FAERS numeric codes {1, 2} to readable
labels {'Male', 'Female'}, filling missing values as 'Unknown' rather than
dropping those rows.

Applies to both dataset versions produced by 03_flag_duplicates.py:
  interim/faers_full_with_duplicate_flag.pkl -> interim/faers_full_sex_cleaned.pkl
  interim/faers_deduplicated.pkl             -> interim/faers_deduplicated_sex_cleaned.pkl

Usage:
    python scripts/04_clean_sex.py
"""

from pathlib import Path

import pandas as pd

INTERIM_DIR = Path(__file__).resolve().parent.parent / "interim"

SEX_CODE_MAP = {
    "1": "Male",
    "2": "Female",
}
UNKNOWN_LABEL = "Unknown"

INPUT_OUTPUT_PAIRS = [
    (INTERIM_DIR / "faers_full_with_duplicate_flag.pkl", INTERIM_DIR / "faers_full_sex_cleaned.pkl"),
    (INTERIM_DIR / "faers_deduplicated.pkl", INTERIM_DIR / "faers_deduplicated_sex_cleaned.pkl"),
]


def clean_sex_column(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    n_missing_before = int(df["patient.patientsex"].isna().sum())

    df["patient.patientsex"] = (
        df["patient.patientsex"]
        .astype(str)
        .map(SEX_CODE_MAP)
        .fillna(UNKNOWN_LABEL)
    )

    print(f"  rows missing before recode: {n_missing_before} -> filled as '{UNKNOWN_LABEL}'")
    print(f"  value counts after recode:\n{df['patient.patientsex'].value_counts().to_string()}")
    return df


def main():
    for input_path, output_path in INPUT_OUTPUT_PAIRS:
        print(f"Processing {input_path.name} ({len(pd.read_pickle(input_path))} records)")
        df = pd.read_pickle(input_path)
        df = clean_sex_column(df)
        df.to_pickle(output_path)
        print(f"  saved to {output_path}\n")


if __name__ == "__main__":
    main()
