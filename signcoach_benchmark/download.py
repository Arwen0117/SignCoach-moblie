from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
from typing import Iterable

import requests

from .config import BenchmarkConfig, VocabularyWord


CHECKSUM_SUFFIX = ".sha256"
EXTRACTION_MARKER = ".popsign-extracted.json"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class DownloadTarget:
    word: VocabularyWord
    category: str
    split: str
    url: str
    archive_path: Path
    extract_dir: Path


@dataclass(frozen=True)
class PrepareResult:
    target: DownloadTarget
    status: str
    detail: str


class UnsafeArchiveError(ValueError):
    pass


def build_tar_url(config: BenchmarkConfig, word: VocabularyWord, category: str, split: str) -> str:
    if category not in config.categories:
        raise ValueError(f"Unsupported PopSign category: {category}")
    if split not in config.splits:
        raise ValueError(f"Unsupported PopSign split: {split}")
    return f"{config.base_url}/{category}/{split}/{word.popsign_slug}.tar"


def build_download_targets(
    config: BenchmarkConfig,
    words: Iterable[VocabularyWord],
    categories: Iterable[str],
    splits: Iterable[str],
    output_root: Path,
) -> list[DownloadTarget]:
    targets: list[DownloadTarget] = []
    for word in words:
        for category in categories:
            if category not in config.categories:
                raise ValueError(f"Unsupported PopSign category: {category}")
            for split in splits:
                if split not in config.splits:
                    raise ValueError(f"Unsupported PopSign split: {split}")
                targets.append(
                    DownloadTarget(
                        word=word,
                        category=category,
                        split=split,
                        url=build_tar_url(config, word, category, split),
                        archive_path=output_root / "archives" / category / split / f"{word.popsign_slug}.tar",
                        extract_dir=output_root / "videos" / category / split / word.popsign_slug,
                    )
                )
    return targets


def checksum_path(archive_path: Path) -> Path:
    return archive_path.with_name(archive_path.name + CHECKSUM_SUFFIX)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum(archive_path: Path, digest: str) -> None:
    checksum_path(archive_path).write_text(f"{digest}  {archive_path.name}\n", encoding="ascii")


def read_checksum(archive_path: Path) -> str:
    sidecar = checksum_path(archive_path)
    if not sidecar.is_file():
        raise ValueError(f"checksum sidecar is missing: {sidecar}")
    digest = sidecar.read_text(encoding="ascii").strip().split(maxsplit=1)[0].lower()
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError(f"checksum sidecar is malformed: {sidecar}")
    return digest


def _normalized_member_path(member: tarfile.TarInfo) -> PurePosixPath:
    raw_name = member.name.replace("\\", "/")
    path = PurePosixPath(raw_name)
    if not raw_name or path.is_absolute() or ".." in path.parts:
        raise UnsafeArchiveError(f"unsafe archive path: {member.name!r}")
    if path.parts and path.parts[0].endswith(":"):
        raise UnsafeArchiveError(f"drive-qualified archive path: {member.name!r}")
    clean_parts = tuple(part for part in path.parts if part not in ("", "."))
    if not clean_parts:
        if member.isdir():
            return PurePosixPath(".")
        raise UnsafeArchiveError(f"empty archive path: {member.name!r}")
    normalized = PurePosixPath(*clean_parts)
    if normalized.name == EXTRACTION_MARKER:
        raise UnsafeArchiveError(f"archive contains reserved marker name: {member.name!r}")
    if not (member.isfile() or member.isdir()):
        raise UnsafeArchiveError(f"archive member is not a regular file or directory: {member.name!r}")
    return normalized


def validated_members(tar: tarfile.TarFile) -> list[tuple[tarfile.TarInfo, PurePosixPath]]:
    validated: list[tuple[tarfile.TarInfo, PurePosixPath]] = []
    seen: set[str] = set()
    for member in tar.getmembers():
        normalized = _normalized_member_path(member)
        key = normalized.as_posix().casefold()
        if key in seen and normalized != PurePosixPath("."):
            raise UnsafeArchiveError(f"duplicate archive path: {member.name!r}")
        seen.add(key)
        validated.append((member, normalized))
    if not any(member.isfile() for member, _ in validated):
        raise UnsafeArchiveError("archive contains no regular files")
    return validated


def inspect_archive(archive_path: Path) -> list[str]:
    try:
        with tarfile.open(archive_path, mode="r:*") as tar:
            return [path.as_posix() for member, path in validated_members(tar) if member.isfile()]
    except (tarfile.TarError, OSError) as exc:
        raise ValueError(f"invalid tar archive {archive_path}: {exc}") from exc


def safe_extract_tar(archive_path: Path, destination: Path) -> list[str]:
    if destination.exists():
        raise FileExistsError(f"refusing to extract over an existing path: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    extracted_files: list[str] = []
    try:
        with tarfile.open(archive_path, mode="r:*") as tar:
            members = validated_members(tar)
            for member, normalized in members:
                if normalized == PurePosixPath("."):
                    continue
                target = destination.joinpath(*normalized.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = tar.extractfile(member)
                if source is None:
                    raise UnsafeArchiveError(f"could not read archive member: {member.name!r}")
                with source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                extracted_files.append(normalized.as_posix())
    except Exception:
        # Callers use a fresh temporary directory, so cleanup cannot remove user data.
        if destination.exists():
            shutil.rmtree(destination)
        raise
    return extracted_files


def verify_archive(archive_path: Path) -> tuple[bool, str, str | None, list[str]]:
    if not archive_path.is_file():
        return False, "archive is missing", None, []
    try:
        expected = read_checksum(archive_path)
        actual = sha256_file(archive_path)
        if actual != expected:
            return False, f"checksum mismatch: expected {expected}, got {actual}", actual, []
        members = inspect_archive(archive_path)
    except (ValueError, UnsafeArchiveError) as exc:
        return False, str(exc), None, []
    return True, "archive checksum and tar structure are valid", actual, members


def verify_extraction(extract_dir: Path, archive_digest: str, members: list[str]) -> tuple[bool, str]:
    marker_path = extract_dir / EXTRACTION_MARKER
    if not extract_dir.is_dir():
        return False, "extraction directory is missing"
    if not marker_path.is_file():
        return False, f"extraction marker is missing: {marker_path}"
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"extraction marker is damaged: {exc}"
    if marker.get("archive_sha256") != archive_digest:
        return False, "extraction marker checksum does not match the archive"
    if marker.get("members") != members:
        return False, "extraction marker member list does not match the archive"
    for relative_path in members:
        path = extract_dir.joinpath(*PurePosixPath(relative_path).parts)
        if not path.is_file():
            return False, f"extracted file is missing: {path}"
    return True, "archive and extracted files already pass verification"


def download_archive(target: DownloadTarget) -> tuple[str, list[str]]:
    archive_path = target.archive_path
    if archive_path.exists() or checksum_path(archive_path).exists():
        raise FileExistsError(f"refusing to overwrite existing archive or checksum: {archive_path}")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(
        prefix=f".{archive_path.name}.", suffix=".part", dir=archive_path.parent, delete=False
    )
    temp_path = Path(temp_file.name)
    temp_file.close()
    try:
        with requests.get(target.url, stream=True, timeout=(10, 120)) as response:
            response.raise_for_status()
            with temp_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
        members = inspect_archive(temp_path)
        digest = sha256_file(temp_path)
        temp_path.replace(archive_path)
        write_checksum(archive_path, digest)
        return digest, members
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def extract_verified_archive(target: DownloadTarget, digest: str, members: list[str]) -> None:
    if target.extract_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing extraction directory: {target.extract_dir}")
    target.extract_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{target.word.popsign_slug}.", dir=target.extract_dir.parent) as temp:
        staging_dir = Path(temp) / "payload"
        extracted = safe_extract_tar(target.archive_path, staging_dir)
        if extracted != members:
            raise ValueError("extracted member list differs from the verified archive")
        marker = {"archive_sha256": digest, "members": members}
        (staging_dir / EXTRACTION_MARKER).write_text(
            json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        staging_dir.replace(target.extract_dir)


def plan_target(target: DownloadTarget) -> PrepareResult:
    archive_ok, archive_detail, digest, members = verify_archive(target.archive_path)
    if not target.archive_path.exists():
        return PrepareResult(target, "missing", "would download and extract")
    if not archive_ok or digest is None:
        return PrepareResult(target, "damaged", archive_detail)
    extracted_ok, extracted_detail = verify_extraction(target.extract_dir, digest, members)
    if extracted_ok:
        return PrepareResult(target, "skipped", extracted_detail)
    if target.extract_dir.exists():
        return PrepareResult(target, "damaged", extracted_detail)
    return PrepareResult(target, "missing", "archive is valid; would extract")


def prepare_target(target: DownloadTarget) -> PrepareResult:
    archive_ok, archive_detail, digest, members = verify_archive(target.archive_path)
    downloaded = False
    if not target.archive_path.exists():
        try:
            digest, members = download_archive(target)
            archive_ok = True
            downloaded = True
        except Exception as exc:
            return PrepareResult(target, "failed", f"download failed: {exc}")
    elif not archive_ok or digest is None:
        return PrepareResult(target, "damaged", archive_detail)

    assert digest is not None
    extracted_ok, extracted_detail = verify_extraction(target.extract_dir, digest, members)
    if extracted_ok:
        return PrepareResult(target, "skipped", extracted_detail)
    if target.extract_dir.exists():
        return PrepareResult(target, "damaged", extracted_detail)
    try:
        extract_verified_archive(target, digest, members)
    except Exception as exc:
        return PrepareResult(target, "failed", f"safe extraction failed: {exc}")
    action = "downloaded, checksummed, and safely extracted" if downloaded else "safely extracted verified archive"
    return PrepareResult(target, "prepared", action)
