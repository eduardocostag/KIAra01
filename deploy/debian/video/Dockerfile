# Kiara video service: orchestration (no GPU here). Python stdlib HTTP + gradio_client + ffmpeg, plus the
# Video Studio (headless Chromium + Edge TTS) for the narrated chat videos.
# Build context: run sync_studio.sh first; it copies app/video_studio, app/voice/kiara_style.py and the screen
# library from the repo into ./studio (not committed).
FROM python:3.12-slim
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-inter fonts-noto-core \
 && pip install --no-cache-dir gradio_client==2.7.2 playwright==1.62.0 edge-tts==7.3.1 \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --create-home kiara && mkdir -p /data && chown kiara /data \
 && echo /app > /usr/local/lib/python3.12/site-packages/kiara-studio.pth
COPY studio/app /app/app
COPY server.py /app/server.py
USER kiara
ENV VIDEO_DATA=/data PYTHONUNBUFFERED=1 HF_HUB_DISABLE_TELEMETRY=1 GRADIO_ANALYTICS_ENABLED=False \
    KIARA_VIDEO_CRF=24 KIARA_VIDEO_PRESET=veryfast
CMD ["python", "/app/server.py"]
