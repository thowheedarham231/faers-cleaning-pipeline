"""
Produces the final, flat, CSV-ready versions of the cleaned FAERS dataset --
one row per report (not per drug/reaction).

patient.drug and patient.reaction are list-of-dict columns (one entry per
drug / per reaction on a report); flattening them to one-row-per-entry would
multiply report rows and break the row counts already documented in
decision_log.md. Instead each is collapsed into a single semicolon-separated
string per report:
  patient.drug     -> drug_names      (medicinalproduct values)
  patient.reaction -> reaction_names  (reactionmeddrapt values)

patient.summary is a single-key dict ({'narrativeincludeclinical': ...}) and
is flattened to a plain text column (patient_summary_narrative) since CSV
can't hold a dict value -- this isn't something the user asked for
explicitly, but every other column is already a CSV-safe scalar, so this is
the only remaining blocker to a valid flat CSV.

Reads interim/faers_full_drug_cleaned.pkl and
interim/faers_deduplicated_drug_cleaned.pkl, writes:
  clean/faers_full_clean.csv
  clean/faers_deduplicated_clean.csv

Usage:
    python scripts/06_finalize_clean.py
"""

from pathlib import Path

import pandas as pd

INTERIM_DIR = Path(__file__).resolve().parent.parent / "interim"
CLEAN_DIR = Path(__file__).resolve().parent.parent / "clean"

JOIN_SEP = "; "

INPUT_OUTPUT_PAIRS = [
    (INTERIM_DIR / "faers_full_drug_cleaned.pkl", CLEAN_DIR / "faers_full_clean.csv"),
    (INTERIM_DIR / "faers_deduplicated_drug_cleaned.pkl", CLEAN_DIR / "faers_deduplicated_clean.csv"),
]


def join_field(entries, key: str) -> str:
    if not isinstance(entries, list):
        return ""
    values = [str(d[key]) for d in entries if d.get(key) not in (None, "")]
    return JOIN_SEP.join(values)


def flatten(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["drug_names"] = df["patient.drug"].apply(lambda v: join_field(v, "medicinalproduct"))
    df["reaction_names"] = df["patient.reaction"].apply(lambda v: join_field(v, "reactionmeddrapt"))
    df["patient_summary_narrative"] = df["patient.summary"].apply(
        lambda v: v.get("narrativeincludeclinical") if isinstance(v, dict) else pd.NA
    )

    return df.drop(columns=["patient.drug", "patient.reaction", "patient.summary"])


def main():
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    for input_path, output_path in INPUT_OUTPUT_PAIRS:
        df = pd.read_pickle(input_path)
        n_rows_before = len(df)

        flat = flatten(df)

        assert len(flat) == n_rows_before, "row count changed during flattening"

        flat.to_csv(output_path, index=False)

        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"{output_path.name}: {len(flat)} rows, {flat.shape[1]} columns, {size_mb:.2f} MB")
        print(f"  columns: {list(flat.columns)}\n")


if __name__ == "__main__":
    main()
