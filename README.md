[🇨🇳 中文](README_ZH.md)

# FullText Search

A Docker-deployed full-text search service with OCR support, designed for indexing and managing documents on NAS.

## Features

- **Full-text search** — Tantivy engine, BM25 ranking, Chinese word segmentation, search suggestions
- **OCR support** — PaddleOCR (ONNX accelerated) for scanned PDFs and images
- **Multi-format** — PDF, Office (docx/xlsx/pptx), plain text, images
- **Real-time monitoring** — Automatic detection of file changes, scheduled full scans
- **Web UI** — React SPA with list/file view toggle
- **REST API** — Complete search, indexing, and management API
- **File management** — Duplicate detection, recent activity, OCR quality report, status filtering
- **Authentication** — Password login, changeable password
- **Batch download** — Select multiple files and download as ZIP
- **Auto backup** — Scheduled index backups, manual trigger supported
- **Docker deployment** — amd64 image, cross-architecture index migration

## Quick Start

```bash
# Clone
git clone https://github.com/Gray-Chan-sh/fulltext-search.git
cd fulltext-search

# (Optional) Configure environment
cp .env.example .env

# One-click deploy
./scripts/deploy.sh

# Or build manually
docker compose up --build

# Access
# http://localhost:8080  — Web UI
# Default password: admin
```

## Docker Image Usage

### Build from Source

```bash
git clone https://github.com/Gray-Chan-sh/fulltext-search.git
cd fulltext-search
docker buildx build --platform linux/amd64 -t fulltext-search .
```

### Run with Docker CLI

```bash
mkdir -p ./data/{docs,app_data,index_data}
docker run -d \
  --name fulltext-search \
  -p 8080:8000 \
  -v $(pwd)/data/docs:/data/docs:ro \
  -v $(pwd)/data/app_data:/data/app \
  -v $(pwd)/data/index_data:/data/index \
  -e OCR_LANG=ch \
  -e OCR_CONCURRENT=2 \
  -e SCHEDULED_SCAN_TIME=00:00 \
  --memory=4g \
  fulltext-search
```

### Run with Docker Compose (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/Gray-Chan-sh/fulltext-search/main/docker-compose.yml -o docker-compose.yml
mkdir -p ./data/docs
docker compose up --build -d
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Host port |
| `DATA_DIR` | `./data/docs` | Document directory path |
| `OCR_LANG` | `ch` | OCR language (ch/en/japan/korean) |
| `OCR_CONCURRENT` | `2` | OCR concurrency (auto-adjusts on OOM) |
| `SCHEDULED_SCAN_TIME` | `00:00` | Daily scheduled scan time |

### Cross-architecture Build

Build amd64 image on Apple Silicon Mac:

```bash
docker buildx build --platform linux/amd64 -t fulltext-search .
docker save fulltext-search | gzip > fulltext-search.tar.gz
```

### Data Persistence

```
data/
├── docs/          → /data/docs  (readonly, documents)
├── app_data/      → /data/app   (SQLite + settings)
└── index_data/    → /data/index (Tantivy search index)
```

Data survives container restarts. Migrate by copying the entire `data/` directory:

```bash
rsync -avz ./data/ user@nas:/path/to/fulltext-search/data/
```

### Memory Limits

PaddleOCR is memory-intensive. For low-memory devices (e.g. J4125 + 3GB):

```bash
OCR_CONCURRENT=1 docker compose up -d
```

### Multiple Document Directories

Add to `volumes` in `docker-compose.yml`. Directories are auto-registered on startup:

```yaml
volumes:
  - /path/to/contracts:/data/contracts:ro
  - /path/to/reports:/data/reports:ro
```

## Settings

Configurable via Web UI Settings page:

| Setting | Description |
|---|---|
| OCR language | Chinese / English / Japanese / Korean |
| OCR concurrency | Auto-suggested based on available memory |
| Scheduled scan | Daily full scan |
| Exclude patterns | Glob patterns to exclude files from indexing |
| Auto backup | Scheduled index backup |
| Theme | Light / Dark / System |

## Data Migration

Index data can be migrated across machines (e.g. from Mac to NAS):

```bash
# Build and index on Mac
docker buildx build --platform linux/amd64 -t fulltext-search .
docker run -d \
  -v /path/to/docs:/data/docs:ro \
  -v $(pwd)/data/app_data:/data/app \
  -v $(pwd)/data/index_data:/data/index \
  fulltext-search

# Migrate data
rsync -avz ./data/ user@nas:/path/to/fulltext-search/data/

# Start on NAS
docker compose up -d
```

## Directory Structure

```
backend/
  app/
    main.py          — FastAPI entry point
    config.py        — Configuration
    routes/          — API routes
    service/         — Business logic
    extractor/       — Text extraction
    models/          — Pydantic models
frontend/
  src/
    pages/           — Page components
    components/      — Shared components
    api/client.ts    — API client
```

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Search | Tantivy (Rust → Python) |
| OCR | PaddleOCR (ONNX) + Tesseract fallback |
| Frontend | React + TypeScript + Tailwind CSS |
| Database | SQLite |
| Container | python:3.12-slim |

## License

MIT