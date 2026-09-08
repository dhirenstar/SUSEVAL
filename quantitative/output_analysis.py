import pandas as pd


def print_output_analysis(scored_data):
    total_responses = len(scored_data)
    missing_ids = scored_data[scored_data['participant_id'].eq('')]
    matched_ids = scored_data[scored_data['participant_id'].ne('')]
    language_counts = scored_data['language'].value_counts().sort_index()
    system_counts = scored_data['system'].value_counts().sort_index()

    print('\nOutput analysis')
    print('---------------')
    print(f'Total responses: {total_responses}')
    print(f'Matched participant IDs: {len(matched_ids)}')
    print(f'Missing participant IDs: {len(missing_ids)}')

    print('\nResponses per language:')
    for language, count in language_counts.items():
        print(f'  {language}: {count}')

    print('\nResponses per system:')
    for system, count in system_counts.items():
        print(f'  {system}: {count}')

    if missing_ids.empty:
        print('\nMissing participant ID values: none')
    else:
        print('\nMissing participant ID values:')
        missing_details = (
            missing_ids
            .groupby(['phone_number', 'language', 'system'])
            .size()
            .reset_index(name='responses')
        )
        for _, missing in missing_details.iterrows():
            print(
                f"  phone {missing['phone_number'] or '[blank]'}; "
                f"{missing['language']} {missing['system']}: "
                f"{missing['responses']} response(s)"
            )

    if matched_ids.empty:
        print('\nSUS score summary: unavailable')
    else:
        scores = matched_ids['sus_score']
        print('\nSUS score summary for matched responses:')
        print(f'  Mean: {scores.mean():.2f}')
        print(f'  Median: {scores.median():.2f}')
        print(f'  Minimum: {scores.min():.2f}')
        print(f'  Maximum: {scores.max():.2f}')
