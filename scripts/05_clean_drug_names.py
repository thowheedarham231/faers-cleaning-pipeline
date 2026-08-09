"""
Standardises patient.drug[].medicinalproduct casing (uppercase, strip
whitespace) to collapse exact-match casing/whitespace variants (e.g.
'Covid-19 Vaccine' vs 'COVID-19 VACCINE').

Does NOT attempt fuzzy matching between genuinely distinct product name
variants (e.g. 'PFIZER-BIONTECH COVID-19 VACCINE' vs 'PFIZER/BIONTECH' vs
'COVID-19 VACCINE') -- those remain distinct values, since collapsing them
requires a brand/NDC lookup, not string normalization.

Applies to both dataset versions produced by 04_clean_sex.py:
  interim/faers_full_sex_cleaned.pkl         -> interim/faers_full_drug_cleaned.pkl
  interim/faers_deduplicated_sex_cleaned.pkl -> interim/faers_deduplicated_drug_cleaned.pkl

Usage:
    python scripts/05_clean_drug_names.py
"""

import copy
from pathlib import Path

import pandas as pd

INTERIM_DIR = Path(__file__).resolve().parent.parent / "interim"

INPUT_OUTPUT_PAIRS = [
    (INTERIM_DIR / "faers_full_sex_cleaned.pkl", INTERIM_DIR / "faers_full_drug_cleaned.pkl"),
    (INTERIM_DIR / "faers_deduplicated_sex_cleaned.pkl", INTERIM_DIR / "faers_deduplicated_drug_cleaned.pkl"),
]


def extract_names(drug_col: pd.Series) -> pd.Series:
    return pd.Series(
        [
            d.get("medicinalproduct")
            for entries in drug_col
            if isinstance(entries, list)
            for d in entries
        ]
    )


def find_casing_groups(names: pd.Series) -> dict:
    """Maps normalized (upper+stripped) name -> sorted list of raw variants, for
    groups with more than one raw spelling/casing variant."""
    names = names.dropna()
    normalized = names.str.strip().str.upper()
    variants_per_group = names.groupby(normalized).unique()
    return {
        norm: sorted(variants)
        for norm, variants in variants_per_group.items()
        if len(variants) > 1
    }


def clean_drug_entry(entry: dict) -> dict:
    entry = copy.deepcopy(entry)
    name = entry.get("medicinalproduct")
    if isinstance(name, str):
        entry["medicinalproduct"] = name.strip().upper()
    return entry


def clean_drug_column(drug_col: pd.Series) -> pd.Series:
    return drug_col.apply(
        lambda entries: [clean_drug_entry(d) for d in entries] if isinstance(entries, list) else entries
    )


def show_before_after_sample(before_groups: dict, cleaned_names: pd.Series, max_groups: int = 6):
    print(f"  found {len(before_groups)} casing/whitespace groups before cleaning:")
    for norm_name, variants in list(before_groups.items())[:max_groups]:
        cleaned_count = int((cleaned_names == norm_name).sum())
        print(f"    before: {variants}")
        print(f"    after:  '{norm_name}' ({cleaned_count} entries)\n")


def main():
    for input_path, output_path in INPUT_OUTPUT_PAIRS:
        df = pd.read_pickle(input_path)
        print(f"Processing {input_path.name} ({len(df)} records)")

        before_names = extract_names(df["patient.drug"])
        before_groups = find_casing_groups(before_names)

        df["patient.drug"] = clean_drug_column(df["patient.drug"])
        after_names = extract_names(df["patient.drug"])

        show_before_after_sample(before_groups, after_names)

        print(f"  unique raw names before: {before_names.dropna().nunique()}")
        print(f"  unique names after:      {after_names.dropna().nunique()}")

        df.to_pickle(output_path)
        print(f"  saved to {output_path}\n")


if __name__ == "__main__":
    main()
