import re

import pandas as pd


CHANGE_LOG_COLUMNS = [
    'row',
    'participant_id',
    'column',
    'old_value',
    'new_value',
    'reason',
]


def normalize_phone(phone):
    phone = str(phone).strip()
    if not phone:
        return ''

    phone = phone.split('/')[0].strip()
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('27') and len(digits) == 11:
        digits = '0' + digits[2:]
    elif len(digits) == 9 and digits[0] in '678':
        digits = '0' + digits

    return digits if len(digits) == 10 and digits.startswith('0') else ''


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
        if 'duplicate entry' in notes:
            changes.append({
                'row': row_number,
                'participant_id': participant_id,
                'column': '',
                'old_value': participant_id,
                'new_value': '',
                'reason': 'Removed row explicitly marked as a duplicate',
            })
            continue

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
        clean_phone = normalize_phone(original_phone)
        if clean_phone != original_phone.strip():
            changes.append({
                'row': row_number,
                'participant_id': participant_id,
                'column': 'Phone no.',
                'old_value': original_phone,
                'new_value': clean_phone,
                'reason': 'Normalized phone number for matching',
            })
        if original_phone.strip() and not clean_phone:
            changes[-1]['reason'] = 'Cleared invalid phone number; cannot match safely'

        row['Participant ID'] = participant_id
        row['Participant number'] = participant_number
        row['Phone no.'] = clean_phone
        clean_rows.append(row)

    clean_tracker = pd.DataFrame(clean_rows)
    return clean_tracker, changes


def build_participant_lookup(clean_tracker):
    participant_ids = {}
    for _, participant in clean_tracker.iterrows():
        phone_key = normalize_phone(participant['Phone no.'])
        if phone_key and phone_key not in participant_ids:
            participant_ids[phone_key] = participant['Participant ID']
    return participant_ids
