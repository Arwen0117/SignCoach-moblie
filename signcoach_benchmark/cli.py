from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

from .config import load_config
from .download import build_download_targets, plan_target, prepare_target
from .manifest import build_manifest, validate_manifest


DEFAULT_DATASET_ROOT = Path("data/popsign_v1_0")


def _parser() -> argparse.ArgumentParser:
    config = load_config()
    parser = argparse.ArgumentParser(
        prog="python -m signcoach_benchmark",
        description="Prepare and validate the fixed 30-word PopSign ASL v1.0 benchmark.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare",
        help="Plan downloads by default; pass --download to fetch and safely extract selected words.",
    )
    prepare.add_argument("--words", nargs="+", required=True, help="Explicit fixed-vocabulary target words")
    prepare.add_argument(
        "--categories", nargs="+", choices=config.categories, default=list(config.categories)
    )
    prepare.add_argument("--splits", nargs="+", choices=config.splits, default=list(config.splits))
    prepare.add_argument("--output-root", type=Path, default=DEFAULT_DATASET_ROOT)
    prepare.add_argument(
        "--download",
        action="store_true",
        help="Perform network downloads. Without this flag the command is a network-free dry run.",
    )

    manifest = subparsers.add_parser("manifest", help="Build a manifest from prepared video files.")
    manifest.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    manifest.add_argument(
        "--output", type=Path, default=DEFAULT_DATASET_ROOT / "benchmark_manifest.csv"
    )
    manifest.add_argument(
        "--words", nargs="+", help="Requested fixed-vocabulary words; defaults to all configured words"
    )

    validate = subparsers.add_parser("validate", help="Validate a benchmark manifest and referenced paths.")
    validate.add_argument(
        "--manifest", type=Path, default=DEFAULT_DATASET_ROOT / "benchmark_manifest.csv"
    )
    return parser


def _prepare(args: argparse.Namespace) -> int:
    config = load_config()
    try:
        words = config.select_words(args.words)
        targets = build_download_targets(
            config, words, args.categories, args.splits, args.output_root
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    mode = "DOWNLOAD" if args.download else "DRY RUN (no network)"
    print(f"PopSign ASL v1.0 prepare: {mode}")
    results = []
    for target in targets:
        result = prepare_target(target) if args.download else plan_target(target)
        results.append(result)
        print(
            f"[{result.status}] {target.word.target_word} {target.category}/{target.split}\n"
            f"  URL: {target.url}\n"
            f"  archive: {target.archive_path}\n"
            f"  extract: {target.extract_dir}\n"
            f"  detail: {result.detail}"
        )

    counts = Counter(result.status for result in results)
    summary = ", ".join(f"{status}={counts[status]}" for status in sorted(counts))
    print(f"Summary: {summary}")
    return 1 if any(result.status in {"damaged", "failed"} for result in results) else 0


def _manifest(args: argparse.Namespace) -> int:
    config = load_config()
    try:
        words = config.select_words(args.words)
        row_count = build_manifest(config, args.dataset_root, args.output, words)
    except (OSError, ValueError) as exc:
        print(f"manifest build failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {row_count} row(s) to {args.output}")
    return 0


def _validate(args: argparse.Namespace) -> int:
    report = validate_manifest(load_config(), args.manifest)
    if report.valid:
        print(f"Manifest valid: {report.row_count} row(s), no signer overlap")
        return 0
    print(f"Manifest invalid: {report.row_count} row(s), {len(report.issues)} error(s)", file=sys.stderr)
    for issue in report.issues:
        print(f"  {issue.format()}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "manifest":
        return _manifest(args)
    if args.command == "validate":
        return _validate(args)
    raise AssertionError(f"unhandled command: {args.command}")
