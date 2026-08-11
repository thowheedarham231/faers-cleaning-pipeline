# Decision Log

Reasoning behind each cleaning step in the FAERS pipeline. Source data:
`raw/faers_raw.json`, 5,000 adverse event reports pulled from the openFDA
FAERS API for `receivedate` between 2023-01-01 and 2023-12-31
(`scripts/01_pull_data.py`).

## 02_handle_missing.py — drop columns over 90% missing

Profiling (`scripts/02_profile_raw_data.py`) showed a long tail of
top-level/flattened columns with very high missingness. Columns clearing a
90% missing threshold carry essentially no signal at 5,000 records, so they
were dropped outright rather than imputed:

- `authoritynumb` — 96.12% missing
- `primarysource.literaturereference` — 95.50% missing
- `reportduplicate`, `reportduplicate.duplicatenumb`, `reportduplicate.duplicatesource` — 88.6–89.0% each

The `reportduplicate` group sits just under the 90% cutoff individually, but
was dropped alongside the others because it's one logical field, not three:
profiling found `reportduplicate` is inconsistently *shaped* across
records (dict on 569 records, list of dicts on 550, absent on 3,881), which
is why it fragments into three columns on flatten. Keeping a
fragmented, low-signal field split across three sparse columns wasn't worth
the complexity of reconciling its shape.

Three other high-missingness columns were deliberately **kept, not
dropped**, because they carry real analytical value despite sparsity —
losing them outright felt like a bigger loss than the columns above:

- `patient.patientweight` — 89.16% missing
- `patient.patientagegroup` — 76.50% missing
- `patient.summary` — 58.82% missing

Rather than silently keeping them, the script flags exactly how much signal
is lost (record counts with/without a value) so downstream consumers know
the coverage before relying on these fields.

Net effect: 40 columns → 35.

## 03_flag_duplicates.py — preserve FAERS's self-flagged duplicates, don't silently drop them

FAERS reports carry their own `duplicate` field, separate from
`safetyreportid` uniqueness (all 5,000 `safetyreportid` values are already
unique — there's no ID collision to resolve). 1,122 of 5,000 records
(22.4%) are self-flagged by FAERS as potential duplicates of another
report.

Rather than unilaterally deciding these should be removed, the script
produces **two dataset variants**:

1. **Full** (5,000 records) — every record kept, with the duplicate flag
   preserved as-is plus an explicit `is_potential_duplicate` boolean column.
2. **Deduplicated** (3,878 records) — the 1,122 flagged records excluded.

The reasoning: whether a FAERS-flagged "duplicate" should actually be
excluded depends on the downstream analysis (e.g. signal detection work
often wants duplicates removed, while completeness/audit work wants every
report retained). Silently dropping 22% of the data inside a "cleaning"
step would hide that decision from whoever uses the output. Keeping both
variants pushes the choice to the point of use instead of baking it into
the pipeline.

## 04_clean_sex.py — recode to Male/Female/Unknown, don't drop missing rows

`patient.patientsex` uses FAERS's numeric code list ({1, 2}), which isn't
self-describing and isn't human-readable. Recoded 1 → `'Male'`,
2 → `'Female'`.

9.02% of records (451 of 5,000) had no `patientsex` value at all. These
were recoded to `'Unknown'` rather than dropped, matching the same
philosophy as the missing-data step: missingness is itself information
worth keeping visible, and dropping ~9% of records over one field would be
a disproportionate loss for a value that's likely irrelevant to most
downstream questions. If a specific analysis needs sex-known records only,
filtering on `'Unknown'` is a one-line operation against the cleaned
column — cheaper than trying to recover 451 dropped rows later.

Applied to both dataset variants from `03_flag_duplicates.py` so the choice
made there (full vs deduplicated) stays independent of this one.

## 05_clean_drug_names.py — fix casing, do not fuzzy-match brand names

`patient.drug[].medicinalproduct` had 2,205 unique raw values, 6 of which
were exact-match casing/whitespace variants of each other (e.g.
`'COVID-19 VACCINE'` / `'Covid-19 Vaccine'` / `'covid-19 vaccine'`).
Standardizing to `strip().upper()` collapsed those 6 groups with zero
ambiguity — same string, different case, unambiguously the same value.

Deliberately **not attempted**: fuzzy-matching or otherwise merging
genuinely distinct name variants that likely refer to the same underlying
product or product family — e.g. `'PFIZER-BIONTECH COVID-19 VACCINE'` vs
`'PFIZER/BIONTECH'` vs `'COVID-19 VACCINE'`. These are different strings
representing different levels of specificity (brand+manufacturer vs
manufacturer alone vs generic product class), and collapsing them correctly
requires a real drug ontology or NDC/brand-name lookup, not string
similarity. A naive fuzzy match risks silently merging genuinely different
drugs that happen to share tokens, which is worse than leaving them
distinct. That normalization belongs in a dedicated step with a real
reference dataset, not bundled into casing cleanup.


## 06_06_finalize_clean.py — Flattens and cleans data
Flattened patient.drug and patient.reaction into
semicolon-separated strings, one row per report (not one row per
drug) — preserves the original 5,000/3,878 record counts rather
than multiplying rows per drug, keeping the row counts documented
earlier accurate. Exported both full and deduplicated versions as
CSV instead of pickle, since a portfolio piece needs to be openable
by anyone reviewing the repo, not just in Python.

2026-08-XX: Split drug_names into a separate drug-level export
(one row per drug mention) for accurate per-drug counting in
visualizations — the report-level flattened string undercounts
drugs appearing multiple times per report (e.g. "HUMIRA" vs
"HUMIRA; HUMIRA" were being treated as distinct categories).