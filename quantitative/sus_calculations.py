import pandas as pd

LIKERT_SCORES = {
    'Strongly Disagree': 0,
    'Disagree': 1,
    'Neutral': 2,
    'Agree': 3,
    'Strongly Agree': 4,
    'Stem glad nie saam nie': 0,
    'Stem nie saam nie': 1,
    'Neutraal': 2,
    'Stem saam': 3,
    'Stem sterk saam': 4,
}

SYSTEM_NAME_TRANSLATIONS = {
    'Verkooppuntmasjien (b.v.b. Yoco)': 'POS Machine',
}
PHONE_COLUMN = 6


def calculate_sus_score(item_scores):
    adjusted_scores = [
        score - 1 if question_number % 2 else 5 - score
        for question_number, score in enumerate(item_scores, start=1)
    ]
    return sum(adjusted_scores) * 2.5


def build_scored_data(
    data,
    participant_ids,
    normalize_phone,
    language_blocks,
):
    scored_rows = []

    for _, participant in data.iterrows():
        phone_key = normalize_phone(participant.iloc[PHONE_COLUMN])
        participant_id = participant_ids.get(phone_key, '')
        for language, first_system_column in language_blocks.items():
            for system_number in range(3):
                system_column = first_system_column + system_number * 11
                system = participant.iloc[system_column]

                if pd.isna(system) or not str(system).strip():
                    continue
                system = SYSTEM_NAME_TRANSLATIONS.get(system, system)

                item_scores = [
                    LIKERT_SCORES[participant.iloc[system_column + item_number]]
                    for item_number in range(1, 11)
                ]
                scored_rows.append({
                    'participant_id': participant_id,
                    'phone_number': phone_key,
                    'system': system,
                    'language': language,
                    **{
                        f'item_{item_number}': score
                        for item_number, score in enumerate(item_scores, start=1)
                    },
                    'sus_score': calculate_sus_score(item_scores),
                })

    return pd.DataFrame(scored_rows)
