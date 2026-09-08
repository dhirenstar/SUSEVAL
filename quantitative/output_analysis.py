import pandas as pd


def _print_counts(title, counts):
    print(f'\n{title}:')
    if counts.empty:
        print('  none')
    for key, count in counts.items():
        print(f'  {key}: {count}')


def _print_summary(title, data):
    print(f'\n{title}:')
    if data.empty:
        print('  unavailable')
        return
    summary = data.agg(['count', 'mean', 'std', 'median', 'min', 'max']).to_frame().T
    summary['IQR'] = data.quantile(0.75) - data.quantile(0.25)
    print(summary[['count', 'mean', 'std', 'median', 'min', 'max', 'IQR']].round(2).to_string(index=False))


def print_output_analysis(scored_data, quality_issues, raw_response_count):
    valid = scored_data[scored_data['processing_status'].eq('valid')].copy()
    matched = scored_data[scored_data['linkage_status'].eq('matched')]

    print('\nDATASET OVERVIEW')
    print('----------------')
    print(f'Raw survey responses: {raw_response_count}')
    print(f'Evaluation rows: {len(scored_data)}')
    print(f'Unique matched participants: {matched.loc[matched.participant_id.ne(""), "participant_id"].nunique()}')
    _print_counts('Evaluations by survey source', scored_data['survey_source'].value_counts().sort_index())
    _print_counts('Evaluations by language', scored_data['language'].value_counts().sort_index())
    _print_counts('Evaluations by system', scored_data['system'].value_counts().sort_index())

    print('\nLINKAGE')
    print('-------')
    _print_counts('Linkage status', scored_data['linkage_status'].value_counts().sort_index())
    _print_counts('Phone normalization status', scored_data['phone_normalization_status'].value_counts().sort_index())

    participant_rows = matched[matched['participant_id'].ne('')]
    _print_counts('Evaluations per participant', participant_rows['participant_id'].value_counts().sort_index())
    _print_counts('Participants contributing by language', participant_rows.groupby('language')['participant_id'].nunique().sort_index())
    _print_counts('Participants contributing by system', participant_rows.groupby('system')['participant_id'].nunique().sort_index())

    duplicates = (
        participant_rows.groupby(['participant_id', 'language', 'system'])
        .size()
        .reset_index(name='evaluations')
    )
    duplicates = duplicates[duplicates['evaluations'] > 1]
    print('\nDUPLICATE EVALUATION KEYS')
    print('------------------------')
    print(duplicates.to_string(index=False) if not duplicates.empty else 'none')

    scores = pd.to_numeric(valid['sus_score'], errors='coerce').dropna()
    _print_summary('Overall SUS score summary', scores)
    grouped = valid.assign(sus_score=pd.to_numeric(valid['sus_score'], errors='coerce')).groupby(['language', 'system'])['sus_score']
    print('\nSUS SUMMARY BY LANGUAGE AND SYSTEM')
    print('----------------------------------')
    grouped_summary = grouped.agg(['count', 'mean', 'std', 'median', 'min', 'max'])
    grouped_summary['IQR'] = grouped.quantile(0.75) - grouped.quantile(0.25)
    print(grouped_summary.round(2).to_string() if not grouped_summary.empty else 'unavailable')

    print('\nITEM-LEVEL SUMMARIES (REVERSE-SCORED VALUES)')
    print('---------------------------------------------')
    item_rows = []
    for item_number in range(1, 11):
        values = pd.to_numeric(valid[f'item_{item_number}_scored'], errors='coerce')
        item_rows.append({'item': item_number, 'n': values.count(), 'mean': values.mean(), 'std': values.std(), 'missing': values.isna().sum()})
    print(pd.DataFrame(item_rows).round(2).to_string(index=False))

    print('\nDATA QUALITY WARNINGS')
    print('---------------------')
    if quality_issues.empty:
        print('none')
    else:
        for _, issue in quality_issues.iterrows():
            print(f"  [{issue['issue_type']}] {issue['detail']} (n={issue['count']})")

    print('\nLIMITATION')
    print('----------')
    print('Rows are evaluations, not independent participants. Language and system are retained because the bilingual forms do not establish a matched system set or a causal language effect.')
