"""Landmark sequence preprocessing shared by training and realtime inference."""

from __future__ import annotations

import numpy as np

from .constants import FEATURE_DIM, FEATURE_LANDMARK_COUNT, LIP_LANDMARKS


def empty_frame() -> np.ndarray:
    return np.zeros((FEATURE_LANDMARK_COUNT, 3), dtype=np.float32)


def flatten_frame(frame: np.ndarray) -> np.ndarray:
    if frame.shape != (FEATURE_LANDMARK_COUNT, 3):
        raise ValueError(f"Expected frame shape {(FEATURE_LANDMARK_COUNT, 3)}, got {frame.shape}")
    return frame.astype(np.float32).reshape(FEATURE_DIM)


def normalize_sequence(sequence: np.ndarray) -> np.ndarray:
    """Normalize a sequence around the visible landmark cloud.

    The Kaggle landmarks and MediaPipe webcam landmarks are both image-normalized,
    but signer distance and camera framing still vary. This per-sequence
    normalization keeps the first version simple and robust enough for an MVP.
    """

    seq = sequence.astype(np.float32, copy=True)
    seq = np.nan_to_num(seq, nan=0.0, posinf=0.0, neginf=0.0)
    points = seq.reshape(-1, 3)
    visible = np.any(np.abs(points[:, :2]) > 1e-6, axis=1)
    if not np.any(visible):
        return seq

    xy = points[visible, :2]
    center = xy.mean(axis=0)
    scale = np.percentile(np.linalg.norm(xy - center, axis=1), 90)
    if scale < 1e-6:
        scale = 1.0

    seq[..., 0] = (seq[..., 0] - center[0]) / scale
    seq[..., 1] = (seq[..., 1] - center[1]) / scale
    seq[..., 2] = seq[..., 2] / scale

    missing = ~np.any(np.abs(sequence[..., :2]) > 1e-6, axis=-1)
    seq[missing] = 0.0
    return seq


def resize_sequence(sequence: np.ndarray, target_frames: int) -> np.ndarray:
    """Linearly resample a variable length sequence to a fixed length."""

    if sequence.ndim != 2:
        raise ValueError(f"Expected 2D sequence, got {sequence.shape}")
    if sequence.shape[1] != FEATURE_DIM:
        raise ValueError(f"Expected feature dim {FEATURE_DIM}, got {sequence.shape[1]}")
    if len(sequence) == 0:
        return np.zeros((target_frames, FEATURE_DIM), dtype=np.float32)
    if len(sequence) == target_frames:
        return sequence.astype(np.float32)
    if len(sequence) == 1:
        return np.repeat(sequence.astype(np.float32), target_frames, axis=0)

    old_x = np.linspace(0.0, 1.0, num=len(sequence), dtype=np.float32)
    new_x = np.linspace(0.0, 1.0, num=target_frames, dtype=np.float32)
    resized = np.empty((target_frames, sequence.shape[1]), dtype=np.float32)
    for dim in range(sequence.shape[1]):
        resized[:, dim] = np.interp(new_x, old_x, sequence[:, dim])
    return resized


def prepare_sequence(sequence: np.ndarray, target_frames: int) -> np.ndarray:
    if sequence.ndim == 3:
        sequence = sequence.reshape(sequence.shape[0], FEATURE_DIM)
    normalized = normalize_sequence(sequence.reshape(-1, FEATURE_LANDMARK_COUNT, 3))
    return resize_sequence(normalized.reshape(-1, FEATURE_DIM), target_frames)


def frame_from_mediapipe_results(results) -> np.ndarray:
    """Convert MediaPipe Holistic results to the shared frame layout."""

    frame = empty_frame()
    offset = 0

    for landmarks, count in (
        (getattr(results, "left_hand_landmarks", None), 21),
        (getattr(results, "right_hand_landmarks", None), 21),
        (getattr(results, "pose_landmarks", None), 33),
    ):
        if landmarks is not None:
            for idx, landmark in enumerate(landmarks.landmark[:count]):
                frame[offset + idx] = (landmark.x, landmark.y, landmark.z)
        offset += count

    face_landmarks = getattr(results, "face_landmarks", None)
    if face_landmarks is not None:
        for local_idx, face_idx in enumerate(LIP_LANDMARKS):
            landmark = face_landmarks.landmark[face_idx]
            frame[offset + local_idx] = (landmark.x, landmark.y, landmark.z)

    return frame

