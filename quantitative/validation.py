import pandas as pd

from sus_calculations import calculate_sus_score


def validate_scored_data(scored_data, duplicate_phone_rows):
    issues = []

    def add_issue(issue_type, detail, count=1):
        issues.append({
            'issue_type': issue_type,
            'detail': detail,
            'count': count,
        })

    forbidden_phone_columns = {
        'phone_number',
        'original_phone',
        'normalized_phone',
    }
    if forbidden_phone_columns.intersection(column.lower() for column in scored_data.columns):
        add_issue('privacy', 'Final analysis data contains a phone-related column')

    for status, count in scored_data['linkage_status'].value_counts().items():
        if status != 'matched':
            add_issue('linkage', status, int(count))

    for row in duplicate_phone_rows:
        add_issue('linkage', f"{row['status']}: {row['participant_ids']}", 1)

    invalid_rows = scored_data[scored_data['processing_status'].ne('valid')]
    if not invalid_rows.empty:
        add_issue('sus_response', 'Rows with missing or unexpected Likert responses', len(invalid_rows))

    valid_scores = pd.to_numeric(
        scored_data.loc[scored_data['processing_status'].eq('valid'), 'sus_score'],
        errors='coerce',
    )
    if valid_scores.isna().any():
        add_issue('sus_score', 'Valid rows with non-numeric SUS scores', int(valid_scores.isna().sum()))
    out_of_range = valid_scores[(valid_scores < 0) | (valid_scores > 100)]
    if not out_of_range.empty:
        add_issue('sus_score', 'Scores outside 0-100', len(out_of_range))
    off_increment = valid_scores[(valid_scores * 2 % 5).round(8).ne(0)]
    if not off_increment.empty:
        add_issue('sus_score', 'Scores not occurring in 2.5-point increments', len(off_increment))

    for index, row in scored_data[scored_data['processing_status'].eq('valid')].iterrows():
        raw_values = [row[f'item_{item}_raw'] for item in range(1, 11)]
        if any(pd.isna(value) or value == '' for value in raw_values):
            add_issue('sus_response', f"Missing item response at output row {index + 2}")
            continue
        recalculated = calculate_sus_score([int(value) for value in raw_values])
        if recalculated != float(row['sus_score']):
            add_issue('sus_score', f"Stored score disagrees at output row {index + 2}")

    duplicate_keys = (
        scored_data[scored_data['participant_id'].ne('')]
        .groupby(['participant_id', 'language', 'system'])
        .size()
        .reset_index(name='count')
    )
    for _, duplicate in duplicate_keys[duplicate_keys['count'] > 1].iterrows():
        add_issue(
            'duplicate_evaluation',
            f"{duplicate['participant_id']} / {duplicate['language']} / {duplicate['system']}",
            int(duplicate['count']),
        )

    return pd.DataFrame(issues, columns=['issue_type', 'detail', 'count'])
