from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from asl_realtime import calibration as c
from asl_realtime.scoring import BASE_MODEL_FEATURE_ORDER_V1

FIXTURE = Path(__file__).parent / "fixtures" / "calibration_rows.csv"
ROOT = Path(__file__).resolve().parents[1]


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        with FIXTURE.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            self.columns = reader.fieldnames
            self.raw = list(reader)
        self.parts = c.read_partitions(FIXTURE)

    def read_modified(self, rows):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample_results.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=self.columns)
                writer.writeheader()
                writer.writerows(rows)
            return c.read_partitions(path)

    def artifact(self):
        train, val = self.parts["train"], self.parts["val"]
        pipeline = c.fit_pipeline(train)
        threshold, _ = c.select_threshold(val, c._probabilities(pipeline, val))
        return c.freeze_artifact(pipeline, threshold, train, val, "calibrator-synthetic-smoke", True)

    def test_exact_eligibility_and_p2_repeats(self):
        self.assertEqual({"train": 4, "val": 4, "test": 4}, {k: len(v) for k, v in self.parts.items()})
        for rows in self.parts.values():
            self.assertEqual(len(rows), len({r["sample_id"] for r in rows}))
            for row in rows:
                self.assertEqual(0, row["repeat_index"])
                self.assertTrue(row["quality_valid"])
                self.assertIn(row["sample_type"], c.SEMANTIC_TYPES)
                self.assertNotEqual("unreviewed", row["variant_status"])
                self.assertIs(type(row["expected_pass"]), bool)
        # Each excluded category works independently, even with valid features.
        for change in ({"repeat_index": "2"}, {"quality_valid": "false"},
                       {"sample_type": "invalid"}, {"variant_status": "unreviewed"}):
            rows = copy.deepcopy(self.raw)
            rows.append(dict(rows[0], sample_id="synthetic:excluded", **change))
            self.assertEqual(self.parts, self.read_modified(rows))

    def test_blank_performed_word_exclusions_preserve_partitions_and_hash(self):
        invalid = [row for row in self.raw if row["sample_type"] == "invalid"]
        self.assertEqual({"train", "val", "test"}, {row["split"] for row in invalid})
        self.assertTrue(all(row["performed_word"] == "" for row in invalid))
        included_ids = {row["sample_id"] for rows in self.parts.values() for row in rows}
        self.assertTrue(included_ids.isdisjoint(row["sample_id"] for row in invalid))
        for word in ("", "PLEASE"):
            rows = copy.deepcopy(self.raw)
            for row in rows:
                if row["sample_type"] == "invalid" or row["variant_status"] == "unreviewed":
                    row["performed_word"] = word
            parts = self.read_modified(rows)
            self.assertEqual(self.parts, parts)
            self.assertEqual(c.training_data_version(self.parts["train"], self.parts["val"]),
                             c.training_data_version(parts["train"], parts["val"]))

    def test_eligible_semantic_rows_require_performed_word_even_for_repeats(self):
        for index, row in enumerate(self.raw):
            if (row["sample_type"] in c.SEMANTIC_TYPES
                    and row["variant_status"] != "unreviewed"
                    and row["expected_pass"] and row["quality_valid"] == "true"):
                with self.subTest(sample=row["sample_id"], repeat=row["repeat_index"]):
                    rows = copy.deepcopy(self.raw)
                    rows[index]["performed_word"] = ""
                    with self.assertRaisesRegex(ValueError, "requires performed_word"):
                        self.read_modified(rows)

    def test_canonical_words_required_even_for_excluded_rows(self):
        for index, row in enumerate(self.raw):
            for key in ("target_word", "performed_word"):
                for word in ("MOTHER", "NOT_A_WORD", "hello", " "):
                    with self.subTest(sample=row["sample_id"], key=key, word=word):
                        rows = copy.deepcopy(self.raw)
                        rows[index][key] = word
                        with self.assertRaisesRegex(ValueError, f"{key} outside fixed"):
                            self.read_modified(rows)
            rows = copy.deepcopy(self.raw)
            rows[index]["target_word"] = ""
            with self.assertRaisesRegex(ValueError, "target_word outside fixed"):
                self.read_modified(rows)

    def test_schema_split_signer_duplicates_labels_words_features_fail(self):
        changes = [
            {"split": "unknown"}, {"signer_id": "synthetic-val"},
            {"target_word": "NOT_A_WORD"}, {"performed_word": "MOTHER"},
            {"expected_pass": ""}, {"expected_pass": "yes"},
            {"quality_valid": "1"}, {"repeat_index": "-1"},
            {"hand_visibility": "1.01"}, {"motion_energy": "nan"},
            {"target_similarity": "inf"}, {"end_position_difference": "-1"},
            {"sample_type": "other"}, {"source": ""},
        ]
        for change in changes:
            with self.subTest(change=change):
                rows = copy.deepcopy(self.raw)
                rows[0].update(change)
                with self.assertRaises(ValueError):
                    self.read_modified(rows)
        with self.assertRaises(ValueError):
            self.read_modified(self.raw + [self.raw[0]])
        for split in ("train", "val", "test"):
            with self.subTest(split=split), self.assertRaises(ValueError):
                self.read_modified([r for r in self.raw if r["split"] != split])
        for split, group in (("train", "positive"), ("val", "positive"), ("val", "hard_negative")):
            with self.subTest(split=split, group=group), self.assertRaises(ValueError):
                self.read_modified([r for r in self.raw if not (r["split"] == split and r["sample_type"] == group)])
        self.columns = [key for key in self.columns if key != "source"]
        with self.assertRaises(ValueError):
            self.read_modified([{key: value for key, value in r.items() if key != "source"} for r in self.raw])

    def test_pipeline_exact_parameters_and_positive_class(self):
        pipeline = c.fit_pipeline(self.parts["train"])
        self.assertEqual(["scaler", "logistic"], list(pipeline.named_steps))
        self.assertEqual(StandardScaler().get_params(), pipeline["scaler"].get_params())
        self.assertEqual(LogisticRegression(random_state=42, max_iter=1000).get_params(), pipeline["logistic"].get_params())
        np.testing.assert_array_equal([False, True], pipeline.classes_)
        self.assertEqual(len(BASE_MODEL_FEATURE_ORDER_V1), pipeline.n_features_in_)
        with self.assertRaises(ValueError):
            c.fit_pipeline(self.parts["test"])
        with self.assertRaises(ValueError):
            c.select_threshold(self.parts["test"], [.5] * 4)

    def test_threshold_constraint_and_ties(self):
        positive = self.parts["val"][0]
        hard = self.parts["val"][2]
        # 10 hard negatives permit one acceptance. Acceptance dominates FAR;
        # among equal acceptance, FAR dominates threshold; final tie goes high.
        rows = [positive, dict(positive), *[dict(hard) for _ in range(10)]]
        threshold, report = c.select_threshold(rows, [.8, .6, .7, *([.2] * 9)])
        self.assertEqual(.6, threshold)
        self.assertEqual(1, report["positive_acceptance_rate"])
        self.assertEqual(.1, report["reviewed_hard_negative_false_acceptance_rate"])
        threshold, report = c.select_threshold(rows, [.8, .8, .7, *([.2] * 9)])
        self.assertEqual(.8, threshold)
        self.assertEqual(0, report["reviewed_hard_negative_false_acceptance_rate"])
        # A random negative creates another boundary with unchanged primary rates.
        random = self.parts["val"][3]
        threshold, _ = c.select_threshold([positive, hard, random], [.9, .1, .6])
        self.assertEqual(.9, threshold)
        threshold, report = c.select_threshold([positive, hard], [.2, .9])
        self.assertEqual(1, threshold)
        self.assertEqual(0, report["positive_acceptance_rate"])
        self.assertEqual(0, report["reviewed_hard_negative_false_acceptance_rate"])
        with self.assertRaises(ValueError):
            c.select_threshold([positive, hard], [.2, 1])
        for values in ([float("nan"), .2], [1.1, .2], [.2]):
            with self.assertRaises(ValueError):
                c.select_threshold([positive, hard], values)
        for rows in ([positive], [hard], [positive, dict(hard, variant_status="unreviewed")]):
            with self.assertRaises(ValueError):
                c.select_threshold(rows, [.5] * len(rows))

    def test_hash_canonical_and_test_independent(self):
        train, val = self.parts["train"], self.parts["val"]
        first = c.training_data_version(train, val)
        self.assertEqual(first, c.training_data_version(train[::-1], val[::-1]))
        changed = copy.deepcopy(train)
        changed[0].update(score=0, accepted=False, latency_ms=900, absolute_path="C:/elsewhere")
        self.assertEqual(first, c.training_data_version(changed, val))
        changed[0][BASE_MODEL_FEATURE_ORDER_V1[0]] -= .01
        self.assertNotEqual(first, c.training_data_version(changed, val))
        self.assertEqual(self.artifact()["training_data_version"], self.artifact()["training_data_version"])
        with self.assertRaises(ValueError):
            c.training_data_version(train, self.parts["test"])

    def test_loader_rejects_corruption_and_synthetic_production_disguise(self):
        original = self.artifact()
        mutations = [
            {"feature_order": tuple(reversed(BASE_MODEL_FEATURE_ORDER_V1))},
            {"pass_threshold": -1}, {"pass_threshold": float("nan")}, {"pass_threshold": 1.1},
            {"model_version": "calibrator-v1"}, {"model_version": "unknown"},
            {"synthetic_smoke": False, "model_version": "calibrator-v1"},
            {"synthetic_smoke": False, "synthetic_markers": False, "model_version": "calibrator-v1"},
            {"schema_version": 2}, {"sklearn_version": "0"}, {"training_data_version": "bad"},
            {"quality_thresholds": {}}, {"train": {}}, {"benchmark_label": "learner_accuracy"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.joblib"
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    joblib.dump(dict(original, **mutation), path)
                    with self.assertRaises(ValueError):
                        c.load_calibrator(path)
            broken = copy.deepcopy(original)
            broken["pipeline"].steps.reverse()
            joblib.dump(broken, path)
            with self.assertRaises(ValueError):
                c.load_calibrator(path)
            broken = copy.deepcopy(original)
            broken["pipeline"]["logistic"].coef_[0, 0] = np.inf
            joblib.dump(broken, path)
            with self.assertRaises(ValueError):
                c.load_calibrator(path)
            broken = copy.deepcopy(original)
            broken["pipeline"]["logistic"].coef_ = np.zeros((1, 2))
            joblib.dump(broken, path)
            with self.assertRaises(ValueError):
                c.load_calibrator(path)
            joblib.dump(original, path)
            loaded = c.load_calibrator(path)
            result = c.predict_match(loaded, self.parts["test"][0])
            self.assertEqual(int(round(100 * result["match_probability"])), result["score"])
            loaded["pass_threshold"] = result["match_probability"]
            self.assertTrue(c.predict_match(loaded, self.parts["test"][0])["accepted"])
            with self.assertRaises(ValueError):
                c.predict_match(loaded, dict(self.parts["test"][0], motion_energy=float("nan")))

    def test_partition_spies_and_freeze_before_single_test_prediction(self):
        events = []
        fit, select, load, probabilities = c.fit_pipeline, c.select_threshold, c.load_calibrator, c._probabilities
        def fit_spy(rows):
            self.assertEqual({"train"}, {r["split"] for r in rows})
            events.append("fit")
            return fit(rows)
        def select_spy(rows, probs):
            self.assertEqual({"val"}, {r["split"] for r in rows})
            events.append("select")
            return select(rows, probs)
        def load_spy(path):
            result = load(path)
            events.append("reload")
            return result
        def probability_spy(pipeline, rows):
            split = rows[0]["split"]
            self.assertEqual({split}, {r["split"] for r in rows})
            events.append(f"predict-{split}")
            return probabilities(pipeline, rows)
        with tempfile.TemporaryDirectory() as temp, patch.object(c, "fit_pipeline", side_effect=fit_spy), patch.object(c, "select_threshold", side_effect=select_spy), patch.object(c, "load_calibrator", side_effect=load_spy), patch.object(c, "_probabilities", side_effect=probability_spy):
            root = Path(temp)
            c.run_calibration(FIXTURE, root / "smoke.joblib", root / "reports", "calibrator-synthetic-smoke", True)
        self.assertEqual(["fit", "predict-val", "select", "reload", "predict-test"], events)

    def test_cli_twice_outputs_identical_and_baseline_uses_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for run in ("first", "second"):
                command = [sys.executable, "scripts/train_calibrator.py", "--features", str(FIXTURE),
                           "--artifact", str(root / run / "smoke.joblib"), "--report-dir", str(root / run / "reports"),
                           "--model-version", "calibrator-synthetic-smoke", "--synthetic-smoke"]
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
            names = {"metadata.json", "validation_metrics.json", "test_metrics.json", "sample_predictions.csv", "baseline_comparison.json"}
            self.assertEqual(names, {p.name for p in (root / "first" / "reports").iterdir()})
            for name in names:
                self.assertEqual((root / "first" / "reports" / name).read_bytes(), (root / "second" / "reports" / name).read_bytes())
            comparison = json.loads((root / "first" / "reports" / "baseline_comparison.json").read_text())
            self.assertEqual(1, comparison["test"]["baseline"]["positive_acceptance_rate"])
            self.assertIsNone(comparison["test"]["baseline"]["threshold"])
            # Change only test rows: fitted metadata and validation must stay frozen.
            changed = copy.deepcopy(self.raw)
            for row in changed:
                if row["split"] == "test" and row["quality_valid"] == "true":
                    row.update(target_similarity="0.1", score="0", accepted="false")
            path = root / "changed.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=self.columns)
                writer.writeheader()
                writer.writerows(changed)
            c.run_calibration(path, root / "changed.joblib", root / "changed", "calibrator-synthetic-smoke", True)
            for name in ("metadata.json", "validation_metrics.json"):
                self.assertEqual((root / "first" / "reports" / name).read_bytes(), (root / "changed" / name).read_bytes())
            comparison = json.loads((root / "changed" / "baseline_comparison.json").read_text())
            self.assertEqual(0, comparison["test"]["baseline"]["positive_acceptance_rate"])

    def test_single_class_auroc_unavailable(self):
        result = c.metrics([self.parts["val"][0]], [.8], .7)
        self.assertIsNone(result["auroc"])
        self.assertIsNone(result["random_negative_false_acceptance_rate"])


if __name__ == "__main__":
    unittest.main()
