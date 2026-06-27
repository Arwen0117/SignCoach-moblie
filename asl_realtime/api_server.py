"""Local API server for connecting the trained ASL model to the web app."""

from __future__ import annotations

import argparse
import base64
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path

import cv2
import numpy as np
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .infer import SignRecognizer
from .mediapipe_compat import get_holistic_module
from .preprocess import flatten_frame, frame_from_mediapipe_results


DEFAULT_CHECKPOINTS = [
    Path("runs/asl_mvp/best.pt"),
    Path("asl_realtime_mvp_colab_subset/runs/runs/asl_mvp/best.pt"),
    Path("asl_realtime_mvp_colab_subset/runs/asl_mvp/best.pt"),
]


def normalize_label(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


class FrameRequest(BaseModel):
    image: str
    target: str
    session_id: str | None = None


class PracticeAPI:
    def __init__(self, checkpoint: Path, labels: Path | None, max_frames: int = 48):
        self.recognizer = SignRecognizer(checkpoint, labels)
        self.max_frames = max_frames
        self.sessions: dict[str, deque[np.ndarray]] = {}
        self.last_seen: dict[str, float] = {}
        self.signasl_cache: dict[str, dict] = {}
        self.lock = threading.Lock()
        holistic = get_holistic_module()
        self.holistic = holistic.Holistic(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=False,
            refine_face_landmarks=True,
        )

    @property
    def labels(self) -> list[str]:
        return self.recognizer.labels

    def close(self) -> None:
        self.holistic.close()

    def decode_image(self, image_data: str) -> np.ndarray:
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        try:
            raw = base64.b64decode(image_data)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Invalid base64 image") from exc

        array = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail="Could not decode image")
        return frame

    def predict_frame(self, payload: FrameRequest) -> dict:
        session_id = payload.session_id or str(uuid.uuid4())
        target_norm = normalize_label(payload.target)
        label_norms = {normalize_label(label) for label in self.labels}
        target_supported = target_norm in label_norms

        frame = self.decode_image(payload.image)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        with self.lock:
            results = self.holistic.process(rgb)
            keypoints = flatten_frame(frame_from_mediapipe_results(results))
            buffer = self.sessions.setdefault(session_id, deque(maxlen=self.max_frames))
            buffer.append(keypoints)
            self.last_seen[session_id] = time.time()
            self.cleanup_sessions()

            if len(buffer) < 6:
                return {
                    "session_id": session_id,
                    "ready": False,
                    "target_supported": target_supported,
                    "prediction": None,
                    "confidence": 0.0,
                    "score": 0,
                    "message": "Collecting motion window",
                    "labels": self.labels,
                }

            sequence = np.array(buffer, dtype=np.float32)
            prediction, confidence = self.recognizer.predict(sequence)

        prediction_norm = normalize_label(prediction)
        target_match = prediction_norm == target_norm
        if target_match:
            score = int(round(72 + min(confidence, 1.0) * 27))
        else:
            # Keep non-matching signs visibly lower while still reflecting confidence.
            score = int(round(min(0.62, confidence) * 100))

        if not target_supported:
            message = f"'{payload.target}' is not in this checkpoint label set."
        elif target_match:
            message = f"Detected {prediction}."
        else:
            message = f"Detected {prediction}; target is {payload.target}."

        return {
            "session_id": session_id,
            "ready": True,
            "target_supported": target_supported,
            "target_match": target_match,
            "prediction": prediction,
            "confidence": confidence,
            "score": score,
            "message": message,
            "labels": self.labels,
        }

    def cleanup_sessions(self) -> None:
        now = time.time()
        expired = [session_id for session_id, seen in self.last_seen.items() if now - seen > 120]
        for session_id in expired:
            self.sessions.pop(session_id, None)
            self.last_seen.pop(session_id, None)

    def get_signasl_video(self, slug: str) -> dict:
        clean_slug = re.sub(r"[^a-zA-Z0-9-]", "", slug.lower())
        if clean_slug in self.signasl_cache:
            return self.signasl_cache[clean_slug]

        page_url = f"https://www.signasl.org/sign/{clean_slug}"
        headers = {
            "User-Agent": "Mozilla/5.0 SignLearnCoach/0.1",
            "Cookie": "cookieconsent_status=dismiss; CookieConsent=true",
        }
        try:
            response = requests.get(page_url, headers=headers, timeout=12)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"Could not load SignASL page: {exc}") from exc

        html = response.text
        patterns = [
            r'<source[^>]+src=["\']([^"\']+\.(?:mp4|webm)[^"\']*)["\']',
            r'<video[^>]+src=["\']([^"\']+\.(?:mp4|webm)[^"\']*)["\']',
            r'["\'](https?://[^"\']+\.(?:mp4|webm)[^"\']*)["\']',
        ]
        video_url = None
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                video_url = match.group(1)
                break

        if video_url and video_url.startswith("//"):
            video_url = f"https:{video_url}"
        elif video_url and video_url.startswith("/"):
            video_url = f"https://www.signasl.org{video_url}"

        payload = {
            "slug": clean_slug,
            "page_url": page_url,
            "video_url": video_url,
            "found": bool(video_url),
        }
        self.signasl_cache[clean_slug] = payload
        return payload


def resolve_checkpoint(path: Path | None) -> Path:
    if path is not None:
        return path
    for candidate in DEFAULT_CHECKPOINTS:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find best.pt. Pass --checkpoint explicitly.")


def build_app(checkpoint: Path, labels: Path | None = None) -> FastAPI:
    api = PracticeAPI(checkpoint, labels)
    app = FastAPI(title="SignLearn ASL Practice API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("shutdown")
    def shutdown() -> None:
        api.close()

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "labels": api.labels}

    @app.get("/api/labels")
    def labels_route() -> dict:
        return {"labels": api.labels}

    @app.get("/api/signasl/video/{slug}")
    def signasl_video(slug: str) -> dict:
        return api.get_signasl_video(slug)

    @app.post("/api/practice/frame")
    def practice_frame(payload: FrameRequest) -> dict:
        return api.predict_frame(payload)

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--labels", type=Path, default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    import uvicorn

    args = parse_args()
    checkpoint = resolve_checkpoint(args.checkpoint)
    print(f"Loading ASL checkpoint: {checkpoint}")
    app = build_app(checkpoint, args.labels)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
