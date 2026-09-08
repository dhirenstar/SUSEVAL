import unittest

import pandas as pd

from participant_cleaning import normalize_phone, normalize_phone_detail
from survey_sources import SURVEY_SOURCES
from sus_calculations import calculate_sus_score, build_scored_data
from validation import validate_scored_data


class PipelineRegressionTests(unittest.TestCase):
    def test_known_sus_scores(self):
        self.assertEqual(calculate_sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]), 100.0)
        self.assertEqual(calculate_sus_score([3] * 10), 50.0)

    def test_phone_normalization_does_not_discard_multiple_values(self):
        detail = normalize_phone_detail('0792749238 / 0662153473')
        self.assertEqual(detail['status'], 'ambiguous_multiple_numbers')
        self.assertEqual(normalize_phone('+27 79 274 9238'), '0792749238')

    def test_ambiguous_phone_is_not_assigned(self):
        source = SURVEY_SOURCES[1]
        data = pd.read_csv(source.filename, dtype=str, keep_default_na=False, encoding=source.encoding)
        data.iloc[0, source.phone_column] = '0680055906'
        scored = build_scored_data(
            data,
            {'0680055906': ['P073', 'P077']},
            normalize_phone_detail,
            source,
        )
        self.assertTrue((scored['participant_id'] == '').all())
        self.assertTrue((scored['linkage_status'] == 'ambiguous_duplicate_phone').all())

    def test_malformed_source_structure_fails_validation(self):
        source = SURVEY_SOURCES[1]
        data = pd.read_csv(source.filename, dtype=str, keep_default_na=False, encoding=source.encoding)
        data.columns = [f'changed_{index}' for index in range(len(data.columns))]
        with self.assertRaises(ValueError):
            build_scored_data(data, {}, normalize_phone_detail, source)

    def test_final_dataset_has_no_phone_values_and_duplicates_are_reported(self):
        scored = pd.read_csv('output/SUS_scored.csv', dtype=str, keep_default_na=False)
        self.assertFalse(any(column in scored.columns for column in ('phone_number', 'original_phone', 'normalized_phone')))
        issues = validate_scored_data(scored, [])
        duplicate_details = issues.loc[issues['issue_type'].eq('duplicate_evaluation'), 'detail'].tolist()
        self.assertIn('P018 / english / ATM', duplicate_details)
        self.assertIn('P055 / english / Uber', duplicate_details)
        self.assertIn('P065 / english / ATM', duplicate_details)
        scores = pd.to_numeric(scored.loc[scored['processing_status'].eq('valid'), 'sus_score'])
        self.assertTrue(((scores >= 0) & (scores <= 100)).all())
        self.assertTrue(((scores * 2 % 5).round(8) == 0).all())


if __name__ == '__main__':
    unittest.main()
