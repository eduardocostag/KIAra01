# Kiara Maps browser: Debian's Chromium + a small fixed-address CDP proxy (proxy.py).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium fonts-liberation fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir websockets==15.0.1 \
 && useradd --uid 10002 --create-home kiara
COPY proxy.py /app/proxy.py
USER kiara
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/proxy.py"]
