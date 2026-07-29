# FullText Search

Docker 部署的全文搜索服务，支持 OCR，适合在 NAS 上索引和管理文档。

A Docker-deployed full-text search service with OCR support, designed for indexing and managing documents on NAS.

## 功能 / Features

- **全文搜索** — Tantivy 搜索引擎，BM25 排序，中文分词，搜索建议
  **Full-text search** — Tantivy engine, BM25 ranking, Chinese word segmentation, search suggestions
- **OCR 支持** — PaddleOCR（ONNX 加速）自动识别扫描件和图片中的文字
  **OCR support** — PaddleOCR (ONNX accelerated) for scanned PDFs and images
- **多格式支持** — PDF、Office（docx/xlsx/pptx）、纯文本、图片
  **Multi-format** — PDF, Office (docx/xlsx/pptx), plain text, images
- **实时监控** — 文件新增/修改/删除自动检测，定时全量扫描
  **Real-time monitoring** — Automatic detection of file changes, scheduled full scans
- **Web UI** — React SPA，支持文件视图/逐条视图切换
  **Web UI** — React SPA with list/file view toggle
- **REST API** — 完整的搜索、索引、管理 API
  **REST API** — Complete search, indexing, and management API
- **文件管理** — 重复文件检测、最近动态、OCR 质量报告、文件状态筛选
  **File management** — Duplicate detection, recent activity, OCR quality report, status filtering
- **用户认证** — 密码登录，支持修改密码
  **Authentication** — Password login, changeable password
- **批量下载** — 勾选多个文件打包 ZIP 下载
  **Batch download** — Select multiple files and download as ZIP
- **自动备份** — 定时备份索引数据，支持手动触发
  **Auto backup** — Scheduled index backups, manual trigger supported
- **Docker 部署** — amd64 镜像，可跨架构迁移索引数据
  **Docker deployment** — amd64 image, cross-architecture index migration

## 快速开始 / Quick Start

```bash
# 克隆 / Clone
git clone https://github.com/Gray-Chan-sh/fulltext-search.git
cd fulltext-search

# (可选) 配置环境变量 / (Optional) Configure environment
cp .env.example .env
# 编辑 .env 修改 DATA_DIR、PORT 等 / Edit .env to set DATA_DIR, PORT etc.

# 一键部署 / One-click deploy
./scripts/deploy.sh

# 或手动构建 / Or build manually
docker compose up --build

# 访问 / Access
# http://localhost:8080  — Web UI
# 默认密码 / Default password: admin
```

## Docker 镜像使用 / Docker Image Usage

### 从源码构建 / Build from Source

```bash
git clone https://github.com/Gray-Chan-sh/fulltext-search.git
cd fulltext-search
docker buildx build --platform linux/amd64 -t fulltext-search .
```

### 使用 Docker CLI 运行 / Run with Docker CLI

```bash
mkdir -p ./data/{docs,app_data,index_data}
# 把需要索引的文档放入 ./data/docs/ / Put your documents in ./data/docs/

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

### 使用 docker-compose（推荐 / Recommended）

```bash
curl -fsSL https://raw.githubusercontent.com/Gray-Chan-sh/fulltext-search/main/docker-compose.yml -o docker-compose.yml
mkdir -p ./data/docs
docker compose up --build -d
```

### 环境变量 / Environment Variables

| 变量 | 默认值 | 说明 / Description |
|---|---|---|
| `PORT` | `8080` | 宿主机映射端口 / Host port |
| `DATA_DIR` | `./data/docs` | 资料目录路径 / Document directory path |
| `OCR_LANG` | `ch` | OCR 语言 / OCR language (ch/en/japan/korean) |
| `OCR_CONCURRENT` | `2` | OCR 并发数 / OCR concurrency (auto-adjusts on OOM) |
| `SCHEDULED_SCAN_TIME` | `00:00` | 每日定时扫描时间 / Daily scheduled scan time |

### 跨架构构建 / Cross-architecture Build

```bash
# Mac M 芯片上构建 amd64 镜像 / Build amd64 image on Mac M chip
docker buildx build --platform linux/amd64 -t fulltext-search .

# 保存镜像 / Save image
docker save fulltext-search | gzip > fulltext-search.tar.gz
```

### 数据持久化 / Data Persistence

```
data/
├── docs/          → /data/docs  (只读，放文档 / readonly, documents)
├── app_data/      → /data/app   (SQLite + 设置 / settings)
└── index_data/    → /data/index (Tantivy 索引 / search index)
```

容器重启或重建不会丢失数据。迁移时复制整个 `data/` 目录即可 / Data survives container restarts. Migrate by copying the `data/` directory:

```bash
rsync -avz ./data/ user@nas:/path/to/fulltext-search/data/
```

### 内存限制 / Memory Limits

PaddleOCR is memory-intensive. For low-memory devices (e.g. J4125 + 3GB):

```bash
OCR_CONCURRENT=1 docker compose up -d
```

### 多资料目录 / Multiple Document Directories

在 `docker-compose.yml` 的 `volumes` 中追加 / Add to `volumes` in `docker-compose.yml`:

```yaml
volumes:
  - /path/to/contracts:/data/contracts:ro
  - /path/to/reports:/data/reports:ro
```

启动后会自动注册这些目录 / Directories are auto-registered on startup.

## 配置 / Settings

通过 Web UI 的设置页面可配置 / Configurable via Web UI Settings page:

| 设置 / Setting | 说明 / Description |
|---|---|
| OCR 语言 / OCR language | 中文/英文/日文/韩文 / Chinese/English/Japanese/Korean |
| OCR 并发数 / OCR concurrency | 根据内存自动建议 / Auto-suggested based on available memory |
| 定时扫描 / Scheduled scan | 每日定时全量扫描 / Daily full scan |
| 排除模式 / Exclude patterns | glob 模式排除不需要索引的文件 / Glob patterns to exclude files |
| 自动备份 / Auto backup | 定期备份索引数据 / Scheduled index backup |
| 主题 / Theme | 浅色/深色/跟随系统 / Light/Dark/System |

## 数据迁移 / Data Migration

索引数据可跨机器迁移 / Index data can be migrated across machines:

```bash
# 在 Mac 上构建并索引 / Build and index on Mac
docker buildx build --platform linux/amd64 -t fulltext-search .
docker run -d \
  -v /本地/资料:/data/docs:ro \
  -v $(pwd)/data/app_data:/data/app \
  -v $(pwd)/data/index_data:/data/index \
  fulltext-search

# 迁移数据 / Migrate data
rsync -avz ./data/ user@nas:/path/to/fulltext-search/data/

# 在 NAS 上启动 / Start on NAS
docker compose up -d
```

## 目录结构 / Directory Structure

```
backend/
  app/
    main.py          — FastAPI 入口 / Entry point
    config.py        — 配置 / Configuration
    routes/          — API 路由 / API routes
    service/         — 业务逻辑 / Business logic
    extractor/       — 文字提取 / Text extraction
    models/          — Pydantic 模型 / Pydantic models
frontend/
  src/
    pages/           — 页面组件 / Page components
    components/      — 通用组件 / Shared components
    api/client.ts    — API 客户端 / API client
```

## 技术栈 / Tech Stack

| 层 / Layer | 选型 / Choice |
|---|---|
| 后端 / Backend | Python 3.12 + FastAPI |
| 搜索 / Search | Tantivy (Rust → Python) |
| OCR | PaddleOCR (ONNX) + Tesseract fallback |
| 前端 / Frontend | React + TypeScript + Tailwind CSS |
| 数据库 / Database | SQLite |
| 容器 / Container | python:3.12-slim |

## License

MIT
