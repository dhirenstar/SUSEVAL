from dataclasses import dataclass
from pathlib import Path
import unittest

import pandas as pd

from participant_cleaning import (
    CHANGE_LOG_COLUMNS,
    build_participant_lookup,
    clean_participant_tracker,
    duplicate_phone_mappings,
    normalize_english_proficiency,
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
GROUPS_DIR = OUTPUT_DIR / 'groups'

GROUP_FILTERS = {
    'afrikaans': ('Afrikaans participant group', 'Experiment B (Written Afrikaans)', 'SUS_afrikaans.csv'),
    'isixhosa': ('isiXhosa participant group', 'Experiment C (Written isiXhosa)', 'SUS_isixhosa.csv'),
    'oral': ('Oral participant group', 'Experiment A (Oral English)', 'SUS_oral.csv'),
}
MENU_OPTIONS = (
    'Process all data',
    'Generate filtered dataset',
    'View data summary',
    'View data quality issues',
    'Run validation checks',
    'Run tests',
    'Exit',
)

SENSITIVE_ANALYSIS_COLUMNS = {
    'linkage_candidate',
    'phone_number',
    'original_phone',
    'normalized_phone',
}


@dataclass
class PipelineResult:
    scored_data: pd.DataFrame
    quality_issues: pd.DataFrame
    linkage_diagnostics: pd.DataFrame
    raw_response_count: int
    cleaning_change_count: int


def _analysis_data(scored_data):
    return scored_data.drop(columns=SENSITIVE_ANALYSIS_COLUMNS, errors='ignore')


def run_pipeline():
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
        row['Participant ID']: {
            'condition_group': row['Condition Group'],
            'english_proficiency_band': normalize_english_proficiency(
                row['English Proficiency Band'],
            ),
        }
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
            sep=source.delimiter,
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
    analysis_data = _analysis_data(scored_data)
    analysis_data.to_csv(OUTPUT_FILE, index=False)
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

    return PipelineResult(
        scored_data=analysis_data,
        quality_issues=quality_issues,
        linkage_diagnostics=linkage_diagnostics,
        raw_response_count=len(linkage_diagnostics),
        cleaning_change_count=len(cleaning_changes),
    )


def _load_existing_outputs():
    if not OUTPUT_FILE.exists():
        raise FileNotFoundError('No scored dataset found. Choose "Process all data" first.')
    scored_data = pd.read_csv(OUTPUT_FILE, dtype=str, keep_default_na=False)
    quality_issues = (
        pd.read_csv(QUALITY_ISSUES_FILE, dtype=str, keep_default_na=False)
        if QUALITY_ISSUES_FILE.exists()
        else pd.DataFrame(columns=['issue_type', 'detail', 'count'])
    )
    raw_response_count = len(scored_data)
    if LINKAGE_DIAGNOSTICS_FILE.exists():
        raw_response_count = len(pd.read_csv(LINKAGE_DIAGNOSTICS_FILE, dtype=str, keep_default_na=False))
    return scored_data, quality_issues, raw_response_count


def generate_group_dataset(scored_data, group_key):
    if group_key not in GROUP_FILTERS:
        raise ValueError(f'Unknown participant group: {group_key}')
    label, condition_group, filename = GROUP_FILTERS[group_key]
    if 'condition_group' not in scored_data.columns:
        raise ValueError('The scored dataset does not contain participant-group metadata.')
    filtered = scored_data[scored_data['condition_group'].eq(condition_group)].copy()
    filtered = _analysis_data(filtered)
    GROUPS_DIR.mkdir(exist_ok=True)
    output_path = GROUPS_DIR / filename
    filtered.to_csv(output_path, index=False)
    return label, output_path, filtered


def _print_processing_summary(result):
    matched = result.scored_data[result.scored_data['linkage_status'].eq('matched')]
    unmatched = result.scored_data[result.scored_data['linkage_status'].ne('matched')]
    invalid = result.scored_data[result.scored_data['processing_status'].ne('valid')]
    duplicate_count = int((result.quality_issues['issue_type'] == 'duplicate_evaluation').sum())
    print('\n' + '=' * 50)
    print('PROCESSING COMPLETE')
    print('=' * 50)
    print('\nInput responses by language')
    for language, count in result.scored_data['language'].value_counts().sort_index().items():
        print(f'  {language:<16} {count}')
    print(f'\nProcessed evaluations: {len(result.scored_data)}')
    print(f'Matched participants:  {matched.loc[matched.participant_id.ne(""), "participant_id"].nunique()}')
    print(f'Unmatched responses:   {len(unmatched)}')
    print('\nData quality')
    print(f'  Duplicate evaluations: {duplicate_count}')
    print(f'  Invalid responses:      {len(invalid)}')
    print(f'  Linkage issues:         {len(unmatched)}')
    print('\nOutputs generated:')
    for path in (OUTPUT_FILE, PARTICIPANT_SUMMARY_FILE, QUALITY_ISSUES_FILE, LINKAGE_DIAGNOSTICS_FILE):
        print(f'  [OK] {path.relative_to(BASE_DIR)}')


def _show_summary():
    scored_data, quality_issues, raw_response_count = _load_existing_outputs()
    print_output_analysis(scored_data, quality_issues, raw_response_count)


def _show_quality_issues():
    _, quality_issues, _ = _load_existing_outputs()
    print('\nDATA QUALITY ISSUES')
    print('===================')
    if quality_issues.empty:
        print('No data-quality issues detected.')
        return
    for _, issue in quality_issues.iterrows():
        print(f"[{issue['issue_type'].upper()}] {issue['detail']} (n={issue['count']})")


def _run_validation():
    _, quality_issues, _ = _load_existing_outputs()
    print('\nVALIDATION RESULT')
    print('=================')
    if quality_issues.empty:
        print('PASS: No validation issues detected.')
        return
    severity = 'ERROR' if (quality_issues['issue_type'] == 'privacy').any() else 'WARNING'
    print(f'{severity}: {len(quality_issues)} validation issue(s) require review.')
    _show_quality_issues()


def _run_tests():
    suite = unittest.defaultTestLoader.discover(str(BASE_DIR), pattern='test_pipeline.py')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print('Tests passed.' if result.wasSuccessful() else 'Tests failed.')


def _prompt_group_dataset():
    print('\nGenerate filtered dataset\n')
    options = [('1', 'afrikaans'), ('2', 'isixhosa'), ('3', 'oral'), ('4', 'all'), ('5', 'cancel')]
    for number, key in options:
        if key == 'all':
            label = 'All participants'
        elif key == 'cancel':
            label = 'Cancel'
        else:
            label = GROUP_FILTERS[key][0]
        print(f'{number}. {label}')
    choice = input('\nSelect an option: ').strip()
    if choice == '5':
        return
    scored_data, _, _ = _load_existing_outputs()
    if choice == '4':
        GROUPS_DIR.mkdir(exist_ok=True)
        output_path = GROUPS_DIR / 'SUS_all.csv'
        _analysis_data(scored_data).to_csv(output_path, index=False)
        filtered = scored_data
        label = 'All participants'
    elif choice in {'1', '2', '3'}:
        key = dict(options)[choice]
        label, output_path, filtered = generate_group_dataset(scored_data, key)
    else:
        print('Please select a number from 1 to 5.')
        return
    print('\n' + '=' * 50)
    print('FILTERED DATASET GENERATED')
    print('=' * 50)
    print(f'\nParticipant group: {label}')
    print(f'\nUnique participants: {filtered.loc[filtered.participant_id.ne(""), "participant_id"].nunique()}')
    print(f'Evaluations: {len(filtered)}')
    print(f'\nOutput (subset of master dataset):\n  [OK] {output_path.relative_to(BASE_DIR)}')


def run_cli():
    while True:
        print('\n' + '=' * 50)
        print('SUS Analysis Pipeline')
        print('=' * 50)
        for number, option in enumerate(MENU_OPTIONS, start=1):
            print(f'{number}. {option}')
        choice = input('\nSelect an option: ').strip()
        if choice == '1':
            try:
                result = run_pipeline()
                _print_processing_summary(result)
            except (FileNotFoundError, ValueError, KeyError, pd.errors.ParserError) as error:
                print(f'\nERROR: {error}')
                print('No output files were generated.')
        elif choice == '2':
            try:
                _prompt_group_dataset()
            except (FileNotFoundError, ValueError, KeyError, pd.errors.ParserError) as error:
                print(f'\nERROR: {error}')
        elif choice == '3':
            try:
                _show_summary()
            except (FileNotFoundError, ValueError, KeyError, pd.errors.ParserError) as error:
                print(f'\nERROR: {error}')
        elif choice == '4':
            try:
                _show_quality_issues()
            except (FileNotFoundError, ValueError, KeyError, pd.errors.ParserError) as error:
                print(f'\nERROR: {error}')
        elif choice == '5':
            try:
                _run_validation()
            except (FileNotFoundError, ValueError, KeyError, pd.errors.ParserError) as error:
                print(f'\nERROR: {error}')
        elif choice == '6':
            _run_tests()
        elif choice == '7':
            print('Goodbye.')
            return
        else:
            print('Please select a number from 1 to 7.')


def main():
    run_cli()


if __name__ == '__main__':
    main()
