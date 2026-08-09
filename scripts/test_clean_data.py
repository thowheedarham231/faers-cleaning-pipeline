"""
Data-quality tests for the cleaned FAERS pipeline outputs (post 05_clean_drug_names.py).

Runs against both dataset versions:
  interim/faers_full_drug_cleaned.pkl
  interim/faers_deduplicated_drug_cleaned.pkl

Usage:
    pytest scripts/test_clean_data.py -v
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

INTERIM_DIR = Path(__file__).resolve().parent.parent / "interim"

DATASET_PATHS = [
    INTERIM_DIR / "faers_full_drug_cleaned.pkl",
    INTERIM_DIR / "faers_deduplicated_drug_cleaned.pkl",
]

VALID_SEX_VALUES = {"Male", "Female", "Unknown"}
VALID_YEAR = 2023


def extract_drug_names(drug_col: pd.Series) -> pd.Series:
    return pd.Series(
        [
            entry.get("medicinalproduct")
            for entries in drug_col
            if isinstance(entries, list)
            for entry in entries
        ]
    )


@pytest.fixture(params=DATASET_PATHS, ids=lambda p: p.stem)
def df(request):
    path = request.param
    if not path.exists():
        pytest.skip(f"{path} not found -- run scripts 01-05 first")
    return pd.read_pickle(path)


def test_no_nulls_in_safetyreportid(df):
    assert df["safetyreportid"].notna().all(), "found null safetyreportid values"


def test_no_duplicate_safetyreportid(df):
    dupes = df["safetyreportid"][df["safetyreportid"].duplicated()]
    assert dupes.empty, f"found duplicate safetyreportid values: {sorted(dupes.unique())[:10]}"


def test_no_nulls_in_cleaned_drug_name_field(df):
    names = extract_drug_names(df["patient.drug"])
    assert not names.empty, "no drug name entries found"
    missing = names.isna() | (names.astype(str).str.strip() == "")
    assert not missing.any(), f"{missing.sum()} drug entries have a null/empty medicinalproduct"


def test_receivedate_all_valid_2023_dates(df):
    assert df["receivedate"].notna().all(), "found null receivedate values"

    bad_values = []
    for value in df["receivedate"]:
        try:
            parsed = datetime.strptime(str(value), "%Y%m%d")
        except ValueError:
            bad_values.append(value)
            continue
        if parsed.year != VALID_YEAR:
            bad_values.append(value)

    assert not bad_values, f"found receivedate values that aren't valid {VALID_YEAR} dates: {bad_values[:10]}"


def test_patientsex_only_expected_values(df):
    actual_values = set(df["patient.patientsex"].unique())
    unexpected = actual_values - VALID_SEX_VALUES
    assert not unexpected, f"found unexpected patient.patientsex values: {unexpected}"
