"""Train the first-version ASL isolated sign classifier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from .kaggle_dataset import KaggleASLDataset, build_subset, load_label_map, save_labels
from .model import build_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=64)
    parser.add_argument("--max-classes", type=int, default=40)
    parser.add_argument("--max-samples-per-class", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def run_epoch(model, loader, criterion, optimizer, device: str, train: bool) -> tuple[float, float]:
    model.train(train)
    total_loss = 0.0
    total_correct = 0
    total_count = 0

    with torch.set_grad_enabled(train):
        for x, y in tqdm(loader, leave=False):
            x = x.to(device)
            y = y.to(device)
            logits = model(x)
            loss = criterion(logits, y)

            if train:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

            total_loss += loss.item() * x.size(0)
            total_correct += (logits.argmax(dim=1) == y).sum().item()
            total_count += x.size(0)

    return total_loss / max(total_count, 1), total_correct / max(total_count, 1)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    label_map = load_label_map(args.data_dir)
    rows, labels = build_subset(
        args.data_dir / "train.csv",
        label_map,
        max_classes=args.max_classes,
        max_samples_per_class=args.max_samples_per_class,
    )

    train_rows, val_rows = train_test_split(
        rows,
        test_size=args.val_size,
        random_state=13,
        stratify=rows["local_label"],
    )

    save_labels(labels, args.output_dir / "labels.json")
    with (args.output_dir / "run_config.json").open("w", encoding="utf-8") as f:
        json.dump(vars(args) | {"num_classes": len(labels)}, f, default=str, indent=2)

    train_ds = KaggleASLDataset(args.data_dir, train_rows, args.frames)
    val_ds = KaggleASLDataset(args.data_dir, val_rows, args.frames)
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=args.device == "cuda",
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=args.device == "cuda",
    )

    model = build_model(num_classes=len(labels)).to(args.device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    best_acc = 0.0
    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer, args.device, train=True)
        val_loss, val_acc = run_epoch(model, val_loader, criterion, optimizer, args.device, train=False)
        print(
            f"epoch={epoch:03d} "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
        )

        if val_acc >= best_acc:
            best_acc = val_acc
            torch.save(
                {
                    "model": model.state_dict(),
                    "labels": labels,
                    "frames": args.frames,
                    "num_classes": len(labels),
                    "best_acc": best_acc,
                },
                args.output_dir / "best.pt",
            )

    print(f"best_val_acc={best_acc:.4f}")


if __name__ == "__main__":
    main()

