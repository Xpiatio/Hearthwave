ARG COMPUTE_BACKEND=cpu

# ── Stage 1: builder ────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

ARG COMPUTE_BACKEND

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libportaudio2 \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

RUN if [ "$COMPUTE_BACKEND" = "cuda" ]; then \
        pip install --no-cache-dir --prefix=/install onnxruntime-gpu; \
    elif [ "$COMPUTE_BACKEND" = "openvino" ]; then \
        pip install --no-cache-dir --prefix=/install openvino onnxruntime-openvino; \
    fi

# ── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime libs + gosu (privilege-drop helper for entrypoint)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libportaudio2 \
        libsndfile1 \
        espeak-ng \
        espeak-ng-data \
        pulseaudio-utils \
        gosu \
    && rm -rf /var/lib/apt/lists/* \
    # audio group GID 29 is standard on Debian/Ubuntu — required for /dev/snd access
    && groupadd -g 29 audio 2>/dev/null || true \
    && useradd -u 1000 -G audio -d /app -s /sbin/nologin -M appuser

COPY --from=builder /install /usr/local

WORKDIR /app

COPY backend/ /app/backend/

# Pre-create data dirs with correct ownership; volume mounts may shadow these,
# so docker-entrypoint.sh re-creates them at runtime after the mount is visible.
RUN mkdir -p /data/voiceprints /data/journals /data/public \
    && chown -R appuser:appuser /app /data

COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8765

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8765"]
