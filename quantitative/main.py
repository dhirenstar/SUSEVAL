from pathlib import Path

import pandas as pd

from participant_cleaning import (
    CHANGE_LOG_COLUMNS,
    build_participant_lookup,
    clean_participant_tracker,
    duplicate_phone_mappings,
    normalize_phone_detail,
)
from sus_calculations import build_linkage_diagnostics, build_scored_data
from survey_sources import SURVEY_SOURCES
from output_analysis import print_output_analysis
from validation import validate_scored_data

BASE_DIR = Path(__file__).resolve().parent
TRACKER_FILE = BASE_DIR / 'data' / 'participant-tracker.csv'
OUTPUT_DIR = BASE_DIR / 'output'
OUTPUT_FILE = OUTPUT_DIR / 'SUS_scored.csv'
CLEAN_TRACKER_FILE = OUTPUT_DIR / 'participant-tracker_cleaned.csv'
CHANGE_LOG_FILE = OUTPUT_DIR / 'participant-tracker_cleaning_log.csv'
LINKAGE_DIAGNOSTICS_FILE = OUTPUT_DIR / 'linkage_diagnostics_sensitive.csv'
QUALITY_ISSUES_FILE = OUTPUT_DIR / 'data_quality_issues.csv'
PARTICIPANT_SUMMARY_FILE = OUTPUT_DIR / 'participant_summary.csv'


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    tracker = pd.read_csv(TRACKER_FILE, dtype=str, keep_default_na=False)
    clean_tracker, cleaning_changes = clean_participant_tracker(tracker)
    clean_tracker.to_csv(CLEAN_TRACKER_FILE, index=False)
    pd.DataFrame(cleaning_changes, columns=CHANGE_LOG_COLUMNS).to_csv(
        CHANGE_LOG_FILE,
        index=False,
    )

    participant_ids = build_participant_lookup(clean_tracker)
    duplicate_phone_rows = duplicate_phone_mappings(clean_tracker)
    participant_metadata = {
        row['Participant ID']: {'condition_group': row['Condition Group']}
        for _, row in clean_tracker.iterrows()
        if row['Participant ID']
    }
    scored_frames = []
    linkage_frames = []
    for source in SURVEY_SOURCES:
        data = pd.read_csv(
            BASE_DIR / source.filename.removeprefix('./'),
            dtype=str,
            keep_default_na=False,
            encoding=source.encoding,
        )
        scored_frames.append(build_scored_data(
            data, participant_ids, normalize_phone_detail, source, participant_metadata,
        ))
        linkage_frames.append(build_linkage_diagnostics(
            data, participant_ids, normalize_phone_detail, source,
        ))

    scored_data = pd.concat(scored_frames, ignore_index=True)
    linkage_diagnostics = pd.concat(linkage_frames, ignore_index=True)
    quality_issues = validate_scored_data(scored_data, duplicate_phone_rows)
    scored_data.to_csv(OUTPUT_FILE, index=False)
    matched_valid = scored_data[
        scored_data['participant_id'].ne('') & scored_data['processing_status'].eq('valid')
    ].copy()
    matched_valid['sus_score'] = pd.to_numeric(matched_valid['sus_score'])
    participant_summary = (
        matched_valid.groupby(['participant_id', 'language'])
        .agg(
            mean_sus_score=('sus_score', 'mean'),
            evaluations=('sus_score', 'size'),
            systems_evaluated=('system', 'nunique'),
        )
        .reset_index()
    )
    participant_summary.to_csv(PARTICIPANT_SUMMARY_FILE, index=False)
    linkage_diagnostics.to_csv(LINKAGE_DIAGNOSTICS_FILE, index=False)
    quality_issues.to_csv(QUALITY_ISSUES_FILE, index=False)

    print(f'Wrote {len(scored_data)} rows to {OUTPUT_FILE}')
    print(f'Logged {len(cleaning_changes)} tracker cleaning changes to {CHANGE_LOG_FILE}')
    print(f'Wrote sensitive linkage diagnostics to {LINKAGE_DIAGNOSTICS_FILE}')
    print(f'Wrote participant-level summary to {PARTICIPANT_SUMMARY_FILE}')
    print(f'Wrote {len(quality_issues)} data-quality issues to {QUALITY_ISSUES_FILE}')
    print_output_analysis(scored_data, quality_issues, len(linkage_diagnostics))


if __name__ == '__main__':
    main()
