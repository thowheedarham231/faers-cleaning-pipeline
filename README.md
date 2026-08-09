# FAERS Cleaning Pipeline

A cleaning pipeline that takes raw FDA Adverse Event Reporting System
(FAERS) data — deeply nested JSON, inconsistent field shapes, heavy
missingness — and turns it into two flat, analysis-ready CSVs.

## The problem

FAERS is the FDA's database of adverse event reports submitted by
manufacturers, healthcare professionals, and consumers. The raw records
returned by the openFDA API are nested JSON: some fields are missing
entirely, some appear as a single dict on one record and a list of dicts
on another (`reportduplicate`), and each report can carry an arbitrary
number of drugs and reactions as list-of-dict sub-fields
(`patient.drug`, `patient.reaction`). None of that is usable directly in
a flat table, and naively flattening it (e.g. one row per drug) would
silently multiply the report-level row count. This pipeline structures
the raw data into a form suitable for tabular analysis while documenting
every judgment call made along the way.

## Data source

- **Source:** [openFDA Drug Adverse Event API](https://api.fda.gov/drug/event.json)
- **Query window:** `receivedate` between 2023-01-01 and 2023-12-31
- **Volume:** 5,000 reports (`scripts/01_pull_data.py`), paginated 100 records at a time
- **Raw output:** `raw/faers_raw.json` (gitignored — regenerate by rerunning the pull)

## Pipeline stages

| Script | Stage | What it does |
|---|---|---|
| `01_pull_data.py` | Pull | Fetches raw JSON reports from the openFDA API, no transformation |
| `02_profile_raw_data.py` | Profile | Flattens top level and reports per-column missingness to inform the drop threshold |
| `02_handle_missing.py` | Missing data | `pd.json_normalize`s the raw JSON (40 columns) and drops columns over 90% missing, or explicitly grouped as one fragmented low-signal field (35 columns) |
| `03_flag_duplicates.py` | Duplicates | Preserves FAERS's self-flagged `duplicate` field; produces **full** and **deduplicated** variants |
| `04_clean_sex.py` | Patient sex | Recodes FAERS numeric codes to `Male` / `Female` / `Unknown` |
| `05_clean_drug_names.py` | Drug names | Standardises `medicinalproduct` casing/whitespace (`strip().upper()`) |
| `06_finalize_clean.py` | Flatten & export | Collapses `patient.drug` / `patient.reaction` to semicolon-separated strings, one row per report; exports final CSVs |

Each stage's reasoning — not just what it did, but why, and what
alternatives were rejected — is written up in
[`decision_log.md`](decision_log.md).

## Before / after

| Stage | Rows | Columns |
|---|---|---|
| Raw (flattened top level) | 5,000 | 40 |
| After missing-data drop (`02_handle_missing.py`) | 5,000 | 35 |
| Final — full (`clean/faers_full_clean.csv`) | 5,000 | 36 |
| Final — deduplicated (`clean/faers_deduplicated_clean.csv`) | 3,878 | 35 |

(Full gains a column relative to the 35-column post-missingness frame
because `is_potential_duplicate` is added; deduplicated drops that same
column again since, once filtered, it's constant and no longer informative.)

## Two key judgment calls

**1. The duplicate-flag split.** FAERS reports carry their own
`duplicate` self-flag, separate from `safetyreportid` uniqueness (all
5,000 IDs are already unique). 1,122 of 5,000 records (22.4%) are
self-flagged as potential duplicates of another report. Rather than
unilaterally deciding whether to drop them, the pipeline produces both
variants and pushes that decision to whoever uses the output — see
[Final outputs](#final-outputs-in-clean) below.

**2. The drug-name fuzzy-matching limitation.** `medicinalproduct` had
2,205 unique raw values. Six groups were exact-match casing/whitespace
variants of each other (e.g. `'COVID-19 VACCINE'` vs `'Covid-19
Vaccine'`) and were safely collapsed via `strip().upper()`. Genuinely
distinct name variants that likely refer to the same underlying product
— e.g. `'PFIZER-BIONTECH COVID-19 VACCINE'` vs `'PFIZER/BIONTECH'` vs
`'COVID-19 VACCINE'` — were deliberately **not** merged. Collapsing
those correctly requires a real drug ontology or NDC/brand-name lookup;
naive string similarity risks silently merging genuinely different
drugs. That normalization belongs in a dedicated step with a real
reference dataset, not bundled into casing cleanup.

## Flattening nested drug/reaction fields

`patient.drug` and `patient.reaction` are list-of-dict columns — one
entry per drug or reaction on a report. Flattening to one row per entry
would multiply report rows and break the row counts above. Instead,
`06_finalize_clean.py` collapses each into a single semicolon-separated
string per report:

- `patient.drug` → `drug_names` (`medicinalproduct` values)
- `patient.reaction` → `reaction_names` (`reactionmeddrapt` values)

`patient.summary` (a single-key dict) is similarly flattened to a plain
text column, `patient_summary_narrative`, since CSV can't hold a dict
value.

## Final outputs (in `clean/`)

| File | Rows | Use when... |
|---|---|---|
| `faers_full_clean.csv` | 5,000 | You need every report retained — completeness/audit work, or you want to apply your own duplicate-handling logic using the `is_potential_duplicate` column |
| `faers_deduplicated_clean.csv` | 3,878 | You want FAERS-flagged potential duplicates excluded up front — e.g. signal detection work, where inflated counts from duplicate reports would bias results |

## Running the pipeline from scratch

```bash
pip install -r requirements.txt

python scripts/01_pull_data.py           # -> raw/faers_raw.json
python scripts/02_handle_missing.py      # -> interim/faers_missing_handled.pkl
python scripts/03_flag_duplicates.py     # -> interim/faers_full_with_duplicate_flag.pkl, faers_deduplicated.pkl
python scripts/04_clean_sex.py           # -> interim/*_sex_cleaned.pkl
python scripts/05_clean_drug_names.py    # -> interim/*_drug_cleaned.pkl
python scripts/06_finalize_clean.py      # -> clean/faers_full_clean.csv, clean/faers_deduplicated_clean.csv
```

`interim/` is gitignored — it holds pickled intermediates (to preserve
nested list/dict columns between stages) and is regenerated in full by
rerunning scripts 01–06 in order. Only `raw/` (the initial pull) and
`clean/` (the final CSVs) are meant to persist; everything in between is
disposable.

To validate the cleaned output:

```bash
pytest scripts/test_clean_data.py -v
```

`scripts/02_profile_raw_data.py` is a standalone profiling script (not
part of the numbered pipeline) that generated the missingness figures
used to set the 90% drop threshold in `02_handle_missing.py`.
