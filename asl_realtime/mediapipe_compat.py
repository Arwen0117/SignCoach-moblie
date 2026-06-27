"""Compatibility helpers for different MediaPipe package layouts."""

from __future__ import annotations

from importlib import import_module
import sys


def get_holistic_module():
    errors = []
    try:
        import mediapipe as mp

        return mp.solutions.holistic
    except Exception as exc:  # noqa: BLE001
        errors.append(f"mp.solutions.holistic failed: {exc}")

    for module_name in (
        "mediapipe.solutions.holistic",
        "mediapipe.python.solutions.holistic",
    ):
        try:
            return import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{module_name} failed: {exc}")

    details = "\n".join(errors)
    raise RuntimeError(
        "Could not import MediaPipe Holistic. This backend needs the classic "
        "MediaPipe solutions API to extract landmarks for the trained model.\n"
        f"Current Python: {sys.executable}\n"
        f"Version: {sys.version}\n"
        "Recommended fix on Windows: create a Python 3.10 or 3.11 virtual "
        "environment, then reinstall requirements.\n"
        f"Import attempts:\n{details}"
    )
