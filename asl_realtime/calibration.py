"""One local proxy-dataset calibrator; joblib files must come from a trusted source.

Production integration is gated on a reviewed real PopSign artifact. Synthetic
smoke artifacts exercise this contract only. DTW experiment deferred until
reviewed real validation data.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted

from asl_realtime.scoring import (
    BASE_MODEL_FEATURE_ORDER_V1, validate_base_feature_row,
    MIN_HAND_VISIBILITY, MIN_MOTION_ENERGY, MIN_MOTION_SPAN,
    MIN_SEQUENCE_COMPLETENESS,
)
from signcoach_benchmark.config import load_config

BENCHMARK_LABEL = "proxy_dataset_matching_confidence"
METADATA_COLUMNS = (
    "sample_id", "target_word", "performed_word", "signer_id", "source", "split",
    "sample_type", "expected_pass", "variant_status", "source_sample_id",
    "anomaly_type", "repeat_index", "quality_valid",
)
QUALITY_THRESHOLDS = {
    "min_hand_visibility": MIN_HAND_VISIBILITY,
    "min_motion_energy": MIN_MOTION_ENERGY,
    "min_motion_span": MIN_MOTION_SPAN,
    "min_sequence_completeness": MIN_SEQUENCE_COMPLETENESS,
}
SEMANTIC_TYPES = ("positive", "hard_negative", "random_negative")


def _boolean(value: str) -> bool:
    if value not in ("true", "false"):
        raise ValueError(f"expected true/false, got {value!r}")
    return value == "true"


def read_partitions(path: Path) -> dict[str, list[dict]]:
    """Validate P2 CSV and partition eligible rows. Never repair signer splits.

    sample_id is unique after repeat_index=0 selection; repeat pairs are unique
    in the raw file. Unreviewed blank labels and quality-invalid blank semantic
    features are legitimate P2 exclusions, not training values.
    """
    required = (*METADATA_COLUMNS, *BASE_MODEL_FEATURE_ORDER_V1, "score", "accepted")
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)) or not set(required) <= set(columns):
            raise ValueError("missing or duplicate sample_results.csv columns")
        raw = list(reader)
    partitions = {split: [] for split in ("train", "val", "test")}
    words = load_config().words_by_target
    pairs, primary_ids, signer_splits = set(), set(), {}
    for raw_row in raw:
        if None in raw_row or any(value is None for value in raw_row.values()):
            raise ValueError("malformed CSV row")
        row = {key: raw_row[key] for key in required}
        for key in ("sample_id", "signer_id", "source", "source_sample_id"):
            if not row[key].strip():
                raise ValueError(f"empty {key}")
        if row["split"] not in partitions:
            raise ValueError("unknown split")
        if row["target_word"] not in words:
            raise ValueError("target_word outside fixed 30-word vocabulary")
        if row["performed_word"] and row["performed_word"] not in words:
            raise ValueError("performed_word outside fixed 30-word vocabulary")
        if row["sample_type"] not in (*SEMANTIC_TYPES, "invalid"):
            raise ValueError("unknown sample_type")
        if row["variant_status"] not in (
            "target_variant", "valid_alternate", "different_sign", "unreviewed"
        ):
            raise ValueError("unknown variant_status")
        signer, split = row["signer_id"], row["split"]
        if signer in signer_splits and signer_splits[signer] != split:
            raise ValueError("signer crosses splits")
        signer_splits[signer] = split
        if not re.fullmatch(r"0|[1-9][0-9]*", row["repeat_index"]):
            raise ValueError("repeat_index must be a nonnegative integer")
        row["repeat_index"] = int(row["repeat_index"])
        pair = (row["sample_id"], row["repeat_index"])
        if pair in pairs:
            raise ValueError("duplicate sample_id/repeat_index")
        pairs.add(pair)
        if row["repeat_index"] == 0:
            if row["sample_id"] in primary_ids:
                raise ValueError("duplicate sample_id")
            primary_ids.add(row["sample_id"])
        row["quality_valid"] = _boolean(row["quality_valid"])
        row["accepted"] = _boolean(row["accepted"])
        row["score"] = float(row["score"])
        if not np.isfinite(row["score"]) or not 0 <= row["score"] <= 100:
            raise ValueError("invalid baseline score")
        if row["expected_pass"] == "" and row["variant_status"] == "unreviewed":
            row["expected_pass"] = None
        else:
            row["expected_pass"] = _boolean(row["expected_pass"])
        if row["quality_valid"]:
            values = validate_base_feature_row(row)
            row.update(zip(BASE_MODEL_FEATURE_ORDER_V1, values))
        eligible = (row["quality_valid"] and row["sample_type"] in SEMANTIC_TYPES
                    and row["variant_status"] != "unreviewed"
                    and row["expected_pass"] is not None)
        if eligible and not row["performed_word"]:
            raise ValueError("eligible semantic row requires performed_word")
        if row["repeat_index"] == 0 and eligible:
            partitions[split].append(row)
    if any(not rows for rows in partitions.values()):
        raise ValueError("eligible train, val and test splits are required")
    if {row["expected_pass"] for row in partitions["train"]} != {True, False}:
        raise ValueError("train requires both classes")
    _require_validation_groups(partitions["val"])
    return {split: sorted(rows, key=lambda row: row["sample_id"])
            for split, rows in partitions.items()}


def _require_split(rows: list[dict], split: str) -> None:
    if not rows or any(row["split"] != split for row in rows):
        raise ValueError(f"only nonempty {split} rows allowed")


def _require_validation_groups(rows: list[dict]) -> None:
    _require_split(rows, "val")
    for group in ("positive", "hard_negative"):
        if not any(row["sample_type"] == group
                   and row["variant_status"] != "unreviewed" for row in rows):
            raise ValueError("val requires positive and reviewed hard_negative")


def _matrix(rows: list[dict]) -> np.ndarray:
    return np.asarray([validate_base_feature_row(row) for row in rows], dtype=float)


def fit_pipeline(train_rows: list[dict]) -> Pipeline:
    """Fit exactly one scaler/logistic pipeline; accepts train rows only."""
    _require_split(train_rows, "train")
    labels = [row["expected_pass"] for row in train_rows]
    if set(labels) != {False, True}:
        raise ValueError("train requires both classes")
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("logistic", LogisticRegression(random_state=42, max_iter=1000)),
    ])
    return pipeline.fit(_matrix(train_rows), labels)


def _probabilities(pipeline: Pipeline, rows: list[dict]) -> np.ndarray:
    values = pipeline.predict_proba(_matrix(rows))[:, 1]
    if not np.all(np.isfinite(values)) or np.any((values < 0) | (values > 1)):
        raise ValueError("invalid predicted probability")
    return values


def metrics(rows: list[dict], probabilities, threshold: float, *, accepted=None) -> dict:
    probabilities = np.asarray(probabilities, dtype=float)
    decisions = probabilities >= threshold if accepted is None else np.asarray(accepted, dtype=bool)
    if len(rows) != len(probabilities) or len(rows) != len(decisions):
        raise ValueError("prediction length mismatch")
    result = {"benchmark_label": BENCHMARK_LABEL, "sample_count": len(rows),
              "threshold": threshold, "sample_counts": {}}
    for group, name in (
        ("positive", "positive_acceptance_rate"),
        ("hard_negative", "reviewed_hard_negative_false_acceptance_rate"),
        ("random_negative", "random_negative_false_acceptance_rate"),
    ):
        mask = np.asarray([row["sample_type"] == group for row in rows])
        result["sample_counts"][group] = int(mask.sum())
        result[name] = float(decisions[mask].mean()) if mask.any() else None
    labels = [row["expected_pass"] for row in rows]
    result["auroc"] = float(roc_auc_score(labels, probabilities)) if len(set(labels)) == 2 else None
    return result


def select_threshold(val_rows: list[dict], probabilities) -> tuple[float, dict]:
    """Val only. Pass iff p >= t; candidates are {0, 1, unique val p}.

    Maximize positive acceptance subject to reviewed hard-negative FAR <= .10;
    ties minimize that FAR, then maximize threshold. If p=1 makes every candidate
    infeasible, fail explicitly instead of violating the constraint.
    """
    _require_validation_groups(val_rows)
    probabilities = np.asarray(probabilities, dtype=float)
    if probabilities.shape != (len(val_rows),) or not np.all(np.isfinite(probabilities)):
        raise ValueError("invalid validation probabilities")
    if np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("probability outside [0,1]")
    candidates = sorted({0.0, 1.0, *map(float, probabilities)})
    feasible = []
    for threshold in candidates:
        report = metrics(val_rows, probabilities, threshold)
        far = report["reviewed_hard_negative_false_acceptance_rate"]
        if far <= 0.10:
            feasible.append((report["positive_acceptance_rate"], -far, threshold, report))
    if not feasible:
        raise ValueError("no feasible threshold in [0,1] under hard-negative FAR <= 0.10")
    _, _, threshold, report = max(feasible, key=lambda item: item[:3])
    return threshold, report


def training_data_version(train_rows: list[dict], val_rows: list[dict]) -> str:
    """SHA-256 of canonical eligible metadata/features, sorted by split/sample_id.

    Excludes baseline outputs, timings, file paths and all test rows. JSON uses
    sorted keys, compact separators, UTF-8, numeric features and boolean labels.
    """
    _require_split(train_rows, "train")
    _require_split(val_rows, "val")
    columns = (*METADATA_COLUMNS, *BASE_MODEL_FEATURE_ORDER_V1)
    canonical = [{key: row[key] for key in columns}
                 for row in sorted(train_rows + val_rows,
                                   key=lambda row: (row["split"], row["sample_id"]))]
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _counts(rows: list[dict]) -> dict:
    positives = sum(row["expected_pass"] for row in rows)
    return {"sample_count": len(rows), "class_counts": {
        "true": positives, "false": len(rows) - positives}}


def freeze_artifact(pipeline: Pipeline, threshold: float, train_rows: list[dict],
                    val_rows: list[dict], model_version: str, synthetic_smoke: bool) -> dict:
    sources = sorted({row["source"] for row in train_rows + val_rows})
    synthetic_markers = any(
        any(marker in str(row[key]).lower() for marker in ("synthetic", "fixture", "smoke"))
        for row in train_rows + val_rows
        for key in ("source", "sample_id", "source_sample_id", "signer_id")
    )
    artifact = {
        "schema_version": 1, "pipeline": pipeline,
        "feature_order": BASE_MODEL_FEATURE_ORDER_V1, "pass_threshold": threshold,
        "model_version": model_version,
        "training_data_version": training_data_version(train_rows, val_rows),
        "sklearn_version": sklearn.__version__,
        "train": _counts(train_rows), "val": _counts(val_rows),
        "quality_thresholds": dict(QUALITY_THRESHOLDS), "benchmark_label": BENCHMARK_LABEL,
        "synthetic_smoke": synthetic_smoke, "synthetic_markers": synthetic_markers,
        "training_sources": sources,
    }
    validate_artifact(artifact)
    return artifact


def validate_artifact(artifact: dict) -> None:
    """Strict schema/type/version checks; no migration or fallback."""
    required = {"schema_version", "pipeline", "feature_order", "pass_threshold",
                "model_version", "training_data_version", "sklearn_version", "train", "val",
                "quality_thresholds", "benchmark_label", "synthetic_smoke",
                "synthetic_markers", "training_sources"}
    if not isinstance(artifact, dict) or set(artifact) != required:
        raise ValueError("invalid artifact fields")
    if type(artifact["schema_version"]) is not int or artifact["schema_version"] != 1:
        raise ValueError("unsupported schema_version")
    if artifact["feature_order"] != BASE_MODEL_FEATURE_ORDER_V1:
        raise ValueError("invalid feature order")
    threshold = artifact["pass_threshold"]
    if type(threshold) not in (float, int) or not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("invalid pass_threshold")
    if artifact["sklearn_version"] != sklearn.__version__:
        raise ValueError("sklearn version mismatch")
    if artifact["benchmark_label"] != BENCHMARK_LABEL or artifact["quality_thresholds"] != QUALITY_THRESHOLDS:
        raise ValueError("benchmark or quality contract mismatch")
    if not isinstance(artifact["training_data_version"], str) or not re.fullmatch(r"[0-9a-f]{64}", artifact["training_data_version"]):
        raise ValueError("invalid training_data_version")
    for key in ("synthetic_smoke", "synthetic_markers"):
        if type(artifact[key]) is not bool:
            raise ValueError("invalid synthetic marker")
    expected_version = "calibrator-synthetic-smoke" if artifact["synthetic_smoke"] else "calibrator-v1"
    if artifact["model_version"] != expected_version:
        raise ValueError("model_version disagrees with synthetic marker")
    sources = artifact["training_sources"]
    if not isinstance(sources, list) or not sources or any(not isinstance(s, str) or not s for s in sources):
        raise ValueError("invalid training sources")
    if not artifact["synthetic_smoke"] and (artifact["synthetic_markers"] or sources != [load_config().source]):
        raise ValueError("production requires real PopSign sources without synthetic markers")
    for split in ("train", "val"):
        counts = artifact[split]
        if not isinstance(counts, dict) or set(counts) != {"sample_count", "class_counts"}:
            raise ValueError("invalid counts")
        classes = counts["class_counts"]
        if not isinstance(classes, dict) or set(classes) != {"true", "false"}:
            raise ValueError("invalid class counts")
        if any(type(n) is not int or n < 0 for n in [counts["sample_count"], *classes.values()]):
            raise ValueError("invalid count values")
        if counts["sample_count"] != sum(classes.values()) or min(classes.values()) < 1:
            raise ValueError("missing artifact classes")
    pipeline = artifact["pipeline"]
    if type(pipeline) is not Pipeline or [name for name, _ in pipeline.steps] != ["scaler", "logistic"]:
        raise ValueError("expected scaler + logistic Pipeline")
    scaler, logistic = pipeline.steps[0][1], pipeline.steps[1][1]
    if type(scaler) is not StandardScaler or type(logistic) is not LogisticRegression:
        raise ValueError("invalid pipeline step types")
    if scaler.get_params() != StandardScaler().get_params() or logistic.get_params() != LogisticRegression(random_state=42, max_iter=1000).get_params():
        raise ValueError("unexpected pipeline parameters")
    for estimator in (scaler, logistic):
        check_is_fitted(estimator)
        if estimator.n_features_in_ != len(BASE_MODEL_FEATURE_ORDER_V1):
            raise ValueError("invalid fitted feature count")
    if not np.array_equal(logistic.classes_, [False, True]):
        raise ValueError("invalid positive class")
    width = len(BASE_MODEL_FEATURE_ORDER_V1)
    for values, shape in ((scaler.mean_, (width,)), (scaler.var_, (width,)),
                          (scaler.scale_, (width,)), (logistic.coef_, (1, width)),
                          (logistic.intercept_, (1,))):
        if np.shape(values) != shape or not np.all(np.isfinite(values)):
            raise ValueError("invalid fitted parameters")
    if np.any(scaler.scale_ <= 0) or np.any(scaler.var_ < 0):
        raise ValueError("invalid fitted scaler statistics")


def load_calibrator(path: Path) -> dict:
    """Load a TRUSTED local joblib object and validate; never load untrusted pickle."""
    artifact = joblib.load(path)
    validate_artifact(artifact)
    return artifact


def predict_match(artifact: dict, feature_row: dict) -> dict:
    """For a quality-valid attempt: score=int(round(100*p)); pass iff p>=t.

    p is proxy-dataset matching confidence, not learner correctness probability.
    The caller must apply the frozen quality gate before this semantic function.
    """
    validate_artifact(artifact)
    probability = float(_probabilities(artifact["pipeline"], [feature_row])[0])
    return {"match_probability": probability, "score": int(round(100 * probability)),
            "accepted": probability >= artifact["pass_threshold"],
            "model_version": artifact["model_version"]}


def run_calibration(features: Path, artifact_path: Path, report_dir: Path,
                    model_version: str, synthetic_smoke: bool = False) -> dict:
    partitions = read_partitions(features)
    train, val = partitions["train"], partitions["val"]
    pipeline = fit_pipeline(train)
    val_probabilities = _probabilities(pipeline, val)
    threshold, validation = select_threshold(val, val_probabilities)
    artifact = freeze_artifact(pipeline, threshold, train, val, model_version, synthetic_smoke)
    artifact_path, report_dir = Path(artifact_path), Path(report_dir)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, artifact_path)
    frozen = load_calibrator(artifact_path)
    # Only now evaluate test once, using the reloaded frozen object.
    test = partitions["test"]
    test_probabilities = _probabilities(frozen["pipeline"], test)
    test_report = metrics(test, test_probabilities, frozen["pass_threshold"])
    metadata = {key: value for key, value in frozen.items() if key != "pipeline"}
    comparison = {"benchmark_label": BENCHMARK_LABEL, "synthetic_smoke": synthetic_smoke,
                  "scope": "eligible repeat-zero semantic rows; baseline accepted and score from input"}
    predictions = []
    for split, rows, probabilities, calibrated in (
        ("val", val, val_probabilities, validation), ("test", test, test_probabilities, test_report)
    ):
        calibrated["synthetic_smoke"] = synthetic_smoke
        comparison[split] = {"calibrated": calibrated, "baseline": metrics(
            rows, [row["score"] for row in rows], None,
            accepted=[row["accepted"] for row in rows])}
        for row, probability in zip(rows, probabilities):
            predictions.append({"sample_id": row["sample_id"], "split": split,
                                "match_probability": float(probability),
                                "score": int(round(100 * float(probability))),
                                "accepted": bool(probability >= frozen["pass_threshold"]),
                                "model_version": model_version,
                                "benchmark_label": BENCHMARK_LABEL,
                                "synthetic_smoke": synthetic_smoke})
    report_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in (("metadata.json", metadata), ("validation_metrics.json", validation),
                              ("test_metrics.json", test_report), ("baseline_comparison.json", comparison)):
        (report_dir / filename).write_text(json.dumps(content, indent=2, sort_keys=True,
                                                     allow_nan=False) + "\n", encoding="utf-8")
    with (report_dir / "sample_predictions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(predictions[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(predictions)
    return metadata
