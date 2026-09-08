from dataclasses import dataclass


@dataclass(frozen=True)
class SurveyBlock:
    language: str
    system_column: int
    system_order: int
    language_order: int


@dataclass(frozen=True)
class SurveySource:
    filename: str
    encoding: str
    name: str
    phone_column: int
    blocks: tuple[SurveyBlock, ...]

    def validate_columns(self, columns):
        for block in self.blocks:
            item_columns = range(block.system_column + 1, block.system_column + 11)
            if block.system_column + 10 >= len(columns):
                raise ValueError(
                    f'{self.name}: block at column {block.system_column} does not contain 10 item columns'
                )
            header = str(columns[block.system_column]).lower()
            if 'system' not in header and 'stelsel' not in header:
                raise ValueError(
                    f'{self.name}: expected a system selector at column {block.system_column}, got {columns[block.system_column]!r}'
                )
            if any(not str(columns[column]).strip() for column in item_columns):
                raise ValueError(f'{self.name}: blank SUS item header in block at column {block.system_column}')
        if self.phone_column >= len(columns):
            raise ValueError(f'{self.name}: configured phone column is outside the source schema')


SURVEY_SOURCES = (
    SurveySource(
        filename='./data/SUS_en-af.csv',
        encoding='utf-8',
        name='SUS_en-af',
        phone_column=6,
        blocks=(
            SurveyBlock('english', 7, 1, 1), SurveyBlock('english', 18, 2, 1), SurveyBlock('english', 29, 3, 1),
            SurveyBlock('afrikaans', 40, 1, 2), SurveyBlock('afrikaans', 51, 2, 2), SurveyBlock('afrikaans', 62, 3, 2),
        ),
    ),
    SurveySource(
        filename='./data/SUS_af.csv',
        encoding='latin-1',
        name='SUS_af',
        phone_column=6,
        blocks=(SurveyBlock('afrikaans', 7, 1, 1), SurveyBlock('afrikaans', 18, 2, 1), SurveyBlock('afrikaans', 29, 3, 1)),
    ),
    SurveySource(
        filename='./data/SUS_en.csv',
        encoding='utf-8',
        name='SUS_en',
        phone_column=6,
        blocks=(SurveyBlock('english', 7, 1, 1), SurveyBlock('english', 18, 2, 1), SurveyBlock('english', 29, 3, 1)),
    ),
)
