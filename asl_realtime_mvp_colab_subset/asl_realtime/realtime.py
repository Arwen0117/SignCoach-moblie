"""Realtime webcam ASL sign recognition demo."""

from __future__ import annotations

import argparse
import time
from collections import deque
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from .fusion import SubtitleSmoother
from .infer import SignRecognizer
from .preprocess import flatten_frame, frame_from_mediapipe_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--labels", type=Path, default=None)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--window-seconds", type=float, default=1.6)
    parser.add_argument("--step-seconds", type=float, default=0.35)
    parser.add_argument("--min-confidence", type=float, default=0.55)
    parser.add_argument("--stable-windows", type=int, default=3)
    parser.add_argument("--device", default=None)
    return parser.parse_args()


def draw_subtitle(frame: np.ndarray, subtitle: str, prediction: str, confidence: float) -> None:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - 120), (w, h), (0, 0, 0), thickness=-1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, dst=frame)
    cv2.putText(
        frame,
        f"{prediction} {confidence:.2f}",
        (24, h - 78),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (120, 220, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        subtitle or "Waiting for a stable sign...",
        (24, h - 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def main() -> None:
    args = parse_args()
    recognizer = SignRecognizer(args.checkpoint, args.labels, args.device)
    smoother = SubtitleSmoother(
        min_confidence=args.min_confidence,
        stable_windows=args.stable_windows,
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera {args.camera}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 1:
        fps = 30.0
    max_buffer = int(max(8, fps * args.window_seconds * 2))
    keypoint_buffer: deque[tuple[float, np.ndarray]] = deque(maxlen=max_buffer)
    last_infer = 0.0
    latest_label = ""
    latest_conf = 0.0

    mp_holistic = mp.solutions.holistic
    with mp_holistic.Holistic(
        static_image_mode=False,
        model_complexity=1,
        smooth_landmarks=True,
        enable_segmentation=False,
        refine_face_landmarks=True,
    ) as holistic:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            now = time.time()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = holistic.process(rgb)
            keypoint_buffer.append((now, flatten_frame(frame_from_mediapipe_results(results))))

            if now - last_infer >= args.step_seconds:
                window_start = now - args.window_seconds
                sequence = np.array([kp for ts, kp in keypoint_buffer if ts >= window_start], dtype=np.float32)
                if len(sequence) >= 4:
                    latest_label, latest_conf = recognizer.predict(sequence)
                    smoother.update(latest_label, latest_conf)
                last_infer = now

            draw_subtitle(frame, smoother.text, latest_label, latest_conf)
            cv2.imshow("Realtime ASL Translator MVP", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                smoother.clear()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

