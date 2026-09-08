from dataclasses import dataclass


@dataclass(frozen=True)
class SurveySource:
    filename: str
    encoding: str
    language_blocks: dict[str, int]


SURVEY_SOURCES = (
    SurveySource(
        filename='./data/SUS_en-af.csv',
        encoding='utf-8',
        language_blocks={'english': 7, 'afrikaans': 40},
    ),
    SurveySource(
        filename='./data/SUS_af.csv',
        encoding='latin-1',
        language_blocks={'afrikaans': 7},
    ),
    SurveySource(
        filename='./data/SUS_en.csv',
        encoding='utf-8',
        language_blocks={'english': 7},
    ),
)
