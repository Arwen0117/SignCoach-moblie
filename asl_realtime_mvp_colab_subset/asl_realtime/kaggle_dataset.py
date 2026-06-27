"""Dataset loader for Kaggle Google ASL Signs landmark files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from .constants import FEATURE_DIM, LIP_LANDMARKS
from .preprocess import prepare_sequence


def load_label_map(data_dir: Path) -> dict[str, int]:
    with (data_dir / "sign_to_prediction_index_map.json").open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return {str(k): int(v) for k, v in raw.items()}


def build_subset(
    train_csv: Path,
    label_map: dict[str, int],
    max_classes: int | None = None,
    max_samples_per_class: int | None = None,
    seed: int = 13,
) -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_csv(train_csv)
    labels = sorted(df["sign"].unique(), key=lambda sign: label_map[sign])
    if max_classes is not None:
        labels = labels[:max_classes]
        df = df[df["sign"].isin(labels)]

    if max_samples_per_class is not None:
        if max_samples_per_class > 0:
            df = (
                df.groupby("sign", group_keys=False)
                .apply(lambda group: group.sample(n=min(len(group), max_samples_per_class), random_state=seed))
                .reset_index(drop=True)
            )
        else:
            df = df.reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    labels = sorted(df["sign"].unique(), key=lambda sign: label_map[sign])
    local_map = {sign: idx for idx, sign in enumerate(labels)}
    df["local_label"] = df["sign"].map(local_map)
    return df, labels


def _landmark_rows_to_frame(group: pd.DataFrame) -> np.ndarray:
    from .preprocess import empty_frame

    frame = empty_frame()
    type_offsets = {
        "left_hand": 0,
        "right_hand": 21,
        "pose": 42,
        "face": 75,
    }

    for landmark_type, offset in type_offsets.items():
        rows = group[group["type"] == landmark_type]
        if rows.empty:
            continue
        if landmark_type == "face":
            rows = rows[rows["landmark_index"].isin(LIP_LANDMARKS)]
            face_index_to_local = {face_idx: idx for idx, face_idx in enumerate(LIP_LANDMARKS)}
            for row in rows.itertuples(index=False):
                local = face_index_to_local[int(row.landmark_index)]
                frame[offset + local] = (row.x, row.y, row.z)
        else:
            for row in rows.itertuples(index=False):
                idx = int(row.landmark_index)
                if landmark_type in ("left_hand", "right_hand") and idx >= 21:
                    continue
                if landmark_type == "pose" and idx >= 33:
                    continue
                frame[offset + idx] = (row.x, row.y, row.z)

    return frame


def load_kaggle_sequence(parquet_path: Path, target_frames: int) -> np.ndarray:
    df = pd.read_parquet(parquet_path, columns=["frame", "type", "landmark_index", "x", "y", "z"])
    frames = [_landmark_rows_to_frame(group) for _, group in df.groupby("frame", sort=True)]
    sequence = np.stack(frames, axis=0).reshape(len(frames), FEATURE_DIM) if frames else np.zeros((0, FEATURE_DIM))
    return prepare_sequence(sequence, target_frames)


class KaggleASLDataset(Dataset):
    def __init__(self, data_dir: Path, rows: pd.DataFrame, target_frames: int):
        self.data_dir = data_dir
        self.rows = rows.reset_index(drop=True)
        self.target_frames = target_frames

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.rows.iloc[index]
        sequence = load_kaggle_sequence(self.data_dir / row["path"], self.target_frames)
        x = torch.from_numpy(sequence).float()
        y = torch.tensor(int(row["local_label"]), dtype=torch.long)
        return x, y


def save_labels(labels: Iterable[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(list(labels), f, ensure_ascii=False, indent=2)


def load_labels(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        return list(json.load(f))
