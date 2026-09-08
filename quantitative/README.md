# Quantitative analysis

This folder contains the Python pipeline used to clean the participant tracker,
link survey responses to participants, calculate System Usability Scale (SUS)
scores, validate the results, and produce analysis-ready CSV files.

## Folder structure

```text
quantitative/
├── main.py
├── output_analysis.py
├── participant_cleaning.py
├── survey_sources.py
├── sus_calculations.py
├── validation.py
├── test_pipeline.py
├── data/
│   ├── participant-tracker.csv
│   ├── SUS_af.csv
│   ├── SUS_en-af.csv
│   ├── SUS_en.csv
│   └── SUS_xh.csv
└── output/
		└── generated CSV files
```

## Scripts

### `main.py`

Entry point for the complete pipeline. It:

1. Reads and cleans `data/participant-tracker.csv`.
2. Builds a participant lookup from normalized phone numbers.
3. Reads every survey source configured in `survey_sources.py`.
4. Extracts each ten-item SUS block and links it to a participant where the
	 phone number identifies exactly one participant.
5. Writes scored data, summaries, diagnostics, and quality issues to `output/`.
6. Prints a dataset, linkage, SUS-score, and data-quality overview.

Run it from this folder with:

```powershell
python main.py
```

### `survey_sources.py`

Defines the schema for each input survey with `SurveySource` and `SurveyBlock`.
The configuration records the file encoding, delimiter, phone-number column,
language, system columns, and order of each SUS block. It also validates that
the expected system and item columns exist before processing a file.

Configured sources are:

- `SUS_en-af.csv`: English and Afrikaans blocks in one file.
- `SUS_af.csv`: Afrikaans blocks.
- `SUS_en.csv`: English blocks.
- `SUS_xh.csv`: isiXhosa blocks, using a semicolon delimiter and UTF-8 BOM.

### `participant_cleaning.py`

Cleans participant tracker values and prepares them for linkage. It normalizes
South African phone numbers, preserves ambiguous multiple-number entries,
fills missing participant numbers when they can be derived from a participant
ID, detects duplicate phone-to-participant mappings, and records every change
in an audit log.

### `sus_calculations.py`

Contains the scoring and linkage logic. It translates the English, Afrikaans,
and isiXhosa Likert responses to values from 1 to 5, reverse-scores the even
SUS items, calculates the 0-100 SUS score, translates selected system names,
and creates both scored rows and sensitive linkage diagnostics.

Linkage is conservative: ambiguous duplicate phone numbers, multiple numbers
in one response, and unmatched numbers are flagged rather than assigned to a
participant.

### `validation.py`

Checks the scored dataset for privacy problems, unmatched or ambiguous
linkage, invalid SUS responses, scores outside the 0-100 range, scores that do
not use 2.5-point increments, score calculation mismatches, and duplicate
participant/language/system evaluation keys. It returns a table of issues for
review.

### `output_analysis.py`

Prints a human-readable summary after the pipeline runs, including row counts,
language and system distributions, linkage statuses, participant coverage,
duplicate evaluation keys, overall and grouped SUS summaries, item-level
statistics, and data-quality warnings.

### `test_pipeline.py`

Contains regression tests for SUS scoring, phone normalization, ambiguous
linkage handling, source-schema validation, privacy checks, duplicate
reporting, and isiXhosa parsing.

Run the tests from this folder with:

```powershell
python -m unittest test_pipeline.py
```

## Input data

All input files are under `data/`:

- `participant-tracker.csv`: participant IDs, participant numbers, phone
	numbers, condition groups, and notes used for controlled linkage.
- `SUS_en-af.csv`: combined English/Afrikaans survey export.
- `SUS_af.csv`: Afrikaans survey export.
- `SUS_en.csv`: English survey export.
- `SUS_xh.csv`: isiXhosa survey export.

Survey files may contain several system blocks per response. Each populated
block contributes one evaluation row with ten SUS item responses.

## Generated output

Running `main.py` creates or updates these files in `output/`:

- `SUS_scored.csv`: primary analysis dataset. Contains one row per populated
	survey-system block, translated metadata, raw and reverse-scored SUS items,
	SUS scores, linkage status, and processing flags. Phone columns are not
	included.
- `participant_summary.csv`: participant/language summary of valid evaluations,
	including mean SUS score, evaluation count, and number of systems evaluated.
- `participant-tracker_cleaned.csv`: cleaned tracker used by the pipeline.
- `participant-tracker_cleaning_log.csv`: audit trail of tracker changes and
	values that could not be safely normalized.
- `data_quality_issues.csv`: validation findings requiring review.
- `linkage_diagnostics_sensitive.csv`: phone-based linkage diagnostics,
	including original and normalized phone values. Treat this file as
	sensitive and do not distribute with general analysis outputs.

The `output/` directory is generated data. Re-running the pipeline overwrites
these files with results based on the current inputs.

## Processing notes

- SUS scoring requires exactly ten valid Likert responses. Odd-numbered items
	use `itemScore - 1`; even-numbered items use `5 - itemScore`; the adjusted
	total is multiplied by 2.5.
- Rows with invalid Likert values remain in `SUS_scored.csv` with an invalid
	processing status and no SUS score.
- A participant is linked only when a normalized phone number maps to one
	participant. Fuzzy matches are retained as candidates for review and are
	not automatically assigned.
- The analysis treats rows as evaluations, not independent participants.
	Language and system are retained as grouping variables; the pipeline does
	not establish a causal language effect or a matched system set.
