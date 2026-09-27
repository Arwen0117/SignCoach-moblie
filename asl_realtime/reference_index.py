"""Reference video vector index for similarity-based ASL practice."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def normalize_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


@dataclass
class ReferenceEntry:
    word: str
    slug: str
    video_path: str
    embedding_index: int
    lecture: str | None = None
    topic: str | None = None
    sentence: str | None = None


class ReferenceIndex:
    def __init__(self, embeddings: np.ndarray, entries: list[ReferenceEntry]):
        if embeddings.ndim != 2 or len(embeddings) == 0:
            raise ValueError(f"Expected non-empty 2D embeddings, got {embeddings.shape}")
        if not np.all(np.isfinite(embeddings)):
            raise ValueError("Reference embeddings contain NaN or infinity")
        if len(entries) != len(embeddings):
            raise ValueError("Reference entry count must equal embedding count")
        expected_indices = set(range(len(entries)))
        actual_indices = {entry.embedding_index for entry in entries}
        if actual_indices != expected_indices:
            raise ValueError("Reference embedding_index values must be contiguous and unique")

        self.embeddings = embeddings.astype(np.float32)
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        self.embeddings = np.divide(self.embeddings, np.maximum(norms, 1e-8))
        self.entries = entries
        self.entries_by_index = {entry.embedding_index: entry for entry in entries}
        self.by_key: dict[str, list[int]] = {}
        for entry in entries:
            for key in {entry.word, entry.slug}:
                self.by_key.setdefault(normalize_key(key), []).append(entry.embedding_index)

    @classmethod
    def load(cls, index_path: Path, manifest_path: Path, *, allowed_words=None) -> "ReferenceIndex":
        embeddings = np.load(index_path)["embeddings"]
        raw_entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = [ReferenceEntry(**item) for item in raw_entries["entries"]]
        if allowed_words is not None:
            allowed = {normalize_key(word) for word in allowed_words}
            selected = [entry for entry in entries if normalize_key(entry.word) in allowed]
            missing = allowed - {normalize_key(entry.word) for entry in selected}
            if missing:
                raise ValueError(f"Missing reference words: {sorted(missing)}")
            # Select vectors by original indices, never by manifest list position.
            original_indices = [entry.embedding_index for entry in selected]
            if len(set(original_indices)) != len(original_indices) or any(i < 0 or i >= len(embeddings) for i in original_indices):
                raise ValueError("Invalid original reference embedding indices")
            embeddings = embeddings[original_indices]
            entries = [replace(entry, embedding_index=i) for i, entry in enumerate(selected)]
        return cls(embeddings, entries)

    def search_target(self, target: str, query_embedding: np.ndarray) -> dict:
        key = normalize_key(target)
        indices = self.by_key.get(key, [])
        if not indices:
            raise KeyError(f"No references found for target {target!r}")

        query = np.asarray(query_embedding, dtype=np.float32)
        if query.ndim != 1 or query.shape[0] != self.embeddings.shape[1]:
            raise ValueError(
                f"Expected query embedding shape ({self.embeddings.shape[1]},), got {query.shape}"
            )
        if not np.all(np.isfinite(query)):
            raise ValueError("Query embedding contains NaN or infinity")
        query_norm = np.linalg.norm(query)
        if query_norm > 1e-8:
            query = query / query_norm

        # Float32 dot products can exceed the mathematical cosine bounds by a
        # few ulps, so constrain them to the exact feature contract.
        all_similarities = np.clip(self.embeddings @ query, -1.0, 1.0)
        target_similarities = all_similarities[indices]
        best_local = int(np.argmax(target_similarities))
        target_index_set = set(indices)
        other_indices = [idx for idx in range(len(self.embeddings)) if idx not in target_index_set]
        if not other_indices:
            raise ValueError("Reference index must contain at least one non-target reference")
        other_similarities = all_similarities[other_indices]
        best_other_local = int(np.argmax(other_similarities))
        best_other_index = other_indices[best_other_local]

        target_similarity = float(target_similarities[best_local])
        best_other_similarity = float(other_similarities[best_other_local])
        return {
            "target_similarity": target_similarity,
            "best_other_similarity": best_other_similarity,
            "best_other_word": self.entries_by_index[best_other_index].word,
            "similarity_margin": target_similarity - best_other_similarity,
        }


def discover_reference_videos(reference_dir: Path) -> list[tuple[str, Path]]:
    if not reference_dir.exists():
        return []

    items: list[tuple[str, Path]] = []
    for word_dir in sorted(path for path in reference_dir.iterdir() if path.is_dir()):
        word = word_dir.name
        for video_path in sorted(word_dir.rglob("*")):
            if video_path.is_file() and video_path.suffix.lower() in VIDEO_EXTENSIONS:
                items.append((word, video_path))
    return items
