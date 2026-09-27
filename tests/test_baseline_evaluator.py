from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from asl_realtime import scoring
from asl_realtime.api_server import PracticeAPI
from asl_realtime.embedding_encoder import PoseEmbeddingEncoder
from asl_realtime.preprocess import prepare_sequence
from asl_realtime.reference_index import ReferenceEntry, ReferenceIndex
from scripts import evaluate_baseline
from signcoach_benchmark.manifest import MANIFEST_COLUMNS, write_manifest


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "baseline_evaluator"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.csv"


def build_fixture_index() -> tuple[ReferenceIndex, PoseEmbeddingEncoder]:
    encoder = PoseEmbeddingEncoder(target_frames=scoring.TARGET_FRAMES_V1)
    embeddings = []
    entries = []
    for index, (word, filename) in enumerate((("HELLO", "hello.csv"), ("PLEASE", "please.csv"))):
        sequence = evaluate_baseline.load_keypoint_csv(FIXTURE_ROOT / "keypoints" / filename)
        prepared = prepare_sequence(sequence, scoring.TARGET_FRAMES_V1)
        embeddings.append(encoder.encode_prepared_sequence(prepared))
        entries.append(ReferenceEntry(word, word.lower(), filename, index))
    return ReferenceIndex(np.stack(embeddings), entries), encoder


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def read_csv_with_columns(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return tuple(reader.fieldnames or ()), list(reader)


def semantic_csv_rows(path: Path) -> list[dict[str, str]]:
    timing_columns = {
        "prepare_ms",
        "quality_ms",
        "similarity_ms",
        "reference_search_ms",
        "scoring_ms",
        "total_ms",
        "latency_ms",
    }
    return [
        {key: value for key, value in row.items() if key not in timing_columns}
        for row in read_csv(path)
    ]


class BaselineEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reference_index, self.encoder = build_fixture_index()

    def test_evaluator_excludes_unreviewed_reports_groups_and_writes_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "results"
            with patch(
                "scripts.evaluate_baseline.prepare_sequence",
                wraps=evaluate_baseline.prepare_sequence,
            ) as prepare, patch.object(
                self.reference_index,
                "search_target",
                wraps=self.reference_index.search_target,
            ) as search:
                summary = evaluate_baseline.evaluate_manifest(
                    MANIFEST_PATH,
                    output,
                    self.reference_index,
                    repeats=1,
                    encoder=self.encoder,
                )

            self.assertEqual(5, prepare.call_count)
            self.assertEqual(4, search.call_count)
            self.assertNotIn("THANKYOU", [call.args[0] for call in search.call_args_list])
            self.assertEqual(6, summary["manifest_row_count"])
            self.assertEqual(5, summary["evaluated_sample_count"])
            self.assertEqual({"total_count": 1, "unreviewed_count": 1}, summary["excluded"])

            expected_counts = {
                "positive": 2,
                "hard_negative": 1,
                "random_negative": 1,
                "invalid": 1,
            }
            for group, expected_count in expected_counts.items():
                with self.subTest(group=group):
                    self.assertEqual("available", summary["groups"][group]["status"])
                    self.assertEqual(expected_count, summary["groups"][group]["sample_count"])
            self.assertEqual(1.0, summary["groups"]["positive"]["acceptance_rate"])
            self.assertEqual(0.0, summary["groups"]["hard_negative"]["acceptance_rate"])
            self.assertEqual(0.0, summary["groups"]["random_negative"]["acceptance_rate"])
            self.assertEqual(1.0, summary["groups"]["invalid"]["rejection_rate"])
            self.assertEqual("available", summary["semantic_auroc"]["status"])
            self.assertEqual(1.0, summary["semantic_auroc"]["value"])

            for filename in ("summary.json", "sample_results.csv", "per_word.csv", "confusions.csv"):
                self.assertTrue((output / filename).is_file(), filename)
            columns, sample_results = read_csv_with_columns(output / "sample_results.csv")
            self.assertEqual(5, len(sample_results))
            self.assertEqual(evaluate_baseline.SAMPLE_RESULT_COLUMNS, columns)
            with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as file:
                manifest_by_id = {row["sample_id"]: row for row in csv.DictReader(file)}
            copied_fields = (
                "signer_id",
                "source",
                "split",
                "variant_status",
                "source_sample_id",
                "anomaly_type",
            )
            for result in sample_results:
                source = manifest_by_id[result["sample_id"]]
                with self.subTest(sample_id=result["sample_id"]):
                    self.assertEqual(
                        {field: source[field] for field in copied_fields},
                        {field: result[field] for field in copied_fields},
                    )
            self.assertFalse(any(row["variant_status"] == "unreviewed" for row in sample_results))
            self.assertNotIn("synthetic:unreviewed:thankyou", {row["sample_id"] for row in sample_results})
            invalid = next(row for row in sample_results if row["sample_type"] == "invalid")
            self.assertEqual("false", invalid["quality_valid"])
            self.assertEqual("rerecord", invalid["decision"])
            self.assertEqual("", invalid["target_similarity"])
            self.assertEqual("", invalid["trajectory_distance"])

            per_word = read_csv(output / "per_word.csv")
            canonical_words = tuple(word["word"] for word in per_word)
            self.assertEqual(30, len(per_word))
            self.assertEqual(
                tuple(word.target_word for word in evaluate_baseline.load_config().words),
                canonical_words,
            )
            allowed = set(canonical_words)
            confusions = read_csv(output / "confusions.csv")
            self.assertTrue(confusions)
            self.assertTrue(
                all(row["target_word"] in allowed and row["confused_with"] in allowed for row in confusions)
            )

            latency = summary["latency_ms"]
            for field in (
                "total_p50",
                "total_p95",
                "similarity_p50",
                "similarity_p95",
                "reference_search_p50",
                "reference_search_p95",
            ):
                self.assertIsNotNone(latency[field])
            self.assertEqual(60, latency["focused_reference_search_target_ms"])
            self.assertEqual("fixture_measurement_only", latency["measurement_scope"])

    def test_empty_groups_and_single_class_auroc_are_not_available(self) -> None:
        with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as file:
            positive = next(row for row in csv.DictReader(file) if row["sample_type"] == "positive")
        positive = dict(positive)
        positive["video_path"] = str((FIXTURE_ROOT / positive["video_path"]).resolve())
        positive["keypoints_path"] = str((FIXTURE_ROOT / positive["keypoints_path"]).resolve())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.csv"
            write_manifest(manifest, [positive])
            summary = evaluate_baseline.evaluate_manifest(
                manifest,
                root / "results",
                self.reference_index,
                repeats=1,
                encoder=self.encoder,
            )

            self.assertEqual("available", summary["groups"]["positive"]["status"])
            for group in ("hard_negative", "random_negative", "invalid"):
                self.assertEqual("not_available", summary["groups"][group]["status"])
                self.assertIsNone(summary["groups"][group]["acceptance_rate"])
                self.assertEqual(0, summary["groups"][group]["sample_count"])
            self.assertEqual(
                {"status": "not_available", "value": None, "positive_count": 1, "negative_count": 0},
                summary["semantic_auroc"],
            )

    def test_asl_citizen_lookup_mapping_does_not_change_product_labels(self) -> None:
        with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as file:
            row = next(row for row in csv.DictReader(file) if row["sample_type"] == "positive")
        row = dict(row)
        row.update(
            {
                "sample_id": "synthetic:positive:mom",
                "target_word": "MOM",
                "performed_word": "MOM",
                "source_sample_id": "mom-positive",
                "video_path": str((FIXTURE_ROOT / row["video_path"]).resolve()),
                "keypoints_path": str((FIXTURE_ROOT / row["keypoints_path"]).resolve()),
            }
        )
        mapped_index = ReferenceIndex(
            self.reference_index.embeddings.copy(),
            [
                ReferenceEntry("MOTHER", "mother", "mother.csv", 0),
                ReferenceEntry("HELLO", "hello", "hello.csv", 1),
            ],
        )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.csv"
            write_manifest(manifest, [row])
            with patch.object(mapped_index, "search_target", wraps=mapped_index.search_target) as search:
                evaluate_baseline.evaluate_manifest(
                    manifest,
                    root / "results",
                    mapped_index,
                    repeats=1,
                    encoder=self.encoder,
                )
            result = read_csv(root / "results" / "sample_results.csv")[0]

        search.assert_called_once()
        self.assertEqual("MOTHER", search.call_args.args[0])
        self.assertEqual("MOM", result["target_word"])
        self.assertEqual("MOM", result["performed_word"])

    def test_repeated_runs_have_identical_non_timing_outputs_and_zero_instability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first"
            second = root / "second"
            first_summary = evaluate_baseline.evaluate_manifest(
                MANIFEST_PATH,
                first,
                self.reference_index,
                repeats=2,
                encoder=self.encoder,
            )
            second_summary = evaluate_baseline.evaluate_manifest(
                MANIFEST_PATH,
                second,
                self.reference_index,
                repeats=2,
                encoder=self.encoder,
            )

            self.assertEqual(0.0, first_summary["score_stability"]["mean_score_stddev"])
            self.assertEqual(0.0, first_summary["score_stability"]["max_score_stddev"])
            first_without_latency = {key: value for key, value in first_summary.items() if key != "latency_ms"}
            second_without_latency = {key: value for key, value in second_summary.items() if key != "latency_ms"}
            self.assertEqual(first_without_latency, second_without_latency)
            self.assertEqual(
                semantic_csv_rows(first / "sample_results.csv"),
                semantic_csv_rows(second / "sample_results.csv"),
            )
            self.assertEqual((first / "per_word.csv").read_text(), (second / "per_word.csv").read_text())
            self.assertEqual((first / "confusions.csv").read_text(), (second / "confusions.csv").read_text())

            identity_fields = (
                "signer_id",
                "source",
                "split",
                "variant_status",
                "source_sample_id",
                "anomaly_type",
            )
            rows_by_sample: dict[str, list[dict[str, str]]] = {}
            for row in read_csv(first / "sample_results.csv"):
                rows_by_sample.setdefault(row["sample_id"], []).append(row)
            for sample_id, repeated_rows in rows_by_sample.items():
                self.assertEqual(2, len(repeated_rows), sample_id)
                self.assertEqual(
                    {field: repeated_rows[0][field] for field in identity_fields},
                    {field: repeated_rows[1][field] for field in identity_fields},
                )

    def test_p3_schema_distinguishes_split_roles_and_filters_one_row_per_valid_semantic_sample(self) -> None:
        with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as file:
            source_rows = [
                row
                for row in csv.DictReader(file)
                if row["sample_type"] in {"positive", "hard_negative"}
                and row["variant_status"] != "unreviewed"
            ][:3]
        for row, split in zip(source_rows, ("train", "val", "test")):
            row["split"] = split
            row["video_path"] = str((FIXTURE_ROOT / row["video_path"]).resolve())
            row["keypoints_path"] = str((FIXTURE_ROOT / row["keypoints_path"]).resolve())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.csv"
            write_manifest(manifest, source_rows)
            evaluate_baseline.evaluate_manifest(
                manifest,
                root / "results",
                self.reference_index,
                repeats=2,
                encoder=self.encoder,
            )
            columns, results = read_csv_with_columns(root / "results" / "sample_results.csv")

        self.assertIn("split", columns)
        p3_rows = [
            row
            for row in results
            if row["repeat_index"] == "0"
            and row["quality_valid"] == "true"
            and row["sample_type"] != "invalid"
            and row["variant_status"] != "unreviewed"
            and row["expected_pass"] != ""
        ]
        self.assertEqual(3, len(p3_rows))
        self.assertEqual({"train", "val", "test"}, {row["split"] for row in p3_rows})
        self.assertEqual(len(p3_rows), len({row["sample_id"] for row in p3_rows}))

    def test_api_and_evaluator_call_same_manual_scorer_and_prepare_once_per_attempt(self) -> None:
        sequence = evaluate_baseline.load_keypoint_csv(FIXTURE_ROOT / "keypoints" / "hello.csv")
        api = PracticeAPI.__new__(PracticeAPI)
        api.recognizer = None
        api.reference_index = self.reference_index
        api.embedding_encoder = self.encoder
        api.log_similarity_result = Mock()

        original_scorer = scoring.manual_baseline_score
        with patch(
            "asl_realtime.scoring.manual_baseline_score", wraps=original_scorer
        ) as shared_scorer, patch(
            "asl_realtime.api_server.prepare_sequence", wraps=prepare_sequence
        ) as api_prepare:
            api_result, _ = api.score_sequence("session", "HELLO", sequence)
            with tempfile.TemporaryDirectory() as temp:
                evaluate_baseline.evaluate_manifest(
                    MANIFEST_PATH,
                    Path(temp),
                    self.reference_index,
                    repeats=1,
                    encoder=self.encoder,
                )

        self.assertTrue(api_result["decision"] == "pass")
        self.assertEqual(1, api_prepare.call_count)
        self.assertEqual(5, shared_scorer.call_count)

    def test_invalid_quality_skips_api_search_and_semantic_scoring(self) -> None:
        sequence = evaluate_baseline.load_keypoint_csv(FIXTURE_ROOT / "keypoints" / "no-hands.csv")
        api = PracticeAPI.__new__(PracticeAPI)
        api.recognizer = None
        api.reference_index = self.reference_index
        api.embedding_encoder = self.encoder
        api.log_similarity_result = Mock()

        with patch.object(self.reference_index, "search_target", wraps=self.reference_index.search_target) as search, patch(
            "asl_realtime.scoring.manual_baseline_score", wraps=scoring.manual_baseline_score
        ) as scorer:
            result, _ = api.score_sequence("session", "THANKYOU", sequence)

        self.assertFalse(result["quality_valid"])
        self.assertIsNone(result["score"])
        search.assert_not_called()
        scorer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
