"""Local 30-word action-similarity demo API."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
import html
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path

import numpy as np
import requests
from fastapi import FastAPI, HTTPException, Body, Query
from pydantic import StrictBool
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from pydantic import BaseModel
from signcoach_benchmark.config import load_config

from . import scoring
from .attempt_store import AttemptStore
from .diagnostics import diagnostics
from .embedding_encoder import PoseEmbeddingEncoder
from .mediapipe_compat import get_holistic_module
from .preprocess import flatten_frame, frame_from_mediapipe_results, prepare_sequence
from .reference_index import ReferenceIndex


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REFERENCE_INDEX = PROJECT_ROOT / "deploy/reference/index.npz"
DEFAULT_REFERENCE_MANIFEST = PROJECT_ROOT / "deploy/reference/manifest.json"
DEFAULT_WEB_DIR = PROJECT_ROOT / "web-app/build"

CURATED_UNSPLASH_IMAGES = {
    "hello": "https://images.unsplash.com/photo-1511632765486-a01980e01a18?auto=format&fit=crop&w=900&h=620&q=80",
    "goodbye": "https://images.unsplash.com/photo-1511632765486-a01980e01a18?auto=format&fit=crop&w=900&h=620&q=80",
    "please": "https://images.unsplash.com/photo-1425082661705-1834bfd09dca?auto=format&fit=crop&w=900&h=620&q=80",
    "thank you": "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=900&h=620&q=80",
    "sorry": "https://images.unsplash.com/photo-1493836512294-502baa1986e2?auto=format&fit=crop&w=900&h=620&q=80",
    "yes": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&h=620&q=80",
    "no": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&h=620&q=80",
    "okay": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&h=620&q=80",
    "again": "https://images.unsplash.com/photo-1506784983877-45594efa4cbe?auto=format&fit=crop&w=900&h=620&q=80",
    "help": "https://images.unsplash.com/photo-1544027993-37dbfe43562a?auto=format&fit=crop&w=900&h=620&q=80",
    "apple": "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?auto=format&fit=crop&w=900&h=620&q=80",
    "car": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=900&h=620&q=80",
    "bath": "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=900&h=620&q=80",
}


def normalize_label(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


_BENCHMARK_CONFIG = load_config()
REFERENCE_WORD_BY_PRODUCT_KEY = {
    word.target_word: word.asl_citizen_word for word in _BENCHMARK_CONFIG.words
}
PRODUCT_KEY_BY_REFERENCE_NORMALIZED = {
    normalize_label(word.asl_citizen_word): word.target_word for word in _BENCHMARK_CONFIG.words
}


MODEL_VERSION = "manual-baseline-v1"


@dataclass
class AttemptSession:
    target: str
    frames: deque = field(default_factory=lambda: deque(maxlen=48))
    lock: threading.Lock = field(default_factory=threading.Lock)
    seen: float = field(default_factory=time.monotonic)


class FeedbackRequest(BaseModel):
    useful: StrictBool


class PracticeAPI:
    def __init__(self, reference_index, db_path=None):
        self.reference_index = reference_index
        self.embedding_encoder = PoseEmbeddingEncoder(target_frames=scoring.TARGET_FRAMES_V1)
        self.store = AttemptStore(db_path or os.environ.get("SIGNCOACH_DB_PATH", "data/signcoach-demo.sqlite3"))
        self.sessions = {}
        self.lock = threading.Lock()
        self.signasl_cache = {}
        self.unsplash_cache = {}
        self.active_detector_attempt = None
        self.holistic = get_holistic_module().Holistic(
            static_image_mode=False, model_complexity=1, smooth_landmarks=True,
            enable_segmentation=False, refine_face_landmarks=True)

    @property
    def labels(self):
        return [word.target_word for word in _BENCHMARK_CONFIG.words]

    def close(self):
        self.holistic.close()

    def decode_image(self, raw):
        import cv2
        if not raw or not raw.startswith(b"\xff\xd8"):
            raise HTTPException(400, "Invalid JPEG")
        frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(400, "Could not decode JPEG")
        return frame

    def predict_frame(self, attempt_id, target, raw, final):
        import cv2
        started = time.perf_counter()
        if target not in self.labels:
            raise HTTPException(422, "Unknown canonical target_word")
        previous = self.store.get(attempt_id)
        if previous is not None:
            if previous['target_word'] != target:
                raise HTTPException(409, "attempt_id belongs to another target")
            return previous if final else None
        with self.lock:
            now = time.monotonic()
            for key, session in list(self.sessions.items()):
                if now - session.seen > 120 and not session.lock.locked():
                    del self.sessions[key]
                    if self.active_detector_attempt == key:
                        self.active_detector_attempt = None
            session = self.sessions.get(attempt_id)
            if session is None:
                if len(self.sessions) >= 128:
                    raise HTTPException(429, "Too many active attempts")
                session = AttemptSession(target)
                self.sessions[attempt_id] = session
            if session.target != target:
                raise HTTPException(409, "attempt_id belongs to another target")
            session.seen = now
        # Serialize only this attempt, including terminal persistence. No global
        # lock is held during preparation, embedding, search, or SQLite IO.
        with session.lock:
            previous = self.store.get(attempt_id)
            if previous is not None:
                if previous['target_word'] != target:
                    raise HTTPException(409, "attempt_id belongs to another target")
                return previous if final else None
            frame = self.decode_image(raw)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            with self.lock:
                if self.active_detector_attempt != attempt_id:
                    self.holistic.reset()
                    self.active_detector_attempt = attempt_id
                results = self.holistic.process(rgb)
                session.frames.append(flatten_frame(frame_from_mediapipe_results(results)))
                session.seen = time.monotonic()
            if not final:
                return None
            result, features = self.score_sequence(attempt_id, target, np.asarray(session.frames, dtype=np.float32))
            result['latency_ms'] = round((time.perf_counter() - started) * 1000, 3)
            self.store.save(result, features)
            session.frames.clear()
            return result

    def score_sequence(self, attempt_id, target, sequence):
        prepared = prepare_sequence(sequence, self.embedding_encoder.target_frames)
        measurements = scoring.measure_quality(prepared, original_frame_count=len(sequence))
        gate = scoring.quality_gate(measurements)
        features = dict(measurements.__dict__)
        baseline = search = None
        if gate.valid:
            embedding = self.embedding_encoder.encode_prepared_sequence(prepared)
            search = self.reference_index.search_target(REFERENCE_WORD_BY_PRODUCT_KEY[target], embedding)
            baseline = scoring.manual_baseline_score(search['target_similarity'], search['similarity_margin'])
            features.update({key: search[key] for key in ('target_similarity', 'best_other_similarity', 'similarity_margin')})
        result = {
            'attempt_id': attempt_id, 'target_word': target,
            'decision': baseline.decision if baseline else 'rerecord',
            'score': baseline.score if baseline else None, 'quality_valid': gate.valid,
            'diagnostics': diagnostics(measurements, gate, baseline, search),
            'nearest_confusion': PRODUCT_KEY_BY_REFERENCE_NORMALIZED[normalize_label(search['best_other_word'])] if search else None,
            'model_version': MODEL_VERSION, 'latency_ms': 0,
        }
        return result, features

    def get_signasl_video(self, slug: str) -> dict:
        clean_slug = re.sub(r"[^a-zA-Z0-9-]", "", slug.lower())
        if clean_slug in self.signasl_cache:
            return self.signasl_cache[clean_slug]

        page_url = f"https://www.signasl.org/sign/{clean_slug}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SignCoach/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Cookie": "cookieconsent_status=dismissed; cookieconsent_status=dismiss; CookieConsent=true; cookie_consent=true",
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

    def get_unsplash_image(self, query: str) -> tuple[bytes, str]:
        clean_query = self.clean_unsplash_query(query)
        if clean_query in self.unsplash_cache:
            return self.unsplash_cache[clean_query], "image/jpeg"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SignCoach/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        image_url = self.resolve_unsplash_image_url(clean_query, headers)
        return self.download_unsplash_image(clean_query, image_url, headers)

    def clean_unsplash_query(self, query: str) -> str:
        clean_query = re.sub(r"[^a-zA-Z0-9 -]", " ", query).strip().lower()
        clean_query = re.sub(r"\s+", " ", clean_query)
        return clean_query or "learning"

    def resolve_unsplash_image_url(self, clean_query: str, headers: dict[str, str]) -> str:
        search_url = f"https://unsplash.com/s/photos/{clean_query.replace(' ', '-')}"
        try:
            response = requests.get(search_url, headers=headers, timeout=12)
            response.raise_for_status()
        except requests.RequestException:
            image_url = CURATED_UNSPLASH_IMAGES.get(clean_query)
            if not image_url:
                raise HTTPException(status_code=502, detail="Could not search Unsplash")
            return image_url

        image_url = self.find_first_free_unsplash_image(response.text, headers)
        if not image_url:
            image_url = CURATED_UNSPLASH_IMAGES.get(clean_query)
            if not image_url:
                raise HTTPException(status_code=404, detail="No free Unsplash image found")
        return image_url

    def download_unsplash_image(self, cache_key: str, image_url: str, headers: dict[str, str]) -> tuple[bytes, str]:
        image_headers = {
            "User-Agent": headers["User-Agent"],
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://unsplash.com/",
        }
        try:
            image_response = requests.get(image_url, headers=image_headers, timeout=15)
            image_response.raise_for_status()
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"Could not load Unsplash image: {exc}") from exc

        content_type = image_response.headers.get("content-type", "image/jpeg").split(";", 1)[0]
        image_bytes = image_response.content
        self.unsplash_cache[cache_key] = image_bytes
        return image_bytes, content_type

    def find_first_free_unsplash_image(self, search_html: str, headers: dict[str, str]) -> str | None:
        candidates = re.finditer(r"https://images\.unsplash\.com/photo-[^\"'\\<>\s]+", search_html)
        seen: set[str] = set()
        for match in candidates:
            raw_url = html.unescape(match.group(0)).replace("\\u0026", "&").replace("&amp;", "&")
            image_url = raw_url.split("?", 1)[0]
            if image_url in seen:
                continue
            seen.add(image_url)

            context_start = max(0, match.start() - 2500)
            context_end = min(len(search_html), match.end() + 1200)
            context = html.unescape(search_html[context_start:context_end]).lower()
            if any(marker in context for marker in ["unsplash+", "unsplash plus", "getty images", "premium", "plus.unsplash.com"]):
                continue
            if any(skip in image_url for skip in ["profile", "avatar"]):
                continue
            return f"{image_url}?auto=format&fit=crop&w=900&h=620&q=80"

        return None


def build_app(reference_index: ReferenceIndex, db_path=None, *, web_dir=DEFAULT_WEB_DIR) -> FastAPI:
    web_dir = Path(web_dir)
    if not (web_dir / "index.html").is_file() or not (web_dir / "assets").is_dir():
        raise FileNotFoundError(f"Frontend build missing at {web_dir}; run npm ci and npm run build in web-app.")
    api = PracticeAPI(reference_index, db_path)
    app = FastAPI(title="SignLearn ASL Practice API")

    @app.on_event("shutdown")
    def shutdown() -> None:
        api.close()

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "model_version": MODEL_VERSION}

    @app.get("/api/labels")
    def labels_route() -> dict:
        return {"labels": api.labels}

    @app.get("/api/signasl/video/{slug}")
    def signasl_video(slug: str) -> dict:
        return api.get_signasl_video(slug)

    @app.get("/api/unsplash/image/{query}")
    def unsplash_image(query: str) -> Response:
        image_bytes, content_type = api.get_unsplash_image(query)
        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )

    @app.get("/api/unsplash/url/{query}")
    def unsplash_url(query: str) -> dict:
        clean_query = api.clean_unsplash_query(query)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SignCoach/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        image_url = api.resolve_unsplash_image_url(clean_query, headers)
        return {
            "query": clean_query,
            "search_url": f"https://unsplash.com/s/photos/{clean_query.replace(' ', '-')}",
            "image_url": image_url,
        }

    @app.post("/api/practice/frame")
    def practice_frame(attempt_id: uuid.UUID, target_word: str, final: bool = False,
                       raw: bytes = Body(media_type="image/jpeg")):
        result = api.predict_frame(str(attempt_id), target_word, raw, final)
        return result if result is not None else Response(status_code=204)

    @app.get("/api/attempts")
    def attempts(limit: int = Query(20, ge=1, le=100)):
        return {"attempts": api.store.recent(limit)}

    @app.patch("/api/attempts/{attempt_id}/feedback")
    def feedback(attempt_id: uuid.UUID, payload: FeedbackRequest):
        if not api.store.feedback(str(attempt_id), payload.useful):
            raise HTTPException(404, "Attempt not found")
        return Response(status_code=204)

    # Reserve API namespace before static mounting: unknown APIs must never serve HTML.
    @app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
    def unknown_api(path: str):
        raise HTTPException(404, "API not found")

    app.mount('/', StaticFiles(directory=web_dir, html=True), name='web')
    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-index", type=Path, default=DEFAULT_REFERENCE_INDEX)
    parser.add_argument("--reference-manifest", type=Path, default=DEFAULT_REFERENCE_MANIFEST)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    return parser.parse_args()


def main() -> None:
    import uvicorn

    args = parse_args()
    if not args.reference_index.is_file() or not args.reference_manifest.is_file():
        raise FileNotFoundError(
            f"Reference index not found: {args.reference_index} and {args.reference_manifest}. "
            "Supply separately authorized index.npz and manifest.json in deploy/reference before startup; this code release contains no reference data."
        )
    reference_index = ReferenceIndex.load(args.reference_index, args.reference_manifest, allowed_words=tuple(REFERENCE_WORD_BY_PRODUCT_KEY.values()))
    print(f"Loading reference index: {args.reference_index}")
    app = build_app(reference_index)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
