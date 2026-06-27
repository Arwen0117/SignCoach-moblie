"""Turn overlapping window predictions into stable subtitle text."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field


@dataclass
class SubtitleSmoother:
    min_confidence: float = 0.55
    stable_windows: int = 3
    history_size: int = 5
    cooldown_windows: int = 6
    max_words: int = 30
    _recent: deque[tuple[str, float]] = field(default_factory=deque)
    _cooldown: dict[str, int] = field(default_factory=dict)
    words: list[str] = field(default_factory=list)

    def update(self, label: str, confidence: float) -> tuple[str | None, str]:
        for key in list(self._cooldown):
            self._cooldown[key] -= 1
            if self._cooldown[key] <= 0:
                del self._cooldown[key]

        if confidence < self.min_confidence:
            return None, self.text

        self._recent.append((label, confidence))
        while len(self._recent) > self.history_size:
            self._recent.popleft()

        labels = [item[0] for item in self._recent]
        winner, count = Counter(labels).most_common(1)[0]
        if count < self.stable_windows or winner in self._cooldown:
            return None, self.text

        if not self.words or self.words[-1] != winner:
            self.words.append(winner)
            self.words = self.words[-self.max_words :]
            self._cooldown[winner] = self.cooldown_windows
            return winner, self.text

        self._cooldown[winner] = self.cooldown_windows
        return None, self.text

    @property
    def text(self) -> str:
        if not self.words:
            return ""
        text = " ".join(self.words)
        return text[:1].upper() + text[1:] + "."

    def clear(self) -> None:
        self._recent.clear()
        self._cooldown.clear()
        self.words.clear()

