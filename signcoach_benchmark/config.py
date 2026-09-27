from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re


CONFIG_PATH = Path(__file__).with_name("vocabulary.json")
_SLUG_RE = re.compile(r"^[a-z0-9]+$")


@dataclass(frozen=True)
class VocabularyWord:
    target_word: str
    popsign_slug: str
    asl_citizen_word: str


@dataclass(frozen=True)
class BenchmarkConfig:
    dataset: str
    source: str
    base_url: str
    categories: tuple[str, ...]
    splits: tuple[str, ...]
    words: tuple[VocabularyWord, ...]

    @property
    def words_by_target(self) -> dict[str, VocabularyWord]:
        return {word.target_word: word for word in self.words}

    def select_words(self, requested: list[str] | tuple[str, ...] | None) -> tuple[VocabularyWord, ...]:
        if requested is None:
            return self.words

        selected: list[VocabularyWord] = []
        seen: set[str] = set()
        by_target = self.words_by_target
        for raw_word in requested:
            target = raw_word.strip().upper()
            if target not in by_target:
                allowed = ", ".join(by_target)
                raise ValueError(f"Unsupported benchmark word {raw_word!r}. Allowed: {allowed}")
            if target not in seen:
                selected.append(by_target[target])
                seen.add(target)
        if not selected:
            raise ValueError("At least one benchmark word is required")
        return tuple(selected)


def _validate_config(config: BenchmarkConfig) -> None:
    if config.dataset != "popsign_v1_0" or config.source != "popsign_v1_0":
        raise ValueError("The benchmark supports only PopSign ASL v1.0")
    if config.categories != ("game", "non-game"):
        raise ValueError("Categories must be exactly game and non-game")
    if config.splits != ("train", "val", "test"):
        raise ValueError("Splits must be exactly train, val, and test")
    if len(config.words) != 30:
        raise ValueError(f"Expected exactly 30 benchmark words, found {len(config.words)}")

    targets = [word.target_word for word in config.words]
    slugs = [word.popsign_slug for word in config.words]
    if len(set(targets)) != len(targets):
        raise ValueError("target_word values must be unique")
    if len(set(slugs)) != len(slugs):
        raise ValueError("popsign_slug values must be unique")
    for word in config.words:
        if not word.target_word or word.target_word != word.target_word.upper():
            raise ValueError(f"target_word must be non-empty uppercase text: {word.target_word!r}")
        if not _SLUG_RE.fullmatch(word.popsign_slug):
            raise ValueError(f"Unsafe PopSign slug: {word.popsign_slug!r}")
        if not word.asl_citizen_word:
            raise ValueError(f"asl_citizen_word is required for {word.target_word}")


@lru_cache(maxsize=1)
def load_config() -> BenchmarkConfig:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config = BenchmarkConfig(
        dataset=raw["dataset"],
        source=raw["source"],
        base_url=raw["base_url"].rstrip("/"),
        categories=tuple(raw["categories"]),
        splits=tuple(raw["splits"]),
        words=tuple(VocabularyWord(**word) for word in raw["words"]),
    )
    _validate_config(config)
    return config
