from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import csv
from io import BytesIO, StringIO
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from signcoach_benchmark.cli import main
from signcoach_benchmark.config import load_config
from signcoach_benchmark.download import (
    EXTRACTION_MARKER,
    UnsafeArchiveError,
    build_download_targets,
    build_tar_url,
    plan_target,
    prepare_target,
    safe_extract_tar,
    sha256_file,
    write_checksum,
)
from signcoach_benchmark.manifest import (
    MANIFEST_COLUMNS,
    build_manifest,
    recover_signer_id,
    validate_manifest,
    write_manifest,
)


def make_tar(path: Path, members: list[tuple[str, bytes, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w") as tar:
        for name, content, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(content)
                tar.addfile(info, BytesIO(content))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = content.decode("utf-8")
                tar.addfile(info)
            else:
                raise AssertionError(f"unsupported test member kind: {kind}")


class ConfigAndUrlTests(unittest.TestCase):
    def test_fixed_vocabulary_and_mappings(self) -> None:
        config = load_config()
        self.assertEqual(30, len(config.words))
        self.assertEqual(("game", "non-game"), config.categories)
        self.assertEqual(("train", "val", "test"), config.splits)
        self.assertEqual("MOTHER", config.words_by_target["MOM"].asl_citizen_word)
        self.assertEqual("FATHER", config.words_by_target["DAD"].asl_citizen_word)
        self.assertEqual("THANK YOU", config.words_by_target["THANKYOU"].asl_citizen_word)

    def test_url_uses_official_hierarchy_and_source_slug(self) -> None:
        config = load_config()
        mom = config.words_by_target["MOM"]
        self.assertEqual(
            "https://signdata.cc.gatech.edu/data/popsign_v1_0/non-game/test/mom.tar",
            build_tar_url(config, mom, "non-game", "test"),
        )

    def test_words_must_be_explicit_for_prepare_cli(self) -> None:
        with self.assertRaises(SystemExit) as context, redirect_stderr(StringIO()):
            main(["prepare"])
        self.assertEqual(2, context.exception.code)


class ArchiveSafetyTests(unittest.TestCase):
    def test_path_traversal_is_rejected_without_writing_outside_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "unsafe.tar"
            destination = root / "extract"
            make_tar(archive, [("../escape.mp4", b"bad", "file")])

            with self.assertRaises(UnsafeArchiveError):
                safe_extract_tar(archive, destination)

            self.assertFalse((root / "escape.mp4").exists())

    def test_windows_style_traversal_and_links_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            traversal = root / "windows-traversal.tar"
            symlink = root / "symlink.tar"
            make_tar(traversal, [("..\\escape.mp4", b"bad", "file")])
            make_tar(symlink, [("linked.mp4", b"../outside.mp4", "symlink")])

            with self.assertRaises(UnsafeArchiveError):
                safe_extract_tar(traversal, root / "traversal-output")
            with self.assertRaises(UnsafeArchiveError):
                safe_extract_tar(symlink, root / "symlink-output")

    def test_safe_extraction_never_overwrites_an_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "safe.tar"
            destination = root / "existing"
            destination.mkdir()
            existing = destination / "keep.txt"
            existing.write_text("user data", encoding="utf-8")
            make_tar(archive, [("signer-001/clip.mp4", b"video", "file")])

            with self.assertRaises(FileExistsError):
                safe_extract_tar(archive, destination)

            self.assertEqual("user data", existing.read_text(encoding="utf-8"))

    def test_verified_archive_is_idempotently_extracted(self) -> None:
        config = load_config()
        hello = config.words_by_target["HELLO"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = build_download_targets(config, [hello], ["game"], ["train"], root)[0]
            make_tar(
                target.archive_path,
                [("signer-001/hello-001.mp4", b"fake video", "file")],
            )
            write_checksum(target.archive_path, sha256_file(target.archive_path))

            with patch("signcoach_benchmark.download.requests.get") as get:
                first = prepare_target(target)
                second = prepare_target(target)

            self.assertEqual("prepared", first.status)
            self.assertEqual("skipped", second.status)
            get.assert_not_called()
            self.assertTrue((target.extract_dir / "signer-001" / "hello-001.mp4").is_file())
            marker = json.loads((target.extract_dir / EXTRACTION_MARKER).read_text(encoding="utf-8"))
            self.assertEqual(
                ["signer-001/hello-001.mp4"],
                marker["members"],
            )

    def test_bad_checksum_is_reported_as_damaged_and_never_overwritten(self) -> None:
        config = load_config()
        hello = config.words_by_target["HELLO"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = build_download_targets(config, [hello], ["game"], ["train"], root)[0]
            make_tar(target.archive_path, [("signer-001/hello.mp4", b"video", "file")])
            write_checksum(target.archive_path, "0" * 64)
            before = target.archive_path.read_bytes()

            result = prepare_target(target)

            self.assertEqual("damaged", result.status)
            self.assertIn("checksum mismatch", result.detail)
            self.assertEqual(before, target.archive_path.read_bytes())
            self.assertFalse(target.extract_dir.exists())

    def test_dry_run_does_not_call_network(self) -> None:
        config = load_config()
        with tempfile.TemporaryDirectory() as temp:
            target = build_download_targets(
                config,
                [config.words_by_target["HELLO"]],
                ["game"],
                ["train"],
                Path(temp),
            )[0]
            with patch("signcoach_benchmark.download.requests.get") as get:
                result = plan_target(target)
            self.assertEqual("missing", result.status)
            get.assert_not_called()


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config()
        self.words = self.config.select_words(["HELLO", "PLEASE", "THANKYOU"])

    def _make_fixture(self, temp: str) -> Path:
        destination = Path(temp) / "popsign"
        for word, split, signer in (
            ("hello", "train", "study.001"),
            ("please", "val", "study.002"),
            ("thankyou", "test", "study.003"),
        ):
            for category in self.config.categories:
                video = destination / "videos" / category / split / word / word / (
                    f"{signer}-{word}-2023_01_01_12_00_00.001-0.mp4"
                )
                video.parent.mkdir(parents=True, exist_ok=True)
                video.write_bytes(b"synthetic fixture, not video")
        return destination

    def test_real_archive_layout_recovers_participant_not_word(self) -> None:
        word_dir = Path("hello")
        video = word_dir / "hello" / "gtsignstudy4a.9999-hello-2023_01_25_18_26_35.014-0.mp4"
        self.assertEqual("gtsignstudy4a.9999", recover_signer_id(video, word_dir))
        for bad in (
            word_dir / "hello" / "unknown.mp4",
            word_dir / "signer-123" / "clip.mp4",
            word_dir / video.name,
            word_dir / "book" / video.name,
            word_dir / "hello" / video.name.replace("-hello-", "-book-"),
        ):
            with self.subTest(path=bad), self.assertRaisesRegex(ValueError, "cannot recover"):
                recover_signer_id(bad, word_dir)

    def test_tar_to_manifest_preserves_participant_across_words_and_splits(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            words = self.config.select_words(["HELLO", "BOOK"])
            for word, split in zip(words, ("train", "test")):
                target = build_download_targets(self.config, [word], ["non-game"], [split], root)[0]
                member = f"{word.popsign_slug}/study.9999-{word.popsign_slug}-2023_01_01_12_00_00.001-0.mp4"
                make_tar(target.archive_path, [(member, b"synthetic non-video", "file")])
                write_checksum(target.archive_path, sha256_file(target.archive_path))
                with patch("signcoach_benchmark.download.requests.get") as get:
                    self.assertEqual("prepared", prepare_target(target).status)
                    get.assert_not_called()
            manifest = root / "manifest.csv"
            self.assertEqual(2, build_manifest(self.config, root, manifest, words))
            with manifest.open(newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual({"study.9999"}, {row["signer_id"] for row in rows})
            self.assertTrue(all(row["variant_status"] == "unreviewed" for row in rows))
            self.assertEqual({"signer_leakage"}, {issue.code for issue in validate_manifest(self.config, manifest).issues})

    def test_fixture_builds_contract_manifest_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dataset_root = self._make_fixture(temp)
            manifest_path = dataset_root / "benchmark_manifest.csv"

            row_count = build_manifest(self.config, dataset_root, manifest_path, self.words)
            report = validate_manifest(self.config, manifest_path)

            self.assertEqual(6, row_count)
            self.assertTrue(report.valid, [issue.format() for issue in report.issues])
            with manifest_path.open("r", encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                self.assertEqual(MANIFEST_COLUMNS, tuple(reader.fieldnames or ()))
                rows = list(reader)

            game = next(row for row in rows if row["target_word"] == "THANKYOU" and row["sample_type"] == "positive")
            variant = next(row for row in rows if row["target_word"] == "THANKYOU" and row["sample_type"] == "hard_negative")
            self.assertEqual("THANKYOU", game["performed_word"])
            self.assertEqual("true", game["expected_pass"])
            self.assertEqual("target_variant", game["variant_status"])
            self.assertEqual("", variant["performed_word"])
            self.assertEqual("", variant["expected_pass"])
            self.assertEqual("unreviewed", variant["variant_status"])

    def test_game_labels_use_product_keys_not_asl_citizen_lookup_words(self) -> None:
        words = self.config.select_words(["THANKYOU", "MOM", "DAD"])
        lookup_words = {"THANKYOU": "THANK YOU", "MOM": "MOTHER", "DAD": "FATHER"}
        with tempfile.TemporaryDirectory() as temp:
            dataset_root = Path(temp) / "popsign"
            manifest_path = dataset_root / "benchmark_manifest.csv"
            for word in words:
                video_path = (
                    dataset_root
                    / "videos"
                    / "game"
                    / "train"
                    / word.popsign_slug
                    / word.popsign_slug
                    / f"study.010-{word.popsign_slug}-2023_01_01_12_00_00.001-0.mp4"
                )
                video_path.parent.mkdir(parents=True, exist_ok=True)
                video_path.write_text("fake video", encoding="utf-8")

            self.assertEqual(3, build_manifest(self.config, dataset_root, manifest_path, words))
            with manifest_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(
                {"THANKYOU": "THANKYOU", "MOM": "MOM", "DAD": "DAD"},
                {row["target_word"]: row["performed_word"] for row in rows},
            )
            self.assertTrue(validate_manifest(self.config, manifest_path).valid)

            for target_word, lookup_word in lookup_words.items():
                with self.subTest(target_word=target_word):
                    altered_rows = [dict(row) for row in rows]
                    next(row for row in altered_rows if row["target_word"] == target_word)[
                        "performed_word"
                    ] = lookup_word
                    invalid_path = dataset_root / f"invalid-{target_word.lower()}.csv"
                    write_manifest(invalid_path, altered_rows)
                    codes = {
                        issue.code for issue in validate_manifest(self.config, invalid_path).issues
                    }
                    self.assertIn("performed_word_product_key", codes)
                    self.assertIn("variant_performed_word", codes)

    def test_valid_alternate_performed_word_must_equal_target_word(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dataset_root = self._make_fixture(temp)
            manifest_path = dataset_root / "benchmark_manifest.csv"
            build_manifest(self.config, dataset_root, manifest_path, self.words)
            with manifest_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            game = next(row for row in rows if row["target_word"] == "THANKYOU" and row["sample_type"] == "positive")
            game["variant_status"] = "valid_alternate"
            game["performed_word"] = "HELLO"
            write_manifest(manifest_path, rows)

            report = validate_manifest(self.config, manifest_path)

            self.assertFalse(report.valid)
            self.assertIn("variant_performed_word", {issue.code for issue in report.issues})

    def test_signer_leakage_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dataset_root = self._make_fixture(temp)
            manifest_path = dataset_root / "benchmark_manifest.csv"
            build_manifest(self.config, dataset_root, manifest_path, self.words)

            with manifest_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            for row in rows:
                if row["split"] == "val":
                    row["signer_id"] = "study.001"
            with manifest_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)

            report = validate_manifest(self.config, manifest_path)

            self.assertFalse(report.valid)
            self.assertIn("signer_leakage", {issue.code for issue in report.issues})

    def test_unreviewed_variant_cannot_have_expected_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dataset_root = self._make_fixture(temp)
            manifest_path = dataset_root / "benchmark_manifest.csv"
            build_manifest(self.config, dataset_root, manifest_path, self.words)
            with manifest_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            variant = next(row for row in rows if row["variant_status"] == "unreviewed")
            variant["expected_pass"] = "false"
            with manifest_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)

            report = validate_manifest(self.config, manifest_path)

            self.assertFalse(report.valid)
            self.assertIn("variant_expected_pass", {issue.code for issue in report.issues})

    def test_validate_cli_returns_nonzero_with_clear_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing.csv"
            stderr = StringIO()
            with redirect_stderr(stderr), redirect_stdout(StringIO()):
                exit_code = main(["validate", "--manifest", str(missing)])
            self.assertEqual(1, exit_code)
            self.assertIn("Manifest invalid", stderr.getvalue())
            self.assertIn("manifest_missing", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
