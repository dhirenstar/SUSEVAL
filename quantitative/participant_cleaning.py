import re
from collections import defaultdict

import pandas as pd


CHANGE_LOG_COLUMNS = [
    'row',
    'participant_id',
    'column',
    'old_value',
    'new_value',
    'reason',
]

ENGLISH_PROFICIENCY_BANDS = {'Basic', 'Conversational', 'Fluent', 'Native'}
ENGLISH_PROFICIENCY_TRANSLATIONS = {
    'Ndiyakwazi kakuhle': 'Fluent',
    'Ndiyakwazi ukuthetha': 'Conversational',
    'Vlot': 'Fluent',
    'Moedertaal': 'Native',
    'Lulwimi lwam lokuqala': 'Native',
    'Fully fluent': 'Fluent',
}


def normalize_english_proficiency(value):
    normalized = ' '.join(str(value).strip().split())
    if not normalized:
        return ''
    if normalized in ENGLISH_PROFICIENCY_BANDS:
        return normalized
    return ENGLISH_PROFICIENCY_TRANSLATIONS.get(normalized, '')


def normalize_phone_detail(phone):
    """Return deterministic phone normalization without discarding ambiguity."""
    original = '' if phone is None else str(phone).strip()
    if not original:
        return {
            'original_phone': '',
            'normalized_phone': '',
            'status': 'missing',
            'candidates': '',
        }

    parts = [part.strip() for part in re.split(r'[/;,]|\bor\b|\n', original, flags=re.I)]
    parts = [part for part in parts if part]
    if len(parts) != 1:
        candidates = sorted({_normalize_single_phone(part) for part in parts})
        candidates = [candidate for candidate in candidates if candidate]
        return {
            'original_phone': original,
            'normalized_phone': '',
            'status': 'ambiguous_multiple_numbers',
            'candidates': ';'.join(candidates),
        }

    normalized = _normalize_single_phone(parts[0])
    return {
        'original_phone': original,
        'normalized_phone': normalized,
        'status': 'valid' if normalized else 'invalid',
        'candidates': normalized,
    }


def _normalize_single_phone(phone):
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('27') and len(digits) == 11:
        digits = '0' + digits[2:]
    elif len(digits) == 9 and digits[0] in '678':
        digits = '0' + digits
    if len(digits) == 10 and re.fullmatch(r'0[6-8]\d{8}', digits):
        return digits
    return ''


def normalize_phone(phone):
    return normalize_phone_detail(phone)['normalized_phone']


def clean_participant_tracker(tracker):
    changes = []
    clean_rows = []

    for row_number, (_, row) in enumerate(tracker.iterrows(), start=2):
        if not any(str(value).strip() for value in row):
            changes.append({
                'row': row_number,
                'participant_id': '',
                'column': '',
                'old_value': '',
                'new_value': '',
                'reason': 'Removed blank row',
            })
            continue

        participant_id = str(row['Participant ID']).strip()
        notes = str(row['Notes']).strip().lower()
        participant_number = str(row['Participant number']).strip()
        if not participant_number and re.fullmatch(r'P\d+', participant_id):
            participant_number = participant_id[1:]
            changes.append({
                'row': row_number,
                'participant_id': participant_id,
                'column': 'Participant number',
                'old_value': '',
                'new_value': participant_number,
                'reason': 'Filled from Participant ID',
            })

        original_phone = str(row['Phone no.'])
        phone_detail = normalize_phone_detail(original_phone)
        clean_phone = phone_detail['normalized_phone']
        if clean_phone != original_phone.strip():
            changes.append({
                'row': row_number,
                'participant_id': participant_id,
                'column': 'Phone no.',
                'old_value': original_phone,
                'new_value': clean_phone,
                'reason': 'Normalized phone number for matching',
            })
        if original_phone.strip() and phone_detail['status'] != 'valid':
            changes.append({
                'row': row_number,
                'participant_id': participant_id,
                'column': 'Phone no.',
                'old_value': original_phone,
                'new_value': clean_phone,
                'reason': f"{phone_detail['status']}; cannot match safely",
            })

        if 'duplicate entry' in notes:
            changes.append({
                'row': row_number,
                'participant_id': participant_id,
                'column': 'Notes',
                'old_value': str(row['Notes']),
                'new_value': str(row['Notes']),
                'reason': 'Retained tracker row marked as duplicate for audit; linkage remains subject to ambiguity checks',
            })

        row['Participant ID'] = participant_id
        row['Participant number'] = participant_number
        row['Phone no.'] = clean_phone
        original_proficiency = str(row['English Proficiency Band'])
        clean_proficiency = normalize_english_proficiency(original_proficiency)
        if clean_proficiency != original_proficiency.strip():
            changes.append({
                'row': row_number,
                'participant_id': participant_id,
                'column': 'English Proficiency Band',
                'old_value': original_proficiency,
                'new_value': clean_proficiency,
                'reason': 'Normalized proficiency band',
            })
        row['English Proficiency Band'] = clean_proficiency
        clean_rows.append(row)

    clean_tracker = pd.DataFrame(clean_rows)
    return clean_tracker, changes


def build_participant_lookup(clean_tracker):
    participant_ids = defaultdict(list)
    for _, participant in clean_tracker.iterrows():
        phone_key = normalize_phone(participant['Phone no.'])
        if phone_key and participant['Participant ID'] not in participant_ids[phone_key]:
            participant_ids[phone_key].append(participant['Participant ID'])
    return dict(participant_ids)


def duplicate_phone_mappings(clean_tracker):
    duplicates = []
    grouped = clean_tracker.copy()
    grouped['normalized_phone'] = grouped['Phone no.'].map(normalize_phone)
    for phone, rows in grouped[grouped['normalized_phone'].ne('')].groupby('normalized_phone'):
        participant_ids = sorted(rows['Participant ID'].astype(str).unique())
        if len(participant_ids) > 1:
            duplicates.append({
                'normalized_phone': phone,
                'participant_ids': ';'.join(participant_ids),
                'status': 'ambiguous_duplicate_phone_mapping',
            })
    return duplicates
