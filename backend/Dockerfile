# ===== Stage 1: Frontend build =====
# To use a Docker Hub mirror, add --build-arg REGISTRY=mirror.example.com/library/
ARG REGISTRY=
FROM --platform=$BUILDPLATFORM ${REGISTRY}node:20-slim AS frontend
WORKDIR /build
COPY frontend/ .
RUN npm ci && npm run build

# ===== Stage 2: Python runtime =====
FROM ${REGISTRY}python:3.12-slim AS backend

# Domestic mirror acceleration
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources || true
RUN rm -f /etc/apt/apt.conf.d/docker-clean 2>/dev/null; \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libstdc++6 \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pre-install PaddlePaddle + PaddleOCR (large download)
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple paddlepaddle==3.2.1 paddleocr

# Then the rest
COPY backend/requirements.txt .
RUN sed -i '/paddleocr/d' requirements.txt && pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# Pre-download PaddleOCR model
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='ch')" 2>/dev/null || true

COPY backend/ .
COPY --from=frontend /build/dist /app/static

EXPOSE 8000

# Default data dirs (overridable via volumes)
ENV INDEX_DIR=/data/index
ENV DATA_DIR=/data/app
ENV OCR_LANG=ch
ENV SCHEDULED_SCAN_TIME=00:00
ENV OCR_CONCURRENT=2

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
