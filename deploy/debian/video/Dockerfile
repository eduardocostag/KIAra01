# Kiara video service: orchestration only (no GPU here). Python stdlib HTTP + gradio_client + ffmpeg.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir gradio_client==2.7.2 \
 && useradd --uid 10001 --create-home kiara && mkdir -p /data && chown kiara /data
COPY server.py /app/server.py
USER kiara
ENV VIDEO_DATA=/data PYTHONUNBUFFERED=1 HF_HUB_DISABLE_TELEMETRY=1 GRADIO_ANALYTICS_ENABLED=False
CMD ["python", "/app/server.py"]
