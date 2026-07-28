import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _clean_stale_locks():
    for f in (".tantivy-writer.lock", ".tantivy-meta.lock"):
        p = os.path.join(settings.index_dir, f)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _preload_ocr():
    """Preload PaddleOCR model at startup (avoids GIL lock during scan)."""
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from app.extractor.ocr import _get_paddleocr
            _get_paddleocr()
            logger.info("PaddleOCR model loaded")
    except Exception as e:
        logger.warning("PaddleOCR preload failed: %s", e)


def _auto_register_data_dirs():
    from app.service.tracker import list_dirs, add_dir
    existing = {d["path"] for d in list_dirs()}
    data_root = "/data"
    if not os.path.isdir(data_root):
        return
    for entry in sorted(os.listdir(data_root)):
        path = os.path.join(data_root, entry)
        # Skip internal dirs (index, app, etc.)
        if entry in ("index", "app", "tmp", "cache"):
            continue
        if os.path.isdir(path) and path not in existing:
            add_dir(path=path, alias=entry, ocr_lang=settings.ocr_lang)
            logger.info("auto-registered data dir: %s", path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from app.service.watcher import set_event_loop
    set_event_loop(asyncio.get_event_loop())

    os.makedirs(settings.index_dir, exist_ok=True)
    os.makedirs(settings.data_dir, exist_ok=True)
    _clean_stale_locks()
    _preload_ocr()

    from app.service.tracker import init_db
    init_db()
    logger.info("database initialized")

    _auto_register_data_dirs()

    from app.service.tracker import add_log
    add_log("INFO", "服务器启动", source="server")
    from app.service.scheduler import start_scheduler
    await start_scheduler()
    from app.service.backup import start_backup_scheduler
    await start_backup_scheduler()
    logger.info("scheduler started")

    yield

    # Shutdown
    add_log("INFO", "服务器关闭", source="server")
    from app.service.scheduler import stop_scheduler
    await stop_scheduler()
    from app.service.backup import stop_backup_scheduler
    await stop_backup_scheduler()
    from app.service.watcher import stop_watcher
    await stop_watcher()
    logger.info("services shut down")


app = FastAPI(title="FullText Search", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
from app.routes import search, dirs, index, file, export, settings as settings_route, logs, auth, files as files_route
from app.routes.auth import _validate_token


@app.middleware("http")
async def auth_middleware(request, call_next):
    # Public endpoints (no auth required)
    public_paths = {"/api/auth/login", "/api/health", "/"}
    if request.url.path in public_paths or request.url.path.startswith("/api/auth/"):
        return await call_next(request)

    # Settings endpoint also public for initial setup
    if request.url.path == "/api/settings" and request.method == "GET":
        return await call_next(request)

    # All /api/* routes require auth
    if request.url.path.startswith("/api/"):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        if not token or not _validate_token(token):
            from starlette.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "请先登录"})

    return await call_next(request)


app.include_router(search.router)
app.include_router(dirs.router)
app.include_router(index.router)
app.include_router(file.router)
app.include_router(export.router)
app.include_router(settings_route.router)
app.include_router(logs.router)
app.include_router(auth.router)
app.include_router(files_route.router)


# Static files for built frontend
static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "static")
static_abs = os.path.abspath(static_dir)
if os.path.isdir(static_abs):
    app.mount("/", StaticFiles(directory=static_abs, html=True), name="static")


@app.get("/api/health")
async def health():
    from app.service.scanner import scan_state
    return {"status": "ok", "scanner": scan_state.get("status", "idle")}
