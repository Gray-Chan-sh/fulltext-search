# FullText Search — 实施计划

> **重要说明：** 以下为原始实施计划。实际开发过程中对部分设计做了调整，
> 详见文末「十一、最终决策与变更记录」。

## 一、架构总览

```
┌─────────────────────────────────────────────────────────┐
│                     Docker 容器                           │
│  ┌──────────────┐    ┌──────────────────────────────┐   │
│  │  React SPA   │◄──►│  FastAPI + Uvicorn            │   │
│  │  (shadcn/ui) │    │  ┌──────────┐ ┌───────────┐ │   │
│  │              │    │  │ API 路由  │ │ service   │ │   │
│  │              │    │  │ - search  │ │ - searcher│ │   │
│  │              │    │  │ - dirs    │ │ - indexer │ │   │
│  │              │    │  │ - index   │ │ - scanner │ │   │
│  │              │    │  │ - file    │ │ - watcher │ │   │
│  │              │    │  │ - export  │ │ - tracker │ │   │
│  │              │    │  └──────────┘ └───────────┘ │   │
│  └──────────────┘    └──────────────────────────────┘   │
│                                │                         │
│                       ┌────────┴────────┐                │
│                       │   SQLite        │                │
│                       │   file_tracking │                │
│                       │   content_index │                │
│                       └────────┬────────┘                │
│                                │                         │
│                       ┌────────┴────────┐                │
│                       │   Tantivy 索引   │                │
│                       │   (分词+倒排)    │                │
│                       └─────────────────┘                │
│                                │                         │
│                       ┌────────┴────────┐                │
│                       │   PaddleOCR     │                │
│                       │   + OpenCV      │                │
│                       └─────────────────┘                │
└─────────────────────────────────────────────────────────┘
         ▲                           ▲
         │ 只读挂载                    │ Docker volume
    ┌────┴────┐                 ┌─────┴─────┐
    │ 资料目录 │                 │ 索引数据   │
    │ (NAS/本机)│                │ (持久化)   │
    └─────────┘                 └───────────┘
```

## 二、项目目录结构

```
fulltext-search/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 入口 + CORS + 生命周期
│   │   ├── config.py                # 配置（路径、OCR语言、定时等）
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── search.py            # /api/search /api/suggest
│   │   │   ├── dirs.py              # /api/dirs CRUD
│   │   │   ├── index.py             # /api/index/status /trigger /exclude
│   │   │   ├── file.py              # /api/file/{id}/preview /download /content
│   │   │   └── export.py            # /api/search/export /api/history
│   │   ├── service/
│   │   │   ├── __init__.py
│   │   │   ├── searcher.py          # Tantivy 搜索 + 建议 + 高亮
│   │   │   ├── indexer.py           # Tantivy 索引写入 + 管理
│   │   │   ├── scanner.py           # 全量扫描 + 增量更新
│   │   │   ├── tracker.py           # SQLite 文件追踪 (file_tracking + content_index)
│   │   │   ├── watcher.py           # watchdog 实时监控
│   │   │   └── scheduler.py         # APScheduler 定时 + 互斥锁
│   │   ├── extractor/
│   │   │   ├── __init__.py
│   │   │   ├── text.py              # 纯文本 / 代码文件
│   │   │   ├── office.py            # docx / xlsx / pptx
│   │   │   ├── pdf.py               # PyMuPDF 文字提取
│   │   │   └── ocr.py               # PaddleOCR + OpenCV 预处理
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── search.py            # SearchResult / SearchResponse
│   │       ├── dirs.py              # DirConfig
│   │       └── index.py             # IndexStatus
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_tracker.py
│   │   ├── test_extractor.py
│   │   ├── test_searcher.py
│   │   └── test_scanner.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── api/
│   │   │   └── client.ts            # API 客户端 + 类型
│   │   ├── hooks/
│   │   │   ├── useSearch.ts
│   │   │   └── useIndexStatus.ts
│   │   ├── pages/
│   │   │   ├── SearchPage.tsx        # 搜索 + 结果 + 预览
│   │   │   ├── DirManager.tsx        # 资料库管理
│   │   │   ├── IndexStatus.tsx       # 索引状态
│   │   │   └── Settings.tsx          # 设置
│   │   └── components/
│   │       ├── SearchBar.tsx
│   │       ├── ResultList.tsx
│   │       ├── PreviewPanel.tsx
│   │       ├── FilterPanel.tsx
│   │       └── StatusBar.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
├── docker-compose.yml
├── AGENTS.md
└── IMPLEMENTATION_PLAN.md
```

## 三、数据库设计

### SQLite: file_tracking

```sql
CREATE TABLE file_tracking (
    id          TEXT PRIMARY KEY,           -- uuid
    path        TEXT NOT NULL UNIQUE,       -- 文件绝对路径
    dir_id      TEXT NOT NULL,              -- 所属资料库目录
    mtime       REAL NOT NULL,              -- 修改时间戳
    size        INTEGER NOT NULL,           -- 文件大小（字节）
    md5         TEXT,                       -- 内容哈希（可为 NULL，新增/变更后填充）
    status      TEXT NOT NULL DEFAULT 'active',  -- active / deleted
    indexed     INTEGER NOT NULL DEFAULT 0, -- 0=未索引 1=已索引 2=失败
    error_msg   TEXT,                       -- 索引失败原因
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE INDEX idx_file_tracking_dir_id ON file_tracking(dir_id);
CREATE INDEX idx_file_tracking_status ON file_tracking(status);
CREATE INDEX idx_file_tracking_md5 ON file_tracking(md5);
```

### SQLite: content_index

```sql
CREATE TABLE content_index (
    md5             TEXT PRIMARY KEY,       -- 文件内容哈希
    text_content    TEXT NOT NULL,          -- 提取的纯文字
    indexed_at      REAL NOT NULL,
    char_count      INTEGER NOT NULL DEFAULT 0,   -- 文字长度
    ocr_used        INTEGER NOT NULL DEFAULT 0,   -- 0=直接提取 1=OCR
    ocr_duration_ms INTEGER                   -- OCR 耗时
);
```

### SQLite: dir_config

```sql
CREATE TABLE dir_config (
    id          TEXT PRIMARY KEY,
    path        TEXT NOT NULL UNIQUE,
    alias       TEXT,
    ocr_lang    TEXT NOT NULL DEFAULT 'ch',
    exclude_patterns TEXT,                  -- 逗号分隔的 glob
    include_exts TEXT,                      -- 留空=全部
    created_at  REAL NOT NULL
);
```

### SQLite: search_history

```sql
CREATE TABLE search_history (
    id          TEXT PRIMARY KEY,
    query       TEXT NOT NULL,
    dir_ids     TEXT,                       -- 搜索时选中的目录
    filters     TEXT,                       -- JSON
    result_count INTEGER,
    pinned      INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL
);
```

## 四、API 契约

### 搜索

```
GET /api/search?q=<keyword>&dir_ids=<id1,id2>&types=<pdf,docx>&date_from=&date_to=
               &sort=score|date|name&order=desc|asc&page=1&size=20

Response:
{
  "total": 153,
  "page": 1,
  "size": 20,
  "took_ms": 42,
  "hits": [
    {
      "id": "uuid",
      "filename": "合同_2024.pdf",
      "path": "/mnt/data/文档/合同_2024.pdf",
      "dir_id": "d1",
      "dir_name": "项目文档",
      "snippet": "...【2024】年度采购<mark>合同</mark>...",
      "modified": "2024-03-15T10:00:00Z",
      "size": 2350000,
      "extension": "pdf",
      "score": 0.89
    }
  ],
  "facets": {
    "types": {"pdf": 120, "docx": 33},
    "dirs": {"d1": {"name": "项目文档", "count": 100}}
  }
}
```

### 搜索建议

```
GET /api/suggest?q=合

Response:
{
  "suggestions": ["合同", "合作", "合并报表", "合同法"],
  "took_ms": 5
}
```

### 文件预览

```
GET /api/file/{id}/preview

Response:
{
  "id": "uuid",
  "content": "完整的文本内容...",
  "char_count": 15000,
  "ocr_used": false,
  "pages": 12
}
```

### 文件下载

```
GET /api/file/{id}/download

→ 返回原始文件（Content-Disposition: attachment）
```

### 文件内容（纯文本查看）

```
GET /api/file/{id}/content

Response:
{
  "id": "uuid",
  "content": "完整原始文本...",
  "char_count": 15000,
  "ocr_used": false
}
```

### 资料库管理

```
# 列表
GET /api/dirs
Response: { "dirs": [{ "id": "d1", "path": "/mnt/data", "alias": "...", "file_count": 3200, "indexed_count": 3100, "status": "idle|scanning|watching" }] }

# 添加
POST /api/dirs
Body: { "path": "/mnt/data/文档", "alias": "项目文档", "ocr_lang": "ch", "exclude_patterns": "*.tmp,node_modules", "include_exts": "" }
Response: { "id": "d1" }

# 删除
DELETE /api/dirs/{id}

# 更新
PUT /api/dirs/{id}
Body: { "alias": "...", "exclude_patterns": "...", "include_exts": "..." }
```

### 索引管理

```
# 状态
GET /api/index/status
Response: {
  "total_files": 5000,
  "indexed": 3200,
  "pending": 1800,
  "failed": 12,
  "ocr_pending": 800,
  "scanner_status": "idle|scanning|watching",
  "progress_percent": 64.0,
  "last_full_scan": "2026-07-27T00:00:00Z",
  "next_scheduled_scan": "2026-07-28T00:00:00Z"
}

# 手动触发全量扫描
POST /api/index/trigger
Response: { "status": "accepted", "message": "全量扫描已触发" }

# 配置排除模式
POST /api/index/exclude
Body: { "patterns": ["*.tmp", "node_modules/*", "*.log"] }
```

### 导出

```
GET /api/search/export?q=&dir_ids=&types=&date_from=&date_to=&sort=

→ 返回 text/csv
```

### 搜索历史

```
GET /api/history
Response: { "history": [{ "id": "h1", "query": "合同", "result_count": 42, "pinned": false, "created_at": "..." }] }

DELETE /api/history/{id}

POST /api/pin
Body: { "result_id": "uuid" }
```

## 五、扫描互斥锁设计

```python
scanner_lock = asyncio.Lock()

async def full_scan():
    async with scanner_lock:
        # 全量扫描所有目录
        ...

async def realtime_event_handler(path):
    # 先检查锁，锁被占用则跳过（定时扫描会覆盖）
    if scanner_lock.locked():
        return
    # 处理单个文件变更
    ...

async def scheduled_scan():
    # 每日 00:00 触发
    async with scanner_lock:
        await full_scan()
```

## 六、实施阶段

### Phase 1 — 后端骨架（2-3 天）

| 步骤 | 产出 |
|---|---|
| 1.1 项目初始化 | `uv venv --python 3.12`、`requirements.txt`、`app/main.py`、`app/config.py` |
| 1.2 数据库层 | `service/tracker.py`：SQLite 建表 + CRUD + MD5 去重 |
| 1.3 文字提取流水线 | `extractor/text.py` `office.py` `pdf.py` `ocr.py` 单元测试 |
| 1.4 索引引擎 | `service/indexer.py` `service/searcher.py`：Tantivy 封装 |
| 1.5 扫描器 | `service/scanner.py` `service/watcher.py` `service/scheduler.py` |
| 1.6 API 路由 | `routes/search.py` `dirs.py` `index.py` `file.py` `export.py` |

### Phase 2 — 前端（3-4 天）

| 步骤 | 产出 |
|---|---|
| 2.1 项目初始化 | `npm create vite`、shadcn/ui、Tailwind、API client |
| 2.2 搜索页 | SearchBar + ResultList + FilterPanel + PreviewPanel + 键盘导航 |
| 2.3 资料库管理 | DirManager：添加/删除/编辑监控目录 |
| 2.4 索引状态页 | IndexStatus：进度条、文件数、最近扫描时间 |
| 2.5 设置页 | OCR 语言、排除模式、定时配置 |
| 2.6 深色模式 + 响应式 | |

### Phase 3 — Docker + 集成（1 天）

| 步骤 | 产出 |
|---|---|
| 3.1 Dockerfile | 多阶段构建、国内源、镜像瘦身 |
| 3.2 docker-compose.yml | 服务编排、volume 挂载、端口映射 |
| 3.3 构建测试 | `docker build --platform linux/amd64` 验证 |

### Phase 4 — 优化（持续）

| 项目 | 内容 |
|---|---|
| 大文件部分哈希 | >500MB 文件只取首尾哈希 |
| OCR 队列并发控制 | 限制 2 并发 OCR |
| 索引增量更新 | 首次全量后只处理变更 |
| 搜索结果缓存 | 前端 IndexDB 缓存 |
| 性能基准 | 10 万文件压力测试 |

## 七、开发环境

### 前置条件

```bash
# macOS: uv + Node 20+
brew install uv node
uv venv --python 3.12 .venv
source .venv/bin/activate

# 安装系统依赖（Tesseract 备用）
brew install tesseract
```

### 安装依赖

```bash
# 后端
uv pip install paddlepaddle==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
uv pip install "paddleocr[doc-parser]"
uv pip install tantivy opencv-python-headless PyMuPDF python-docx openpyxl python-pptx
uv pip install watchdog apscheduler fastapi uvicorn python-multipart aiofiles

# 前端
cd frontend
npm create vite@latest . -- --template react-ts
npx shadcn@latest init
npm install lucide-react
```

### 启动

```bash
# 终端 1 后端
source .venv/bin/activate
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2 前端
cd frontend && npm run dev
```

### 测试数据准备

```bash
mkdir -p /tmp/test_docs/{合同,报告,会议,图片}
echo "2024年度采购合同" > /tmp/test_docs/合同/contract_2024.txt
echo "项目启动会议纪要" > /tmp/test_docs/会议/meeting_0321.txt
# 放一些测试 PDF / docx / 扫描件图片
```

## 八、Docker 部署

### Dockerfile

```dockerfile
# ===== 阶段 1: 前端构建 =====
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/ .
RUN npm ci && npm run build

# ===== 阶段 2: Python 环境 =====
FROM python:3.12-slim AS backend

# 国内源加速
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 libstdc++6 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    paddlepaddle==3.2.1 \
    && pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# PaddleOCR 模型预下载
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='ch')" 2>/dev/null || true

COPY backend/ .
COPY --from=frontend /build/dist /app/static

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
services:
  fulltext-search:
    build:
      context: .
      dockerfile: backend/Dockerfile
      platforms:
        - linux/amd64
    ports:
      - "8080:8000"
    volumes:
      - /path/to/data:/data:ro           # 资料目录（只读）
      - index_data:/app/index_data       # Tantivy 索引持久化
      - app_data:/app/data               # SQLite 追踪数据
    environment:
      - OCR_LANG=ch
      - SCHEDULED_SCAN_TIME=00:00
      - OCR_CONCURRENT=2
    restart: unless-stopped

volumes:
  index_data:
  app_data:
```

### 构建与部署

```bash
# 开发测试（macOS 验证）
docker compose up --build

# 发布到 x86 服务器
docker buildx build --platform linux/amd64 \
  -t registry/fulltext-search:latest \
  --push .
```

## 九、质量要求

| 维度 | 标准 |
|---|---|
| 类型注解 | 所有函数完整 type hint |
| 空索引容错 | 首次运行无文件时返回友好提示 |
| 并发安全 | 扫描器 asyncio.Lock 互斥 |
| 磁盘压力 | 索引队列限速 10MB/s |
| 错误隔离 | 单个文件 OCR 失败不影响整个索引 |
| 镜像大小 | 目标 < 1.5GB |
| 搜索延迟 | 万级索引 < 200ms |

---

## 十一、最终决策与变更记录

### 扫描器架构（与原计划不同）

| 原计划 | 最终实现 | 原因 |
|---|---|---|
| 子进程扫描 (`subprocess.Popen`) | **进程内扫描** (`asyncio.create_task`) | SQLite 跨进程锁竞争导致崩溃 |
| OCR 在主进程线程池 | 专用 `ThreadPoolExecutor(max_workers=4)` | 隔离 OCR 线程，避免 GIL 阻塞 |
| `scan_state` 通过模块引用传递 | 必须通过 `scanner_mod.scan_state` 访问 | 模块重新赋值后本地引用会过期 |
| 状态文件 `scan_status.json` | **无**，直接读 `scan_state` 字典 | 进程内共享无需文件 |

### 最终扫描流程

```
APScheduler / 手动触发 / watchdog
        │
        ▼
  _run_scan_task()    ← asyncio.create_task (不阻塞 API)
        │
        ▼
  run_full_scan()
        │
        ├── Phase -1: 清理幽灵文件 (在 DB 但磁盘已不存在)
        ├── Phase 0: 重置卡住文件 (indexed=3 → 0)
        ├── Phase 1: 遍历目录，逐个文件提取文字（OCR 在线程池）
        └── Phase 2: 批量写入 Tantivy 索引
```

### OCR 配置

| 参数 | 默认值 | 说明 |
|---|---|---|
| `ocr_engine` | `"onnxruntime"` | PaddleOCR 推理引擎，比默认快 3-5x |
| `ocr_dpi` | `100` | PDF 渲染 DPI，原计划 150 |
| `ocr_concurrent` | `2` | 并发 OCR 数 |
| `ocr_fallback_tesseract` | `true` | OCR 失败时降级到 Tesseract |

### 文件状态

| 值 | 含义 | 前端显示 |
|---|---|---|
| 0 | 待处理 | ⏳ 待处理 |
| 1 | 已索引 | ✅ 已索引 |
| 2 | 失败 | ❌ 失败 (`error_msg` 记录原因) |
| 3 | 正在索引 | ⏳ 正在索引 |

### 数据库

- **`get_db()`** — 每次调用创建新连接，用完关闭（避免连接泄漏）
- **`scan_log`** 表新增 `source` 列（server/indexer/ocr/extractor/watcher）
- **`mark_processing()`** 同时清除 `error_msg`，避免状态冲突
- **`count_files()`** 加 `status='active'` 过滤，排除已删除文件

### 前端页面

| 原计划 | 最终 |
|---|---|
| 索引状态页 | **日志页面** 替代，含级别/来源筛选、CSV 导出、实时进度 |
| 资料库：统计文字 | 合并为**筛选按钮+计数**（全部/已索引/待处理/正在索引/失败） |
| 搜索：转圈加载 | **骨架屏** 替代 |
| 操作无反馈 | 全局 **Toast 通知** + **确认弹窗** |

### 数据迁移

索引数据（`app_data/` + `index_data/`）可跨机器迁移：

```
Mac (M 芯片)                    NAS (J4125)
─────────────────               ────────────────
docker build --platform amd64    docker compose up
docker run (全量索引)               ├── 直接使用已索引数据
  ├── 产出 app_data/              └── 新文件用 Tesseract 处理
  │   ├── tracker.db
  │   ├── settings.json
  │   └── scan_queue.json
  └── 产出 index_data/
         │
         ▼
   rsync → NAS
```

注意事项：
- 两台机器的资料挂载路径必须一致（都是 `/data/docs`）
- Tantivy 和 SQLite 数据跨架构兼容（amd64 ↔ arm64）
- 首次迁移后后续只需增量 `rsync`
- `settings.json` 也会一并迁移，设置无需重新配置

