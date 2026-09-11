import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from main import MENU_OPTIONS, generate_group_dataset
from participant_cleaning import normalize_english_proficiency, normalize_phone, normalize_phone_detail
from survey_sources import SURVEY_SOURCES
from sus_calculations import calculate_sus_score, build_scored_data
from validation import validate_scored_data


class PipelineRegressionTests(unittest.TestCase):
    def test_english_proficiency_is_normalized(self):
        expected = {
            '': '',
            'Basic': 'Basic',
            'Conversational': 'Conversational',
            'Fluent': 'Fluent',
            'Native': 'Native',
            'Fully fluent': 'Fluent',
            'Vlot': 'Fluent',
            'Moedertaal': 'Native',
            'Lulwimi lwam lokuqala': 'Native',
            'Ndiyakwazi kakuhle': 'Fluent',
            'Ndiyakwazi ukuthetha': 'Conversational',
        }
        for source, canonical in expected.items():
            self.assertEqual(normalize_english_proficiency(source), canonical)

    def test_cli_exposes_expected_operations(self):
        self.assertEqual(len(MENU_OPTIONS), 7)
        self.assertEqual(MENU_OPTIONS[0], 'Process all data')
        self.assertEqual(MENU_OPTIONS[-1], 'Exit')

    def test_group_filter_uses_condition_group_not_response_language(self):
        scored = pd.DataFrame([
            {
                'participant_id': 'P001',
                'condition_group': 'Experiment B (Written Afrikaans)',
                'language': 'english',
                'linkage_candidate': '',
                'sus_score': '80',
            },
            {
                'participant_id': 'P002',
                'condition_group': 'Experiment A (Oral English)',
                'language': 'afrikaans',
                'linkage_candidate': '',
                'sus_score': '70',
            },
        ])
        original = scored.copy(deep=True)
        with TemporaryDirectory() as temporary_directory, patch(
            'main.GROUPS_DIR', Path(temporary_directory),
        ):
            _, output_path, filtered = generate_group_dataset(scored, 'afrikaans')

        self.assertEqual(output_path.name, 'SUS_afrikaans.csv')
        self.assertEqual(filtered['participant_id'].tolist(), ['P001'])
        self.assertEqual(filtered['language'].tolist(), ['english'])
        self.assertNotIn('linkage_candidate', filtered.columns)
        self.assertTrue(scored.equals(original))

    def test_all_group_filters_use_participant_condition_metadata(self):
        scored = pd.DataFrame([
            {'participant_id': 'P001', 'condition_group': 'Experiment B (Written Afrikaans)', 'language': 'english'},
            {'participant_id': 'P002', 'condition_group': 'Experiment C (Written isiXhosa)', 'language': 'english'},
            {'participant_id': 'P003', 'condition_group': 'Experiment A (Oral English)', 'language': 'afrikaans'},
        ])
        expected = {
            'afrikaans': ['P001'],
            'isixhosa': ['P002'],
            'oral': ['P003'],
        }
        with TemporaryDirectory() as temporary_directory, patch(
            'main.GROUPS_DIR', Path(temporary_directory),
        ):
            for group_key, participant_ids in expected.items():
                _, _, filtered = generate_group_dataset(scored, group_key)
                self.assertEqual(filtered['participant_id'].tolist(), participant_ids)

    def test_filtered_dataset_excludes_sensitive_columns(self):
        scored = pd.DataFrame([
            {
                'participant_id': 'P001',
                'condition_group': 'Experiment C (Written isiXhosa)',
                'linkage_candidate': 'P002',
                'original_phone': '0790000000',
            },
        ])
        with TemporaryDirectory() as temporary_directory, patch(
            'main.GROUPS_DIR', Path(temporary_directory),
        ):
            _, output_path, filtered = generate_group_dataset(scored, 'isixhosa')
            written = pd.read_csv(output_path, dtype=str, keep_default_na=False)

        self.assertNotIn('linkage_candidate', filtered.columns)
        self.assertNotIn('original_phone', filtered.columns)
        self.assertNotIn('linkage_candidate', written.columns)
        self.assertNotIn('original_phone', written.columns)

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

    def test_isixhosa_source_is_parsed_and_scored(self):
        source = next(source for source in SURVEY_SOURCES if source.name == 'SUS_xh')
        self.assertEqual(source.delimiter, ',')
        data = pd.read_csv(
            source.filename,
            dtype=str,
            keep_default_na=False,
            encoding=source.encoding,
            sep=source.delimiter,
        )
        scored = build_scored_data(data, {}, normalize_phone_detail, source)
        self.assertEqual(len(scored), len(data) * 3)
        self.assertTrue((scored['language'] == 'isiXhosa').all())
        self.assertTrue((scored['processing_status'] == 'valid').all())
        self.assertTrue((pd.to_numeric(scored['sus_score']) >= 0).all())


if __name__ == '__main__':
    unittest.main()
