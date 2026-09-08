import os

import pandas as pd

from participant_cleaning import (
    CHANGE_LOG_COLUMNS,
    build_participant_lookup,
    clean_participant_tracker,
    normalize_phone,
)
from sus_calculations import build_scored_data

INPUT_FILE = './data/SUS_en-af.csv'
AFRIKAANS_INPUT_FILE = './data/SUS_af.csv'
TRACKER_FILE = './data/participant-tracker.csv'
OUTPUT_FILE = './output/SUS_scored.csv'
CLEAN_TRACKER_FILE = './output/participant-tracker_cleaned.csv'
CHANGE_LOG_FILE = './output/participant-tracker_cleaning_log.csv'


def main():
    os.makedirs('./output', exist_ok=True)

    tracker = pd.read_csv(TRACKER_FILE, dtype=str, keep_default_na=False)
    clean_tracker, cleaning_changes = clean_participant_tracker(tracker)
    clean_tracker.to_csv(CLEAN_TRACKER_FILE, index=False)
    pd.DataFrame(cleaning_changes, columns=CHANGE_LOG_COLUMNS).to_csv(
        CHANGE_LOG_FILE,
        index=False,
    )

    participant_numbers = build_participant_lookup(clean_tracker)
    data = pd.read_csv(INPUT_FILE, dtype=str, keep_default_na=False)
    scored_data = build_scored_data(data, participant_numbers, normalize_phone)

    afrikaans_data = pd.read_csv(
        AFRIKAANS_INPUT_FILE,
        dtype=str,
        keep_default_na=False,
        encoding='latin-1',
    )
    afrikaans_scores = build_scored_data(
        afrikaans_data,
        participant_numbers,
        normalize_phone,
        language_blocks={'afrikaans': 7},
    )
    scored_data = pd.concat([scored_data, afrikaans_scores], ignore_index=True)
    scored_data.to_csv(OUTPUT_FILE, index=False)

    print(f'Wrote {len(scored_data)} rows to {OUTPUT_FILE}')
    print(f'Logged {len(cleaning_changes)} tracker cleaning changes to {CHANGE_LOG_FILE}')


if __name__ == '__main__':
    main()
