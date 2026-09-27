from __future__ import annotations

import csv
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re
from typing import Iterable

from .config import BenchmarkConfig, VocabularyWord


MANIFEST_COLUMNS = (
    "sample_id",
    "target_word",
    "performed_word",
    "signer_id",
    "source",
    "split",
    "sample_type",
    "expected_pass",
    "variant_status",
    "video_path",
    "keypoints_path",
    "anomaly_type",
    "source_sample_id",
)
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".webm"}
SAMPLE_TYPES = {"positive", "hard_negative", "random_negative", "invalid"}
VARIANT_STATUSES = {"target_variant", "valid_alternate", "different_sign", "unreviewed"}
_POPSIGN_FILENAME_RE = re.compile(
    r"(?P<signer>[A-Za-z0-9]+\.[0-9]+)-(?P<word>[a-z0-9]+)-"
    r"[0-9]{4}_[0-9]{2}_[0-9]{2}_[0-9]{2}_[0-9]{2}_[0-9]{2}\.[0-9]+-[0-9]+\.mp4"
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    row_number: int | None = None

    def format(self) -> str:
        location = f"row {self.row_number}: " if self.row_number is not None else ""
        return f"[{self.code}] {location}{self.message}"


@dataclass(frozen=True)
class ValidationReport:
    row_count: int
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


def recover_signer_id(video_path: Path, word_dir: Path) -> str:
    relative = video_path.relative_to(word_dir)
    match = _POPSIGN_FILENAME_RE.fullmatch(video_path.name)
    if (
        len(relative.parts) == 2
        and relative.parts[0] == word_dir.name
        and match is not None
        and match.group("word") == word_dir.name
    ):
        return match.group("signer")
    raise ValueError(
        "cannot recover signer_id: expected PopSign word/participant-word-timestamp-index.mp4 "
        f"with matching word labels below {word_dir}: {video_path}"
    )


def _manifest_relative_path(path: Path, manifest_path: Path) -> str:
    relative = os.path.relpath(path.resolve(), manifest_path.parent.resolve())
    return Path(relative).as_posix()


def _source_sample_id(video_path: Path, word_dir: Path) -> str:
    relative = video_path.relative_to(word_dir)
    return PurePosixPath(*relative.with_suffix("").parts).as_posix()


def build_manifest_rows(
    config: BenchmarkConfig,
    dataset_root: Path,
    manifest_path: Path,
    words: Iterable[VocabularyWord],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    missing_words: list[str] = []
    signer_errors: list[str] = []

    for word in words:
        word_count = 0
        for category in config.categories:
            for split in config.splits:
                word_dir = dataset_root / "videos" / category / split / word.popsign_slug
                if not word_dir.is_dir():
                    continue
                videos = sorted(
                    path for path in word_dir.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
                )
                for video_path in videos:
                    try:
                        signer_id = recover_signer_id(video_path, word_dir)
                    except ValueError as exc:
                        signer_errors.append(str(exc))
                        continue
                    source_sample_id = _source_sample_id(video_path, word_dir)
                    sample_id = (
                        f"{config.source}:{category}:{split}:{word.target_word}:{source_sample_id}"
                    )
                    is_game = category == "game"
                    rows.append(
                        {
                            "sample_id": sample_id,
                            "target_word": word.target_word,
                            "performed_word": word.target_word if is_game else "",
                            "signer_id": signer_id,
                            "source": config.source,
                            "split": split,
                            "sample_type": "positive" if is_game else "hard_negative",
                            "expected_pass": "true" if is_game else "",
                            "variant_status": "target_variant" if is_game else "unreviewed",
                            "video_path": _manifest_relative_path(video_path, manifest_path),
                            "keypoints_path": "",
                            "anomaly_type": "",
                            "source_sample_id": source_sample_id,
                        }
                    )
                    word_count += 1
        if word_count == 0:
            missing_words.append(word.target_word)

    if signer_errors:
        preview = "\n".join(f"  - {error}" for error in signer_errors[:20])
        remainder = len(signer_errors) - 20
        suffix = f"\n  - ... and {remainder} more" if remainder else ""
        raise ValueError(f"Signer recovery failed for {len(signer_errors)} file(s):\n{preview}{suffix}")
    if missing_words:
        raise ValueError(f"No video files found for requested word(s): {', '.join(missing_words)}")

    split_order = {split: index for index, split in enumerate(config.splits)}
    rows.sort(key=lambda row: (row["target_word"], split_order[row["split"]], row["sample_id"]))
    return rows


def write_manifest(path: Path, rows: Iterable[dict[str, str]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(materialized)
    return len(materialized)


def build_manifest(
    config: BenchmarkConfig,
    dataset_root: Path,
    manifest_path: Path,
    words: Iterable[VocabularyWord],
) -> int:
    rows = build_manifest_rows(config, dataset_root, manifest_path, words)
    return write_manifest(manifest_path, rows)


def _resolve_data_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path


def validate_manifest(config: BenchmarkConfig, manifest_path: Path) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if not manifest_path.is_file():
        return ValidationReport(0, (ValidationIssue("manifest_missing", f"file not found: {manifest_path}"),))

    try:
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            columns = tuple(reader.fieldnames or ())
            if columns != MANIFEST_COLUMNS:
                issues.append(
                    ValidationIssue(
                        "columns",
                        f"expected columns {list(MANIFEST_COLUMNS)}, found {list(columns)}",
                    )
                )
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        return ValidationReport(0, (ValidationIssue("manifest_read", str(exc)),))

    if not rows:
        issues.append(ValidationIssue("empty", "manifest contains no sample rows"))

    allowed_targets = config.words_by_target
    required_values = (
        "sample_id",
        "target_word",
        "signer_id",
        "source",
        "split",
        "sample_type",
        "variant_status",
        "video_path",
        "source_sample_id",
    )
    seen_sample_ids: dict[str, int] = {}
    signer_splits: dict[str, set[str]] = {}

    for row_number, row in enumerate(rows, start=2):
        for column in required_values:
            if not (row.get(column) or "").strip():
                issues.append(ValidationIssue("required", f"{column} is blank", row_number))

        sample_id = (row.get("sample_id") or "").strip()
        if sample_id:
            if sample_id in seen_sample_ids:
                issues.append(
                    ValidationIssue(
                        "duplicate_sample_id",
                        f"{sample_id!r} also appears on row {seen_sample_ids[sample_id]}",
                        row_number,
                    )
                )
            else:
                seen_sample_ids[sample_id] = row_number

        target_word = (row.get("target_word") or "").strip()
        if target_word and target_word not in allowed_targets:
            issues.append(ValidationIssue("target_word", f"unsupported target {target_word!r}", row_number))

        source = (row.get("source") or "").strip()
        if source and source != config.source:
            issues.append(ValidationIssue("source", f"expected {config.source!r}, found {source!r}", row_number))

        split = (row.get("split") or "").strip()
        if split and split not in config.splits:
            issues.append(ValidationIssue("split", f"unsupported split {split!r}", row_number))

        sample_type = (row.get("sample_type") or "").strip()
        if sample_type and sample_type not in SAMPLE_TYPES:
            issues.append(ValidationIssue("sample_type", f"unsupported value {sample_type!r}", row_number))

        variant_status = (row.get("variant_status") or "").strip()
        if variant_status and variant_status not in VARIANT_STATUSES:
            issues.append(ValidationIssue("variant_status", f"unsupported value {variant_status!r}", row_number))

        expected_pass = (row.get("expected_pass") or "").strip()
        if expected_pass not in {"", "true", "false"}:
            issues.append(ValidationIssue("expected_pass", f"unsupported value {expected_pass!r}", row_number))
        expected_by_variant = {
            "target_variant": "true",
            "valid_alternate": "true",
            "different_sign": "false",
            "unreviewed": "",
        }
        if variant_status in expected_by_variant and expected_pass != expected_by_variant[variant_status]:
            issues.append(
                ValidationIssue(
                    "variant_expected_pass",
                    f"{variant_status!r} requires expected_pass={expected_by_variant[variant_status]!r}",
                    row_number,
                )
            )

        performed_word = (row.get("performed_word") or "").strip()
        if performed_word and performed_word not in allowed_targets:
            issues.append(
                ValidationIssue(
                    "performed_word_product_key",
                    f"performed_word must be one of the fixed product keys, found {performed_word!r}",
                    row_number,
                )
            )
        if variant_status == "unreviewed" and performed_word:
            issues.append(
                ValidationIssue(
                    "unreviewed_performed_word",
                    "unreviewed variants must leave performed_word blank",
                    row_number,
                )
            )
        if variant_status in {"target_variant", "valid_alternate"} and performed_word != target_word:
            issues.append(
                ValidationIssue(
                    "variant_performed_word",
                    f"{variant_status} requires performed_word to equal target_word",
                    row_number,
                )
            )
        if sample_type == "positive" and variant_status not in {"target_variant", "valid_alternate"}:
            issues.append(
                ValidationIssue(
                    "positive_variant",
                    "positive samples must be target_variant or valid_alternate",
                    row_number,
                )
            )

        video_value = (row.get("video_path") or "").strip()
        if video_value:
            video_path = _resolve_data_path(video_value, manifest_path)
            if not video_path.is_file():
                issues.append(ValidationIssue("video_path", f"file not found: {video_path}", row_number))
        keypoints_value = (row.get("keypoints_path") or "").strip()
        if keypoints_value:
            keypoints_path = _resolve_data_path(keypoints_value, manifest_path)
            if not keypoints_path.is_file():
                issues.append(ValidationIssue("keypoints_path", f"file not found: {keypoints_path}", row_number))

        signer_id = (row.get("signer_id") or "").strip()
        if signer_id and split in config.splits:
            signer_splits.setdefault(signer_id, set()).add(split)

    for signer_id, splits in sorted(signer_splits.items()):
        if len(splits) > 1:
            issues.append(
                ValidationIssue(
                    "signer_leakage",
                    f"signer {signer_id!r} appears in splits {', '.join(sorted(splits))}",
                )
            )

    return ValidationReport(len(rows), tuple(issues))
