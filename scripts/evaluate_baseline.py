"""Evaluate the shared Phase 1 manual baseline on a validated manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from time import perf_counter_ns
from typing import Iterable

import numpy as np
from sklearn.metrics import roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from asl_realtime import scoring  # noqa: E402
from asl_realtime.constants import FEATURE_DIM, FEATURE_LANDMARK_COUNT  # noqa: E402
from asl_realtime.embedding_encoder import PoseEmbeddingEncoder  # noqa: E402
from asl_realtime.preprocess import prepare_sequence  # noqa: E402
from asl_realtime.reference_index import ReferenceIndex  # noqa: E402
from signcoach_benchmark.config import load_config  # noqa: E402
from signcoach_benchmark.manifest import validate_manifest  # noqa: E402


GROUPS = ("positive", "hard_negative", "random_negative", "invalid")
FEATURE_ROW_COLUMNS = (
    "sample_id",
    *scoring.BASE_MODEL_FEATURE_ORDER_V1,
    "trajectory_distance",
    "latency_ms",
    "repeat_index",
)
SAMPLE_RESULT_COLUMNS = (
    "sample_id",
    "target_word",
    "performed_word",
    "signer_id",
    "source",
    "split",
    "sample_type",
    "expected_pass",
    "variant_status",
    "source_sample_id",
    "anomaly_type",
    "repeat_index",
    "quality_valid",
    "quality_reasons",
    "decision",
    "accepted",
    "score",
    "nearest_confusion",
    *scoring.BASE_MODEL_FEATURE_ORDER_V1,
    "trajectory_distance",
    "prepare_ms",
    "quality_ms",
    "similarity_ms",
    "reference_search_ms",
    "scoring_ms",
    "total_ms",
    "latency_ms",
)
# P3 selects repeat_index == 0, quality_valid == true, sample_type != invalid,
# variant_status != unreviewed, and nonblank expected_pass from this sole row output.
# Train fits, val selects the threshold, and test is opened once only after the
# feature list, threshold, and model version are frozen. P1 validates signer splits.
PER_WORD_COLUMNS = (
    "word",
    "positive_count",
    "positive_acceptance_rate",
    "negative_count",
    "false_acceptance_rate",
    "invalid_count",
    "invalid_rejection_rate",
)
CONFUSION_COLUMNS = ("target_word", "confused_with", "count")


def _milliseconds(start_ns: int, end_ns: int) -> float:
    return round((end_ns - start_ns) / 1_000_000, 6)


def _resolve_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path


def load_keypoint_csv(path: Path) -> np.ndarray:
    """Load readable sparse rows: frame, landmark_index, x, y, z."""

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        expected_columns = ("frame", "landmark_index", "x", "y", "z")
        if tuple(reader.fieldnames or ()) != expected_columns:
            raise ValueError(f"{path}: expected columns {expected_columns}")
        raw_rows = list(reader)
    if not raw_rows:
        raise ValueError(f"{path}: keypoint file is empty")

    parsed: list[tuple[int, int, float, float, float]] = []
    frame_values: set[int] = set()
    seen: set[tuple[int, int]] = set()
    for row_number, row in enumerate(raw_rows, start=2):
        try:
            frame = int(row["frame"])
            landmark_index = int(row["landmark_index"])
            xyz = tuple(float(row[axis]) for axis in ("x", "y", "z"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path}:{row_number}: invalid numeric value") from exc
        if frame < 0:
            raise ValueError(f"{path}:{row_number}: frame must be non-negative")
        if not 0 <= landmark_index < FEATURE_LANDMARK_COUNT:
            raise ValueError(f"{path}:{row_number}: landmark_index out of range")
        if not np.all(np.isfinite(xyz)):
            raise ValueError(f"{path}:{row_number}: coordinates must be finite")
        key = (frame, landmark_index)
        if key in seen:
            raise ValueError(f"{path}:{row_number}: duplicate frame/landmark row")
        seen.add(key)
        frame_values.add(frame)
        parsed.append((frame, landmark_index, *xyz))

    frames = sorted(frame_values)
    frame_to_index = {frame: index for index, frame in enumerate(frames)}
    sequence = np.zeros((len(frames), FEATURE_LANDMARK_COUNT, 3), dtype=np.float32)
    for frame, landmark_index, x, y, z in parsed:
        sequence[frame_to_index[frame], landmark_index] = (x, y, z)
    return sequence.reshape(len(frames), FEATURE_DIM)


def _read_manifest_rows(manifest_path: Path) -> list[dict[str, str]]:
    report = validate_manifest(load_config(), manifest_path)
    if not report.valid:
        issues = "\n".join(issue.format() for issue in report.issues)
        raise ValueError(f"Manifest failed P1 validation:\n{issues}")
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, columns: Iterable[str], rows: Iterable[dict]) -> None:
    materialized = list(rows)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=tuple(columns), lineterminator="\n")
        writer.writeheader()
        writer.writerows(materialized)


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    return round(float(np.percentile(np.asarray(values, dtype=np.float64), percentile)), 6)


def _group_summary(rows: list[dict]) -> dict:
    sample_count = len(rows)
    accepted_count = sum(bool(row["accepted"]) for row in rows)
    rejected_count = sample_count - accepted_count
    return {
        "status": "available" if sample_count else "not_available",
        "sample_count": sample_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "acceptance_rate": _rate(accepted_count, sample_count),
        "rejection_rate": _rate(rejected_count, sample_count),
    }


def _primary_rows(results: list[dict]) -> list[dict]:
    return [row for row in results if row["repeat_index"] == 0]


def _build_per_word(primary: list[dict], words: tuple[str, ...]) -> list[dict]:
    rows: list[dict] = []
    for word in words:
        word_rows = [row for row in primary if row["target_word"] == word]
        positives = [row for row in word_rows if row["sample_type"] == "positive"]
        negatives = [
            row for row in word_rows if row["sample_type"] in {"hard_negative", "random_negative"}
        ]
        invalid = [row for row in word_rows if row["sample_type"] == "invalid"]
        rows.append(
            {
                "word": word,
                "positive_count": len(positives),
                "positive_acceptance_rate": _rate(
                    sum(bool(row["accepted"]) for row in positives), len(positives)
                ),
                "negative_count": len(negatives),
                "false_acceptance_rate": _rate(
                    sum(bool(row["accepted"]) for row in negatives), len(negatives)
                ),
                "invalid_count": len(invalid),
                "invalid_rejection_rate": _rate(
                    sum(not bool(row["accepted"]) for row in invalid), len(invalid)
                ),
            }
        )
    return rows


def _build_confusions(primary: list[dict], words: tuple[str, ...]) -> list[dict]:
    allowed = set(words)
    counts: dict[tuple[str, str], int] = {}
    for row in primary:
        confused_with = row["nearest_confusion"]
        if (
            row["quality_valid"]
            and not row["accepted"]
            and confused_with in allowed
            and confused_with != row["target_word"]
        ):
            key = (row["target_word"], confused_with)
            counts[key] = counts.get(key, 0) + 1
    return [
        {"target_word": target, "confused_with": confused, "count": count}
        for (target, confused), count in sorted(counts.items())
    ]


def _build_stability(results: list[dict]) -> dict:
    scores_by_sample: dict[str, list[float]] = {}
    for row in results:
        scores_by_sample.setdefault(row["sample_id"], []).append(float(row["score"]))
    deviations = [float(np.std(scores, ddof=0)) for scores in scores_by_sample.values()]
    return {
        "sample_count": len(deviations),
        "repeat_count": max((len(scores) for scores in scores_by_sample.values()), default=0),
        "mean_score_stddev": round(float(np.mean(deviations)), 6) if deviations else None,
        "max_score_stddev": round(max(deviations), 6) if deviations else None,
    }


def _semantic_auroc(primary: list[dict]) -> dict:
    semantic = [
        row
        for row in primary
        if row["sample_type"] in {"positive", "hard_negative", "random_negative"}
    ]
    labels = [1 if row["expected_pass"] else 0 for row in semantic]
    positive_count = sum(labels)
    negative_count = len(labels) - positive_count
    if not positive_count or not negative_count:
        return {
            "status": "not_available",
            "value": None,
            "positive_count": positive_count,
            "negative_count": negative_count,
        }
    value = float(roc_auc_score(labels, [float(row["score"]) for row in semantic]))
    return {
        "status": "available",
        "value": round(value, 6),
        "positive_count": positive_count,
        "negative_count": negative_count,
    }


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def evaluate_manifest(
    manifest_path: Path,
    output_dir: Path,
    reference_index: ReferenceIndex,
    *,
    repeats: int = 2,
    encoder: PoseEmbeddingEncoder | None = None,
) -> dict:
    """Run the baseline and write deterministic JSON/CSV artifacts."""

    if repeats <= 0:
        raise ValueError("repeats must be positive")
    manifest_path = manifest_path.resolve()
    output_dir = output_dir.resolve()
    rows = _read_manifest_rows(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config()
    reference_word_by_target = {
        word.target_word: word.asl_citizen_word for word in config.words
    }
    target_by_reference_word = {
        word.asl_citizen_word: word.target_word for word in config.words
    }
    words = tuple(word.target_word for word in config.words)
    encoder = encoder or PoseEmbeddingEncoder(target_frames=scoring.TARGET_FRAMES_V1)
    if encoder.target_frames != scoring.TARGET_FRAMES_V1:
        raise ValueError(f"Phase 1 evaluator requires {scoring.TARGET_FRAMES_V1} target frames")

    excluded = [
        row
        for row in rows
        if row["variant_status"] == "unreviewed" or not row["expected_pass"].strip()
    ]
    included = [row for row in rows if row not in excluded]
    results: list[dict] = []
    for manifest_row in included:
        keypoints_value = manifest_row["keypoints_path"].strip()
        if not keypoints_value:
            raise ValueError(f"{manifest_row['sample_id']}: truth-labeled row requires keypoints_path")
        keypoints_path = _resolve_path(keypoints_value, manifest_path)
        sequence = load_keypoint_csv(keypoints_path)

        for repeat_index in range(repeats):
            total_start = perf_counter_ns()
            stage_start = total_start
            prepared = prepare_sequence(sequence, scoring.TARGET_FRAMES_V1)
            prepare_end = perf_counter_ns()

            measurements = scoring.measure_quality(prepared, original_frame_count=len(sequence))
            gate = scoring.quality_gate(measurements)
            quality_end = perf_counter_ns()

            target_similarity = None
            best_other_similarity = None
            similarity_margin = None
            nearest_confusion = None
            similarity_end = quality_end
            search_start = quality_end
            search_end = quality_end
            scoring_end = similarity_end
            if gate.valid:
                embedding = encoder.encode_prepared_sequence(prepared)
                search_start = perf_counter_ns()
                search = reference_index.search_target(
                    reference_word_by_target[manifest_row["target_word"]], embedding
                )
                search_end = perf_counter_ns()
                similarity_end = search_end
                target_similarity = search["target_similarity"]
                best_other_similarity = search["best_other_similarity"]
                similarity_margin = search["similarity_margin"]
                nearest_confusion = target_by_reference_word.get(
                    search["best_other_word"], search["best_other_word"]
                )
                baseline = scoring.manual_baseline_score(target_similarity, similarity_margin)
                scoring_end = perf_counter_ns()
                decision = baseline.decision
                accepted = baseline.accepted
                score = baseline.score
            else:
                decision = "rerecord"
                accepted = False
                score = 0

            total_end = perf_counter_ns()
            total_ms = _milliseconds(total_start, total_end)
            result = {
                "sample_id": manifest_row["sample_id"],
                "target_word": manifest_row["target_word"],
                "performed_word": manifest_row["performed_word"],
                "signer_id": manifest_row["signer_id"],
                "source": manifest_row["source"],
                "split": manifest_row["split"],
                "sample_type": manifest_row["sample_type"],
                "expected_pass": manifest_row["expected_pass"] == "true",
                "variant_status": manifest_row["variant_status"],
                "source_sample_id": manifest_row["source_sample_id"],
                "anomaly_type": manifest_row["anomaly_type"],
                "repeat_index": repeat_index,
                "quality_valid": gate.valid,
                "quality_reasons": "|".join(gate.reasons),
                "decision": decision,
                "accepted": accepted,
                "score": score,
                "nearest_confusion": nearest_confusion,
                "target_similarity": target_similarity,
                "best_other_similarity": best_other_similarity,
                "similarity_margin": similarity_margin,
                **measurements.__dict__,
                "trajectory_distance": None,
                "prepare_ms": _milliseconds(stage_start, prepare_end),
                "quality_ms": _milliseconds(prepare_end, quality_end),
                "similarity_ms": _milliseconds(quality_end, similarity_end),
                "reference_search_ms": _milliseconds(search_start, search_end),
                "scoring_ms": _milliseconds(similarity_end, scoring_end),
                "total_ms": total_ms,
                "latency_ms": total_ms,
            }
            if gate.valid:
                scoring.validate_base_feature_row(result)
            results.append(result)

    results.sort(key=lambda row: (row["sample_id"], row["repeat_index"]))
    primary = _primary_rows(results)
    per_word = _build_per_word(primary, words)
    confusions = _build_confusions(primary, words)
    group_rows = {
        group: [row for row in primary if row["sample_type"] == group] for group in GROUPS
    }
    timing_rows = results
    similarity_timings = [float(row["similarity_ms"]) for row in timing_rows if row["quality_valid"]]
    search_timings = [float(row["reference_search_ms"]) for row in timing_rows if row["quality_valid"]]
    total_timings = [float(row["total_ms"]) for row in timing_rows]
    summary = {
        "schema_version": 1,
        "benchmark_label": "proxy_dataset_results",
        "manifest_row_count": len(rows),
        "evaluated_sample_count": len(primary),
        "attempt_count": len(results),
        "excluded": {
            "total_count": len(excluded),
            "unreviewed_count": sum(row["variant_status"] == "unreviewed" for row in excluded),
        },
        "groups": {group: _group_summary(group_rows[group]) for group in GROUPS},
        "semantic_auroc": _semantic_auroc(primary),
        "score_stability": _build_stability(results),
        "latency_ms": {
            "total_p50": _percentile(total_timings, 50),
            "total_p95": _percentile(total_timings, 95),
            "similarity_p50": _percentile(similarity_timings, 50),
            "similarity_p95": _percentile(similarity_timings, 95),
            "reference_search_p50": _percentile(search_timings, 50),
            "reference_search_p95": _percentile(search_timings, 95),
            "focused_reference_search_target_ms": 60,
            "measurement_scope": "fixture_measurement_only",
        },
    }

    csv_rows = [{key: _csv_value(row[key]) for key in SAMPLE_RESULT_COLUMNS} for row in results]
    _write_csv(output_dir / "sample_results.csv", SAMPLE_RESULT_COLUMNS, csv_rows)
    _write_csv(output_dir / "per_word.csv", PER_WORD_COLUMNS, per_word)
    _write_csv(output_dir / "confusions.csv", CONFUSION_COLUMNS, confusions)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference-index", type=Path, default=Path("data/reference_index/index.npz"))
    parser.add_argument(
        "--reference-manifest", type=Path, default=Path("data/reference_index/manifest.json")
    )
    parser.add_argument("--repeats", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reference_index = ReferenceIndex.load(args.reference_index, args.reference_manifest)
    summary = evaluate_manifest(
        args.manifest,
        args.output_dir,
        reference_index,
        repeats=args.repeats,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
