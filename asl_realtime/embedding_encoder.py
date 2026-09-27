"""The local MediaPipe landmark embedding used by Phase 1 scoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .constants import FEATURE_DIM
from .mediapipe_compat import get_holistic_module
from .preprocess import flatten_frame, frame_from_mediapipe_results, prepare_sequence
from .scoring import TARGET_FRAMES_V1


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    vector = vector.astype(np.float32, copy=False)
    if not np.all(np.isfinite(vector)):
        raise ValueError("Embedding vector contains NaN or infinity")
    norm = np.linalg.norm(vector)
    if norm < 1e-8:
        return vector
    return vector / norm


@dataclass
class PoseEmbeddingEncoder:
    """Local baseline embedding encoder using MediaPipe landmarks."""

    target_frames: int = TARGET_FRAMES_V1
    max_video_frames: int = 96

    def encode_keypoint_sequence(self, sequence: np.ndarray) -> np.ndarray:
        if sequence.ndim != 2 or sequence.shape[1] != FEATURE_DIM:
            raise ValueError(f"Expected keypoint sequence shape (T, {FEATURE_DIM}), got {sequence.shape}")

        prepared = prepare_sequence(sequence, self.target_frames)
        return self.encode_prepared_sequence(prepared)

    def encode_prepared_sequence(self, prepared: np.ndarray) -> np.ndarray:
        """Encode a sequence already normalized and resized for this encoder."""

        expected_shape = (self.target_frames, FEATURE_DIM)
        if prepared.shape != expected_shape:
            raise ValueError(f"Expected prepared sequence shape {expected_shape}, got {prepared.shape}")
        if not np.all(np.isfinite(prepared)):
            raise ValueError("Prepared sequence contains NaN or infinity")
        velocity = np.diff(prepared, axis=0, prepend=prepared[:1])
        # Position captures shape; velocity captures motion direction/rhythm.
        vector = np.concatenate([prepared.reshape(-1), velocity.reshape(-1)], axis=0)
        return l2_normalize(vector)

    def extract_keypoints_from_video(self, video_path: Path) -> np.ndarray:
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total > self.max_video_frames:
            keep = set(np.linspace(0, total - 1, self.max_video_frames, dtype=int).tolist())
        else:
            keep = None

        holistic_module = get_holistic_module()
        frames: list[np.ndarray] = []
        with holistic_module.Holistic(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=False,
            refine_face_landmarks=True,
        ) as holistic:
            frame_idx = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if keep is not None and frame_idx not in keep:
                    frame_idx += 1
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = holistic.process(rgb)
                frames.append(flatten_frame(frame_from_mediapipe_results(results)))
                frame_idx += 1

        cap.release()
        if not frames:
            raise RuntimeError(f"No frames extracted from video: {video_path}")
        return np.asarray(frames, dtype=np.float32)

    def encode_video(self, video_path: Path) -> np.ndarray:
        return self.encode_keypoint_sequence(self.extract_keypoints_from_video(video_path))
