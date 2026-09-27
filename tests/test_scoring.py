from __future__ import annotations

from pathlib import Path
import unittest

import numpy as np

from asl_realtime import embedding_encoder, scoring
from asl_realtime.constants import FEATURE_DIM
from asl_realtime.preprocess import prepare_sequence
from asl_realtime.reference_index import ReferenceEntry, ReferenceIndex
from scripts.evaluate_baseline import load_keypoint_csv


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "baseline_evaluator" / "keypoints"


class ManualBaselineTests(unittest.TestCase):
    def test_golden_formula_values_and_pass_boundary(self) -> None:
        cases = (
            ((0.68, -0.02), 0, False),
            ((0.90, 0.06), 100, True),
            ((0.90, 0.00), 74, False),
            ((0.832, 0.06), 79, False),
            ((0.835, 0.06), 80, True),
        )
        for inputs, expected_score, expected_accepted in cases:
            with self.subTest(inputs=inputs):
                result = scoring.manual_baseline_score(*inputs)
                self.assertEqual(expected_score, result.score)
                self.assertEqual(expected_accepted, result.accepted)
                self.assertEqual("pass" if expected_accepted else "retry", result.decision)

    def test_similarity_078_and_ambiguous_094_boundaries(self) -> None:
        self.assertEqual(63, scoring.manual_baseline_score(0.78, 0.06).score)
        self.assertEqual(63, scoring.manual_baseline_score(0.779999, 0.06).score)

        exact = scoring.manual_baseline_score(0.94, -0.015)
        below_similarity = scoring.manual_baseline_score(0.939999, -0.015)
        below_margin = scoring.manual_baseline_score(0.94, -0.015001)
        self.assertEqual((82, True, True), (exact.score, exact.accepted, exact.ambiguous_high_target))
        self.assertEqual((70, False, False), (below_similarity.score, below_similarity.accepted, below_similarity.ambiguous_high_target))
        self.assertEqual((70, False, False), (below_margin.score, below_margin.accepted, below_margin.ambiguous_high_target))

    def test_non_finite_and_out_of_range_semantic_values_are_rejected(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                scoring.manual_baseline_score(value, 0.0)
        with self.assertRaises(ValueError):
            scoring.manual_baseline_score(1.01, 0.0)
        with self.assertRaises(ValueError):
            scoring.manual_baseline_score(0.8, 2.01)


class FeatureContractTests(unittest.TestCase):
    def test_feature_order_and_metadata_are_frozen(self) -> None:
        self.assertEqual(
            (
                "target_similarity",
                "best_other_similarity",
                "similarity_margin",
                "hand_visibility",
                "motion_energy",
                "motion_span",
                "sequence_completeness",
                "start_position_difference",
                "end_position_difference",
            ),
            scoring.BASE_MODEL_FEATURE_ORDER_V1,
        )
        self.assertEqual(
            set(scoring.BASE_MODEL_FEATURE_ORDER_V1), set(scoring.BASE_MODEL_FEATURE_SPECS_V1)
        )
        for spec in scoring.BASE_MODEL_FEATURE_SPECS_V1.values():
            self.assertTrue(spec.unit)
            self.assertTrue(spec.direction)

    def test_feature_validation_orders_values_and_rejects_bad_ranges(self) -> None:
        row = {
            "target_similarity": 0.9,
            "best_other_similarity": 0.7,
            "similarity_margin": 0.2,
            "hand_visibility": 1.0,
            "motion_energy": 0.02,
            "motion_span": 0.1,
            "sequence_completeness": 1.0,
            "start_position_difference": 0.4,
            "end_position_difference": 0.5,
        }
        self.assertEqual(tuple(row[name] for name in scoring.BASE_MODEL_FEATURE_ORDER_V1), scoring.validate_base_feature_row(row))

        for feature, bad_value in (
            ("target_similarity", 1.1),
            ("hand_visibility", -0.01),
            ("sequence_completeness", 1.01),
            ("motion_span", float("nan")),
            ("end_position_difference", float("inf")),
        ):
            invalid = dict(row)
            invalid[feature] = bad_value
            with self.subTest(feature=feature), self.assertRaises(ValueError):
                scoring.validate_base_feature_row(invalid)

        self.assertIsNone(scoring.validate_trajectory_distance(None))
        with self.assertRaises(ValueError):
            scoring.validate_trajectory_distance(-0.01)


class QualityAndPreparationTests(unittest.TestCase):
    def test_prepared_shape_dtype_and_valid_quality_measurements(self) -> None:
        sequence = load_keypoint_csv(FIXTURE_ROOT / "hello.csv")
        prepared = prepare_sequence(sequence, scoring.TARGET_FRAMES_V1)
        self.assertEqual((32, FEATURE_DIM), prepared.shape)
        self.assertEqual(np.dtype(np.float32), prepared.dtype)
        self.assertTrue(prepared.flags.c_contiguous)

        measurements = scoring.measure_quality(prepared, original_frame_count=len(sequence))
        gate = scoring.quality_gate(measurements)
        self.assertTrue(gate.valid, gate.reasons)
        self.assertEqual(1.0, measurements.hand_visibility)
        self.assertEqual(0.25, measurements.sequence_completeness)
        self.assertGreater(measurements.motion_energy, 0.014)
        self.assertGreater(measurements.motion_span, 0.075)

    def test_quality_gate_rejects_hidden_hands(self) -> None:
        sequence = load_keypoint_csv(FIXTURE_ROOT / "no-hands.csv")
        prepared = prepare_sequence(sequence, scoring.TARGET_FRAMES_V1)
        measurements = scoring.measure_quality(prepared, original_frame_count=len(sequence))
        gate = scoring.quality_gate(measurements)
        self.assertFalse(gate.valid)
        self.assertIn("insufficient_hand_visibility", gate.reasons)
        self.assertIn("insufficient_motion", gate.reasons)

    def test_prepare_rejects_nan_and_infinity(self) -> None:
        sequence = np.zeros((8, FEATURE_DIM), dtype=np.float32)
        for value in (np.nan, np.inf, -np.inf):
            invalid = sequence.copy()
            invalid[0, 0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare_sequence(invalid, scoring.TARGET_FRAMES_V1)


class ReferenceIndexContractTests(unittest.TestCase):
    def test_search_returns_only_similarity_contract_with_correct_best_other(self) -> None:
        entries = [
            ReferenceEntry("HELLO", "hello", "hello-a", 0),
            ReferenceEntry("HELLO", "hello", "hello-b", 1),
            ReferenceEntry("PLEASE", "please", "please-a", 2),
        ]
        index = ReferenceIndex(
            np.asarray([[1.0, 0.0], [0.8, 0.6], [0.0, 1.0]], dtype=np.float32),
            entries,
        )

        result = index.search_target("HELLO", np.asarray([1.0, 0.0], dtype=np.float32))

        self.assertEqual(
            {"target_similarity", "best_other_similarity", "best_other_word", "similarity_margin"},
            set(result),
        )
        self.assertAlmostEqual(1.0, result["target_similarity"])
        self.assertAlmostEqual(0.0, result["best_other_similarity"])
        self.assertEqual("PLEASE", result["best_other_word"])
        self.assertAlmostEqual(1.0, result["similarity_margin"])

    def test_unknown_target_and_non_finite_query_fail(self) -> None:
        entries = [
            ReferenceEntry("HELLO", "hello", "hello", 0),
            ReferenceEntry("PLEASE", "please", "please", 1),
        ]
        index = ReferenceIndex(np.eye(2, dtype=np.float32), entries)
        with self.assertRaises(KeyError):
            index.search_target("NO", np.asarray([1.0, 0.0], dtype=np.float32))
        with self.assertRaises(ValueError):
            index.search_target("HELLO", np.asarray([np.nan, 0.0], dtype=np.float32))

    def test_signclip_dead_path_is_removed(self) -> None:
        self.assertFalse(hasattr(embedding_encoder, "SignCLIPEncoder"))


if __name__ == "__main__":
    unittest.main()
