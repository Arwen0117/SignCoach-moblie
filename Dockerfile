FROM node:24-bookworm-slim AS frontend
WORKDIR /build/web-app
COPY web-app/package.json web-app/package-lock.json ./
RUN npm ci
COPY web-app/index.html web-app/postcss.config.js web-app/tailwind.config.js ./
COPY web-app/src ./src
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PORT=8000 SIGNCOACH_DB_PATH=/data/signcoach-demo.sqlite3 \
    MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app
# OpenCV's non-headless wheel (required by MediaPipe) needs GL/GLib;
# libgomp supports CPU numerical libraries. No GPU or training stack.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-demo.txt ./
RUN pip install --no-cache-dir -r requirements-demo.txt && pip check \
    && python -c "import cv2, mediapipe; m=mediapipe.solutions.holistic.Holistic(); m.close()"
COPY asl_realtime ./asl_realtime
COPY signcoach_benchmark/__init__.py signcoach_benchmark/config.py signcoach_benchmark/vocabulary.json ./signcoach_benchmark/
# Authorized references are supplied separately at /app/deploy/reference at runtime.
COPY deploy/reference/index.npz deploy/reference/manifest.json ./deploy/reference/
COPY --from=frontend /build/web-app/build ./web-app/build
RUN useradd --create-home --uid 10001 demo && mkdir /data && chown demo:demo /data
USER demo
EXPOSE 8000
CMD ["python", "-m", "asl_realtime.api_server", "--host", "0.0.0.0"]
