ARG COMPUTE_BACKEND=cpu

# ── Stage 1: builder ────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

ARG COMPUTE_BACKEND

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

# Compute-backend extras
RUN if [ "$COMPUTE_BACKEND" = "cuda" ]; then \
        pip install --no-cache-dir --prefix=/install onnxruntime-gpu; \
    elif [ "$COMPUTE_BACKEND" = "openvino" ]; then \
        pip install --no-cache-dir --prefix=/install openvino onnxruntime-openvino; \
    fi

# ── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy backend source
COPY backend/ /app/backend/

# Mount point for persistent data (contacts.json, config.json)
RUN mkdir -p /data

EXPOSE 8765

CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8765"]
