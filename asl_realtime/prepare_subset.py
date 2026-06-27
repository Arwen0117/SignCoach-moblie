"""Extract only the Kaggle ASL files needed for an MVP training subset."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd

from .kaggle_dataset import build_subset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True, help="Path to asl-signs.zip")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-classes", type=int, default=40)
    parser.add_argument("--max-samples-per-class", type=int, default=120)
    parser.add_argument("--seed", type=int, default=13)
    return parser.parse_args()


def read_json_from_zip(zf: zipfile.ZipFile, name: str) -> dict[str, int]:
    with zf.open(name) as f:
        raw = json.load(f)
    return {str(k): int(v) for k, v in raw.items()}


def read_csv_from_zip(zf: zipfile.ZipFile, name: str) -> pd.DataFrame:
    with zf.open(name) as f:
        return pd.read_csv(f)


def copy_zip_entry(zf: zipfile.ZipFile, member: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member) as src, output_path.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(args.zip) as zf:
        label_map = read_json_from_zip(zf, "sign_to_prediction_index_map.json")
        train_df = read_csv_from_zip(zf, "train.csv")
        temp_train_csv = args.output_dir / "_all_train.csv"
        train_df.to_csv(temp_train_csv, index=False)

        subset, labels = build_subset(
            temp_train_csv,
            label_map,
            max_classes=args.max_classes,
            max_samples_per_class=args.max_samples_per_class,
            seed=args.seed,
        )
        temp_train_csv.unlink(missing_ok=True)

        (args.output_dir / "sign_to_prediction_index_map.json").write_text(
            json.dumps(label_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        subset.drop(columns=["local_label"]).to_csv(args.output_dir / "train.csv", index=False)

        missing = []
        for path in subset["path"].tolist():
            if path not in zf.namelist():
                missing.append(path)
                continue
            copy_zip_entry(zf, path, args.output_dir / path)

    if missing:
        preview = "\n".join(missing[:5])
        raise FileNotFoundError(f"{len(missing)} selected files were missing from the zip. First entries:\n{preview}")

    print(f"Created subset in: {args.output_dir}")
    print(f"Classes: {len(labels)}")
    print(f"Samples: {len(subset)}")
    print("Now train with:")
    print(f"python -m asl_realtime.train --data-dir {args.output_dir} --output-dir runs/asl_mvp")


if __name__ == "__main__":
    main()

