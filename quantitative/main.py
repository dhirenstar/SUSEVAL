import os

import pandas as pd

from participant_cleaning import (
    CHANGE_LOG_COLUMNS,
    build_participant_lookup,
    clean_participant_tracker,
    normalize_phone,
)
from sus_calculations import build_scored_data
from survey_sources import SURVEY_SOURCES
from output_analysis import print_output_analysis

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

    participant_ids = build_participant_lookup(clean_tracker)
    scored_frames = []
    for source in SURVEY_SOURCES:
        data = pd.read_csv(
            source.filename,
            dtype=str,
            keep_default_na=False,
            encoding=source.encoding,
        )
        scored_frames.append(build_scored_data(
            data,
            participant_ids,
            normalize_phone,
            source.language_blocks,
        ))

    scored_data = pd.concat(scored_frames, ignore_index=True)
    scored_data.to_csv(OUTPUT_FILE, index=False)

    print(f'Wrote {len(scored_data)} rows to {OUTPUT_FILE}')
    print(f'Logged {len(cleaning_changes)} tracker cleaning changes to {CHANGE_LOG_FILE}')
    print_output_analysis(scored_data)


if __name__ == '__main__':
    main()
