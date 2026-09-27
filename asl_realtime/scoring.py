"""Pure quality measurements and the single Phase 1 manual baseline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from .constants import FEATURE_DIM, FEATURE_LANDMARK_COUNT, LEFT_HAND_COUNT, RIGHT_HAND_COUNT


TARGET_FRAMES_V1 = 32
MIN_HAND_VISIBILITY = 0.18
MIN_MOTION_ENERGY = 0.014
MIN_MOTION_SPAN = 0.075
MIN_SEQUENCE_COMPLETENESS = 6 / TARGET_FRAMES_V1

SIMILARITY_FLOOR = 0.68
SIMILARITY_CEILING = 0.90
MARGIN_FLOOR = -0.02
MARGIN_CEILING = 0.06
HIGH_TARGET_SIMILARITY = 0.94
AMBIGUOUS_MARGIN_FLOOR = -0.015
PASS_SCORE = 80

BASE_MODEL_FEATURE_ORDER_V1 = (
    "target_similarity",
    "best_other_similarity",
    "similarity_margin",
    "hand_visibility",
    "motion_energy",
    "motion_span",
    "sequence_completeness",
    "start_position_difference",
    "end_position_difference",
)


@dataclass(frozen=True)
class FeatureSpec:
    unit: str
    direction: str
    minimum: float
    maximum: float | None


BASE_MODEL_FEATURE_SPECS_V1 = {
    "target_similarity": FeatureSpec("cosine similarity", "higher_is_better", -1.0, 1.0),
    "best_other_similarity": FeatureSpec("cosine similarity", "lower_is_better", -1.0, 1.0),
    "similarity_margin": FeatureSpec(
        "target minus best-other cosine similarity", "higher_is_better", -2.0, 2.0
    ),
    "hand_visibility": FeatureSpec("fraction of prepared frames", "higher_is_better", 0.0, 1.0),
    "motion_energy": FeatureSpec(
        "75th-percentile hand step distance in normalized XY per prepared frame",
        "higher_means_more_motion",
        0.0,
        None,
    ),
    "motion_span": FeatureSpec(
        "hand-centroid XY span in normalized signer-relative coordinates",
        "higher_means_larger_motion",
        0.0,
        None,
    ),
    "sequence_completeness": FeatureSpec(
        "original frame count divided by 32, clipped to one", "higher_is_better", 0.0, 1.0
    ),
    "start_position_difference": FeatureSpec(
        "start hand-centroid distance from normalized signing-space origin",
        "lower_means_more_centered",
        0.0,
        None,
    ),
    "end_position_difference": FeatureSpec(
        "end hand-centroid distance from normalized signing-space origin",
        "lower_means_more_centered",
        0.0,
        None,
    ),
}


@dataclass(frozen=True)
class QualityMeasurements:
    hand_visibility: float
    motion_energy: float
    motion_span: float
    sequence_completeness: float
    start_position_difference: float
    end_position_difference: float


@dataclass(frozen=True)
class QualityGateResult:
    valid: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ManualBaselineResult:
    score: int
    accepted: bool
    decision: str
    ambiguous_high_target: bool


def _finite_float(name: str, value: float) -> float:
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return result


def _bounded_float(
    name: str,
    value: float,
    minimum: float,
    maximum: float | None,
) -> float:
    result = _finite_float(name, value)
    if result < minimum or (maximum is not None and result > maximum):
        upper = "infinity" if maximum is None else str(maximum)
        raise ValueError(f"{name} must be in [{minimum}, {upper}], got {result}")
    return result


def validate_base_feature_row(row: Mapping[str, float]) -> tuple[float, ...]:
    """Validate and order one BASE_MODEL_FEATURE_ORDER_V1 model row."""

    ordered: list[float] = []
    for name in BASE_MODEL_FEATURE_ORDER_V1:
        if name not in row:
            raise ValueError(f"missing base model feature: {name}")
        spec = BASE_MODEL_FEATURE_SPECS_V1[name]
        ordered.append(_bounded_float(name, row[name], spec.minimum, spec.maximum))
    return tuple(ordered)


def validate_trajectory_distance(value: float | None) -> float | None:
    """Validate the nullable offline-only experimental trajectory column."""

    if value is None:
        return None
    return _bounded_float("trajectory_distance", value, 0.0, None)


def _validate_prepared_sequence(prepared_sequence: np.ndarray) -> np.ndarray:
    prepared = np.asarray(prepared_sequence)
    expected_shape = (TARGET_FRAMES_V1, FEATURE_DIM)
    if prepared.shape != expected_shape:
        raise ValueError(f"Expected prepared sequence shape {expected_shape}, got {prepared.shape}")
    if not np.issubdtype(prepared.dtype, np.floating):
        raise ValueError(f"Prepared sequence must have a floating dtype, got {prepared.dtype}")
    if not np.all(np.isfinite(prepared)):
        raise ValueError("Prepared sequence contains NaN or infinity")
    return prepared.astype(np.float32, copy=False)


def measure_quality(prepared_sequence: np.ndarray, original_frame_count: int) -> QualityMeasurements:
    """Measure quality and position features from one already-prepared sequence."""

    prepared = _validate_prepared_sequence(prepared_sequence)
    if original_frame_count < 0:
        raise ValueError("original_frame_count must be non-negative")

    points = prepared.reshape(TARGET_FRAMES_V1, FEATURE_LANDMARK_COUNT, 3)
    hand_count = LEFT_HAND_COUNT + RIGHT_HAND_COUNT
    hands = points[:, :hand_count, :]
    visible = np.any(np.abs(hands[..., :2]) > 1e-6, axis=-1)
    visible_frame_mask = np.any(visible, axis=1)
    hand_visibility = float(np.mean(visible_frame_mask))

    diffs = hands[1:, :, :2] - hands[:-1, :, :2]
    valid_diffs = visible[1:] & visible[:-1]
    step_distances = np.linalg.norm(diffs, axis=-1)[valid_diffs]
    motion_energy = float(np.percentile(step_distances, 75)) if step_distances.size else 0.0

    centroids = np.asarray(
        [frame[frame_visible].mean(axis=0) for frame, frame_visible in zip(hands[..., :2], visible) if np.any(frame_visible)],
        dtype=np.float32,
    )
    if len(centroids) >= 2:
        motion_span = float(np.linalg.norm(np.ptp(centroids, axis=0)))
    else:
        motion_span = 0.0

    if len(centroids):
        start_position_difference = float(np.linalg.norm(centroids[0]))
        end_position_difference = float(np.linalg.norm(centroids[-1]))
    else:
        start_position_difference = 0.0
        end_position_difference = 0.0

    measurements = QualityMeasurements(
        hand_visibility=hand_visibility,
        motion_energy=motion_energy,
        motion_span=motion_span,
        sequence_completeness=min(float(original_frame_count) / TARGET_FRAMES_V1, 1.0),
        start_position_difference=start_position_difference,
        end_position_difference=end_position_difference,
    )
    validate_base_feature_row(
        {
            "target_similarity": 0.0,
            "best_other_similarity": 0.0,
            "similarity_margin": 0.0,
            **measurements.__dict__,
        }
    )
    return measurements


def quality_gate(measurements: QualityMeasurements) -> QualityGateResult:
    """Apply the one deterministic Phase 1 quality gate."""

    validate_base_feature_row(
        {
            "target_similarity": 0.0,
            "best_other_similarity": 0.0,
            "similarity_margin": 0.0,
            **measurements.__dict__,
        }
    )
    reasons: list[str] = []
    if measurements.hand_visibility < MIN_HAND_VISIBILITY:
        reasons.append("insufficient_hand_visibility")
    if measurements.sequence_completeness < MIN_SEQUENCE_COMPLETENESS:
        reasons.append("incomplete_sequence")
    if measurements.motion_energy < MIN_MOTION_ENERGY and measurements.motion_span < MIN_MOTION_SPAN:
        reasons.append("insufficient_motion")
    return QualityGateResult(valid=not reasons, reasons=tuple(reasons))


def scaled_unit(value: float, lower: float, upper: float) -> float:
    value = _finite_float("value", value)
    lower = _finite_float("lower", lower)
    upper = _finite_float("upper", upper)
    if upper <= lower:
        raise ValueError("upper must be greater than lower")
    return float(np.clip((value - lower) / (upper - lower), 0.0, 1.0))


def manual_baseline_score(target_similarity: float, similarity_margin: float) -> ManualBaselineResult:
    """Return the sole manual semantic score used by the API and evaluator."""

    target_similarity = _bounded_float("target_similarity", target_similarity, -1.0, 1.0)
    similarity_margin = _bounded_float("similarity_margin", similarity_margin, -2.0, 2.0)

    similarity_component = scaled_unit(target_similarity, SIMILARITY_FLOOR, SIMILARITY_CEILING)
    margin_component = scaled_unit(similarity_margin, MARGIN_FLOOR, MARGIN_CEILING)
    score = int(round((0.68 * similarity_component + 0.32 * margin_component) * 100))
    if target_similarity < 0.78:
        score = min(score, 74)

    ambiguous_high_target = (
        target_similarity >= HIGH_TARGET_SIMILARITY
        and similarity_margin >= AMBIGUOUS_MARGIN_FLOOR
    )
    if similarity_margin < 0.01 and not ambiguous_high_target:
        near_miss_score = int(
            round(
                62
                + 12 * scaled_unit(target_similarity, 0.78, 0.96)
                + 5 * scaled_unit(similarity_margin, -0.04, 0.01)
            )
        )
        score = min(score, near_miss_score)
    if ambiguous_high_target:
        score = max(score, 82)

    accepted = score >= PASS_SCORE
    return ManualBaselineResult(
        score=score,
        accepted=accepted,
        decision="pass" if accepted else "retry",
        ambiguous_high_target=ambiguous_high_target,
    )
