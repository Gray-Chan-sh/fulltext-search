# AGENTS.md — fulltext-search

**Full-text search service** with Docker, Web UI + REST API. Pre-indexes read-only document directories with OCR for scanned PDFs/images.

## Quick start

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r backend/requirements.txt
# macOS: brew install tesseract

# Terminal 1: backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: frontend
cd frontend && npm run dev
```

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI | OCR 生态最强 |
| Search | Tantivy (Rust → Python) | 速度优先，BM25 |
| OCR | PaddleOCR (ONNX) + Tesseract fallback | 中文质量最高 |
| Frontend | React + shadcn/ui + Tailwind | SPA 体验 |
| DB | SQLite | 零依赖，文件追踪 + 索引元数据 |
| Watch | watchdog (fsevents/inotify) | 实时文件变更 |
| Schedule | APScheduler | 每日全量扫描 |
| Container | python:3.12-slim | 国内源加速 |

## Architecture

```
FastAPI → Routes → Services (searcher/indexer/scanner/tracker/watcher)
               → Extractor (text/office/pdf/ocr)
               → Tantivy (index) + SQLite (metadata)
               → PaddleOCR (image/scanned PDF)
```

### Scanning — in-process background task (NO subprocess)

All scans run via `asyncio.create_task` in the same process. OCR runs in a
dedicated `ThreadPoolExecutor(max_workers=4)` — CPU-bound C extensions release
the GIL during computation, keeping the API responsive.

```
scheduler → _run_scan_task() → run_full_scan()
                                └── asyncio.create_task (background)
                                      └── dedicated ThreadPoolExecutor (OCR)
```

### Dedup strategy

```
(mtime, size) → fast skip (no MD5)
(mtime|size changed) → MD5 → check content_index
  → MD5 exists → update file_tracking path (zero-cost move/restore)
  → MD5 new   → route to extractor → index
```

### File status (indexed field)

| Value | Display | Color |
|---|---|---|
| 0 | ⏳ 待处理 | amber |
| 1 | ✅ 已索引 | green |
| 2 | ❌ 失败 | red |
| 3 | ⏳ 正在索引 | blue |

## Project structure

```
backend/app/
  main.py         — FastAPI entry + lifespan (init_db, preload OCR, start scheduler)
  config.py       — Settings (pydantic-settings)
  routes/         — search, dirs, index, file, export, settings, logs
  service/        — searcher, indexer, scanner, tracker, watcher, scheduler
  extractor/      — text, office, pdf, ocr
  models/         — Pydantic schemas (API contract)

frontend/src/
  pages/          — SearchPage, DirManager, LogsPage, Settings
  components/     — Toast, ConfirmDialog, Skeleton
  hooks/          — useSearch
  api/client.ts   — Typed API client
```

## Critical commands

```bash
# Dev (direct, no Docker)
uv run uvicorn app.main:app --reload
cd frontend && npm run dev

# Dev (Docker with hot-reload)
docker compose -f docker-compose.dev.yml up --build

# Production build (for x86_64 NAS/server)
docker buildx build --platform linux/amd64 -t fulltext-search .
docker compose up

# Index data migration (build on Mac → deploy to NAS)
rsync -avz ./app_data/ user@nas:/path/to/app_data/
rsync -avz ./index_data/ user@nas:/path/to/index_data/
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | /api/search?q=&dir_ids=&types=&page=&size=&sort=&order= | Search |
| GET | /api/suggest?q= | Search suggestions |
| GET | /api/file/{id}/preview | Full text preview |
| GET | /api/file/{id}/download | Download original file |
| GET | /api/file/{id}/content | Raw text content |
| POST | /api/file/batch-download | ZIP download of selected files |
| GET | /api/dirs | Directory list (with counts) |
| POST | /api/dirs | Add directory |
| DELETE | /api/dirs/{id} | Remove directory |
| GET | /api/dirs/{id}/files?status_filter= | File list with status filter |
| POST | /api/dirs/{id}/index | Index selected files |
| GET | /api/index/status | Scan status + progress |
| POST | /api/index/trigger | Trigger full scan |
| GET | /api/logs?level=&source=&q= | Query logs |
| GET | /api/logs/export | Export logs CSV |
| GET | /api/settings | Get settings |
| PUT | /api/settings | Save settings |
| GET | /api/search/export?q= | Export results CSV |
| GET | /api/history | Search history |
| POST | /api/auth/login | Login |
| POST | /api/auth/logout | Logout |
| GET | /api/auth/check | Check auth status |
| GET | /api/files/duplicates | Duplicate files |
| GET | /api/files/recent | Recent activity |
| GET | /api/files/ocr-report | OCR quality report |

## Key design decisions

- **No subprocess for scanner** — previously tried `subprocess.Popen` but SQLite
  lock contention between processes caused crashes. Now runs in-process via
  `asyncio.create_task` with dedicated `ThreadPoolExecutor` for OCR.
- **Single global SQLite connection** was tried and caused "closed database"
  errors across process boundaries. Reverted to per-request connections.
- **scan_state** must be accessed via `scanner_mod.scan_state` (module attribute),
  NOT via `from scanner import scan_state` (local reference becomes stale when
  `run_full_scan` reassigns the dict).
- **PaddleOCR with ONNX runtime** — ~4-5x faster than default Paddle engine.
  Default DPI reduced from 150 to 100.
- **Large PDFs (>50MB)** — skip OCR, only extract embedded text (prevents OOM).
- **Stuck processing recovery** — `reset_stuck_processing()` at scan start
  resets files stuck at `indexed=3` back to `indexed=0`.
- **Ghost entry cleanup** — `run_full_scan()` Phase -1 checks tracked files
  still exist on disk; marks missing files as deleted.
- **No JSX comments on closing tags** — oxc parser fails on
  `</div> {/* comment */}`. Keep JSX comments on their own lines.

## Important conventions

- **Python 3.12** — NOT system Python 3.14 (PaddlePaddle not compatible)
- **AMD64 target** for Docker: `docker buildx build --platform linux/amd64`
- **No `as any` / `@ts-ignore`** in frontend
- **OCR queue** capped at 2 concurrent (`ocr_concurrent`)
- **scanner_lock** must be respected by watcher, scheduler, and manual trigger
- **PaddleOCR model cache**: `~/.paddleocr/` (add `paddleocr` + `onnxruntime` to pip)
- **macOS debug**: watchdog uses fsevents, works natively
- **Directory is read-only mounted** (`:ro` in Docker)
- **Index data is cross-platform** — SQLite + Tantivy files can be built on Mac
  (amd64 Docker) and migrated to NAS via rsync
- **Migration**: copy `app_data/` (settings + SQLite) and `index_data/` (Tantivy)
- **Settings persistence**: stored in `/data/app/settings.json`, Docker volume
- **Read-only data dirs** — files are mounted `:ro`, all management is metadata-only
  (tags, notes, duplicates, activity tracking — no disk file modification)

## When things break

- OCR fails → check `error_msg` in file_tracking, model download
- Search empty → check scanner ran (index_status), or watchdog started
- Docker build fails on amd64 → `docker run --privileged --rm tonistiigi/binfmt --install all`
- PaddlePaddle import error on macOS → ensure using `python:3.12` venv
- Scanner stuck at "scanning" with no progress → check `scanner_lock` stale,
  restart container
- "Cannot operate on a closed database" → access `scan_state` via module, not
  local import
- Setting theme not applied → refresh page, saved theme loads on mount
