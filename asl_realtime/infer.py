"""Checkpoint loading and single-window inference."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from .kaggle_dataset import load_labels
from .model import build_model
from .preprocess import prepare_sequence


class SignRecognizer:
    def __init__(self, checkpoint: Path, labels_path: Path | None = None, device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        payload = torch.load(checkpoint, map_location=self.device)
        self.labels = payload.get("labels") or load_labels(labels_path)  # type: ignore[arg-type]
        self.frames = int(payload.get("frames", 64))
        self.model = build_model(num_classes=len(self.labels)).to(self.device)
        self.model.load_state_dict(payload["model"])
        self.model.eval()

    @torch.inference_mode()
    def predict(self, sequence: np.ndarray) -> tuple[str, float]:
        x = prepare_sequence(sequence, self.frames)
        tensor = torch.from_numpy(x).float().unsqueeze(0).to(self.device)
        probs = torch.softmax(self.model(tensor), dim=1)[0]
        score, idx = torch.max(probs, dim=0)
        return self.labels[int(idx.item())], float(score.item())

