# FullText Search

Docker 部署的全文搜索服务，支持 OCR，适合在 NAS 上索引和管理文档。

## 功能

- **全文搜索** — Tantivy 搜索引擎，BM25 排序，中文分词，搜索建议
- **OCR 支持** — PaddleOCR（ONNX 加速）自动识别扫描件和图片中的文字
- **多格式支持** — PDF、Office（docx/xlsx/pptx）、纯文本、图片
- **实时监控** — 文件新增/修改/删除自动检测，定时全量扫描
- **Web UI** — React SPA，支持文件视图/逐条视图切换
- **REST API** — 完整的搜索、索引、管理 API
- **文件管理** — 重复文件检测、最近动态、OCR 质量报告、文件状态筛选
- **用户认证** — 密码登录，支持修改密码
- **批量下载** — 勾选多个文件打包 ZIP 下载
- **自动备份** — 定时备份索引数据，支持手动触发
- **Docker 部署** — amd64 镜像，可跨架构迁移索引数据

## 快速开始

```bash
# 构建并启动
docker compose up --build

# 访问
# http://localhost:8080  — Web UI
# 默认密码: admin
```

## Docker 镜像使用

### 从源码构建

```bash
# 克隆仓库
git clone https://github.com/Gray-Chan-sh/fulltext-search.git
cd fulltext-search

# 构建镜像（amd64，适用于 NAS/服务器）
docker buildx build --platform linux/amd64 -t fulltext-search .
```

### 使用 Docker CLI 运行

```bash
# 准备目录
mkdir -p ./data/{docs,app_data,index_data}
# 把需要索引的文档放入 ./data/docs/

# 启动容器
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

### 使用 docker-compose（推荐）

```bash
# 下载 docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/Gray-Chan-sh/fulltext-search/main/docker-compose.yml -o docker-compose.yml

# 准备资料目录
mkdir -p ./data/docs
# 把文档放入 ./data/docs/

# 构建并启动
docker compose up --build -d
```

### 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORT` | `8080` | 宿主机映射端口 |
| `DATA_DIR` | `./data/docs` | 资料目录路径 |
| `OCR_LANG` | `ch` | OCR 语言（ch/en/japan/korean） |
| `OCR_CONCURRENT` | `2` | OCR 并发数，内存不足时自动降级 |
| `SCHEDULED_SCAN_TIME` | `00:00` | 每日定时扫描时间 |

### 跨架构构建（Mac 构建 → NAS 部署）

```bash
# Mac M 芯片上构建 amd64 镜像
docker buildx build --platform linux/amd64 -t fulltext-search .

# 保存镜像
docker save fulltext-search | gzip > fulltext-search.tar.gz
# 或直接 push 到私有 registry
docker tag fulltext-search registry.example.com/fulltext-search:latest
docker push registry.example.com/fulltext-search:latest
```

### 使用 Docker Hub 镜像站

如果无法直接访问 Docker Hub，构建时指定镜像站：

```bash
docker compose build --build-arg REGISTRY=mirror.example.com/library/
```

### 基本用法

```yaml
services:
  fulltext-search:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "${PORT:-8080}:8000"
    volumes:
      - ${DATA_DIR:-./data/docs}:/data/docs:ro
      - ./data/index_data:/data/index
      - ./data/app_data:/data/app
```

### 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORT` | `8080` | Web 访问端口 |
| `DATA_DIR` | `./data/docs` | 资料目录（只读挂载） |
| `OCR_LANG` | `ch` | OCR 语言：ch / en / japan / korean |
| `SCHEDULED_SCAN_TIME` | `00:00` | 每日定时扫描时间 |
| `OCR_CONCURRENT` | `2` | OCR 并发数，OOM 时自动降级 |

容器内环境变量（无需修改）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `INDEX_DIR` | `/data/index` | Tantivy 索引存储路径 |
| `DATA_DIR` | `/data/app` | SQLite 数据库和设置存储路径 |

### 数据持久化

数据存储在 `data/` 目录下，通过 bind mount 挂载到容器：

```
data/
├── docs/          → /data/docs  (只读，放文档)
├── app_data/      → /data/app   (SQLite + 设置)
└── index_data/    → /data/index (Tantivy 索引)
```

容器重启或重建不会丢失数据。迁移时复制整个 `data/` 目录即可：

```bash
rsync -avz ./data/ user@nas:/path/to/fulltext-search/data/
```

### 内存限制

```yaml
mem_limit: 4g
mem_reservation: 1g
```

PaddleOCR 是内存密集型应用。`mem_limit` 限制最大内存（OOM 时容器会被杀死），`mem_reservation` 是软限制。

如果部署在低内存设备（如 J4125 + 3GB），建议：
- 设置 `OCR_CONCURRENT=1`
- 降低 `mem_limit` 为 `2g`

```bash
OCR_CONCURRENT=1 docker compose up -d
```

### 多资料目录

默认只挂载 `./data/docs`。如需多个目录，在 `docker-compose.yml` 的 `volumes` 中追加：

```yaml
volumes:
  - /path/to/contracts:/data/contracts:ro
  - /path/to/reports:/data/reports:ro
```

启动后会自动注册这些目录。

### 使用 Docker Hub 镜像站

如果无法直接访问 Docker Hub，构建时指定镜像站：

```bash
docker compose build --build-arg REGISTRY=mirror.example.com/library/
```

## 配置

通过 Web UI 的设置页面可配置：

| 设置 | 说明 |
|---|---|
| OCR 语言 | 中文 / 英文 / 日文 / 韩文 |
| OCR 并发数 | 根据内存自动建议，OOM 时自动降级 |
| 定时扫描 | 每日定时全量扫描 |
| 排除模式 | glob 模式排除不需要索引的文件 |
| 自动备份 | 定期备份索引数据 |
| 主题 | 浅色 / 深色 / 跟随系统 |

## 数据迁移

索引数据可跨机器迁移（如从 Mac 迁移到 NAS）：

```bash
# 在 Mac 上构建并索引
docker buildx build --platform linux/amd64 -t fulltext-search .
docker run -d \
  -v /本地/资料:/data/docs:ro \
  -v $(pwd)/data/app_data:/data/app \
  -v $(pwd)/data/index_data:/data/index \
  fulltext-search

# 迁移数据（整个 data/ 目录）
rsync -avz ./data/ user@nas:/path/to/fulltext-search/data/

# 在 NAS 上启动
docker compose up -d
```

## 目录结构

```
backend/
  app/
    main.py          — FastAPI 入口
    config.py        — 配置
    routes/          — API 路由
    service/         — 业务逻辑（搜索/索引/扫描/监控）
    extractor/       — 文字提取（文本/Office/PDF/OCR）
    models/          — Pydantic 模型
frontend/
  src/
    pages/           — 搜索/资料库/日志/设置/登录
    components/      — 通用组件（Toast/ConfirmDialog/Auth）
    api/client.ts    — API 客户端
```

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.12 + FastAPI |
| 搜索 | Tantivy (Rust → Python) |
| OCR | PaddleOCR (ONNX) + Tesseract fallback |
| 前端 | React + TypeScript + Tailwind CSS |
| 数据库 | SQLite |
| 容器 | python:3.12-slim |

## License

MIT
