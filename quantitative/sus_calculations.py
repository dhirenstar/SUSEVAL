from difflib import SequenceMatcher

import pandas as pd


LIKERT_SCORES = {
    'Strongly Disagree': 1,
    'Disagree': 2,
    'Neutral': 3,
    'Agree': 4,
    'Strongly Agree': 5,
    'Stem glad nie saam nie': 1,
    'Stem nie saam nie': 2,
    'Neutraal': 3,
    'Stem saam': 4,
    'Stem sterk saam': 5,
    'Ndiyavumelani kakhulu (Strongly Disagree)': 1,
    'Andivumelani kakhulu (Strongly Disagree)': 1,
    'Andivumelani (Disagree)': 2,
    'Andinangcamango / Ndiphakathi (Neutral)': 3,
    'Ndiyavumelana (Agree)': 4,
    'Ndiyavumelana kakhulu (Strongly Agree)': 5,
}

SYSTEM_NAME_TRANSLATIONS = {
    'Verkooppuntmasjien (b.v.b. Yoco)': 'POS Machine',
    'Takealot.com': 'Takealot',
}


def _clean_text(value):
    return ' '.join(str(value).strip().split())


def _likert_score(value):
    return LIKERT_SCORES.get(_clean_text(value))


def calculate_sus_score(item_scores):
    if len(item_scores) != 10 or any(score not in range(1, 6) for score in item_scores):
        raise ValueError('SUS scoring requires exactly ten responses in the 1-5 range')
    adjusted_scores = [
        score - 1 if question_number % 2 else 5 - score
        for question_number, score in enumerate(item_scores, start=1)
    ]
    return sum(adjusted_scores) * 2.5


def _link_participant(phone_detail, participant_ids):
    phone_key = phone_detail['normalized_phone']
    matches = participant_ids.get(phone_key, []) if phone_key else []
    if len(matches) == 1:
        return matches[0], 'matched', ''
    if len(matches) > 1:
        return '', 'ambiguous_duplicate_phone', ';'.join(sorted(matches))
    if phone_detail['status'] == 'ambiguous_multiple_numbers':
        suggestions = []
        for candidate_phone in phone_detail['candidates'].split(';'):
            suggestions.extend(participant_ids.get(candidate_phone, []))
        return '', 'ambiguous_multiple_numbers', ';'.join(sorted(set(suggestions)))
    if phone_key:
        suggestions = []
        for candidate_phone, candidate_ids in participant_ids.items():
            if SequenceMatcher(None, phone_key, candidate_phone).ratio() >= 0.9:
                suggestions.extend(candidate_ids)
        return '', 'unmatched', ';'.join(sorted(set(suggestions)))
    return '', f"unmatched_{phone_detail['status']}", ''


def build_linkage_diagnostics(data, participant_ids, normalize_phone_detail, source):
    source.validate_columns(data.columns)
    diagnostics = []
    for source_row, participant in data.iterrows():
        phone_detail = normalize_phone_detail(participant.iloc[source.phone_column])
        participant_id, linkage_status, linkage_candidate = _link_participant(
            phone_detail,
            participant_ids,
        )
        diagnostics.append({
            'source_survey': source.name,
            'source_row': source_row + 2,
            'source_response_id': str(participant.iloc[0]).strip(),
            'original_phone': phone_detail['original_phone'],
            'normalized_phone': phone_detail['normalized_phone'],
            'phone_normalization_status': phone_detail['status'],
            'participant_id': participant_id,
            'linkage_status': linkage_status,
            'linkage_candidate': linkage_candidate,
        })
    return pd.DataFrame(diagnostics)


def build_scored_data(
    data,
    participant_ids,
    normalize_phone_detail,
    source,
    participant_metadata=None,
):
    source.validate_columns(data.columns)
    participant_metadata = participant_metadata or {}
    scored_rows = []

    for source_row, participant in data.iterrows():
        phone_detail = normalize_phone_detail(participant.iloc[source.phone_column])
        participant_id, linkage_status, linkage_candidate = _link_participant(
            phone_detail,
            participant_ids,
        )
        response_id = str(participant.iloc[0]).strip()
        for block in source.blocks:
            system_column = block.system_column
            system_raw = _clean_text(participant.iloc[system_column])
            if not system_raw:
                continue

            raw_responses = [
                _clean_text(participant.iloc[system_column + item_number])
                for item_number in range(1, 11)
            ]
            item_scores = [_likert_score(response) for response in raw_responses]
            invalid_items = [
                str(item_number)
                for item_number, score in enumerate(item_scores, start=1)
                if score is None
            ]
            flags = []
            if linkage_status != 'matched':
                flags.append(linkage_status)
            if invalid_items:
                flags.append(f"invalid_likert_items:{','.join(invalid_items)}")

            valid_response = not invalid_items
            row = {
                'source_survey': source.name,
                'source_row': source_row + 2,
                'source_response_id': response_id,
                'participant_id': participant_id,
                'survey_source': source.name,
                'language': block.language,
                'condition_group': participant_metadata.get(participant_id, {}).get('condition_group', ''),
                'english_proficiency_band': participant_metadata.get(participant_id, {}).get(
                    'english_proficiency_band', '',
                ),
                'language_order': block.language_order,
                'system_raw': system_raw,
                'system': SYSTEM_NAME_TRANSLATIONS.get(system_raw, system_raw),
                'system_order': block.system_order,
                'linkage_status': linkage_status,
                'linkage_candidate': linkage_candidate,
                'phone_normalization_status': phone_detail['status'],
                'processing_status': 'valid' if valid_response else 'invalid_sus_response',
                'validation_flags': ';'.join(flags),
            }
            for item_number, score in enumerate(item_scores, start=1):
                row[f'item_{item_number}_raw'] = score if score is not None else ''
                row[f'item_{item_number}_scored'] = ''
            if valid_response:
                for item_number, score in enumerate(item_scores, start=1):
                    row[f'item_{item_number}_scored'] = (
                        score - 1 if item_number % 2 else 5 - score
                    )
                row['sus_score'] = calculate_sus_score(item_scores)
            else:
                row['sus_score'] = ''
            scored_rows.append(row)

    return pd.DataFrame(scored_rows)
