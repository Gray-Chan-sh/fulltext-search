#!/bin/bash
set -e

# ============================================================
# FullText Search — 一键部署脚本
# 支持 Ubuntu/Debian/CentOS/Rocky Linux
# 用法:
#   ./scripts/deploy.sh                       # 部署到当前目录
#   DATA_DIR=/mnt/docs ./scripts/deploy.sh    # 自定义资料目录
#   EXTRA_DIRS=/mnt/books,/mnt/photos ./scripts/deploy.sh  # 多个目录
#   支持 macOS / Linux / Windows (Git Bash)
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 检测操作系统
detect_os() {
    case "$(uname -s)" in
        Darwin)
            OS="macos"
            OS_VERSION="$(sw_vers -productVersion 2>/dev/null || echo "unknown")"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            OS="windows"
            OS_VERSION="$(uname -s)"
            ;;
        Linux)
            if [ -f /etc/os-release ]; then
                . /etc/os-release
                OS=$ID
                OS_VERSION=$VERSION_ID
            else
                OS="linux"
                OS_VERSION="unknown"
            fi
            ;;
        *)
            OS="unknown"
            OS_VERSION="$(uname -s)"
            ;;
    esac
    log "检测到系统: $OS $OS_VERSION"
}

# 安装 Docker
install_docker() {
    if command -v docker &>/dev/null; then
        log "Docker 已安装: $(docker --version)"
        return
    fi
    warn "Docker 未安装，正在安装..."

    case $OS in
        macos)
            warn "macOS 请手动安装 Docker Desktop: https://www.docker.com/products/docker-desktop/"
            warn "安装后重新运行此脚本"
            exit 1
            ;;
        windows)
            warn "Windows 请手动安装 Docker Desktop: https://www.docker.com/products/docker-desktop/"
            warn "安装后重新运行此脚本"
            exit 1
            ;;
        ubuntu|debian)
            apt-get update -qq
            apt-get install -y -qq ca-certificates curl
            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/$OS/gpg -o /etc/apt/keyrings/docker.asc
            chmod a+r /etc/apt/keyrings/docker.asc
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$OS $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
            apt-get update -qq
            apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
            systemctl enable --now docker
            ;;
        centos|rocky|rhel)
            yum install -y yum-utils
            yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            systemctl enable --now docker
            ;;
        *)
            err "不支持的平台: $OS"
            ;;
    esac
    log "Docker 安装完成"
}

# 准备目录和配置
setup_dirs() {
    local base_dir="${1:-$(pwd)}"
    base_dir="$(cd "$base_dir" && pwd)"  # resolve to absolute path
    mkdir -p "$base_dir"/data/{docs,app_data,index_data}

    # 如果脚本目录和 base_dir 不同，复制 docker-compose.yml
    local script_dir="$(cd "$(dirname "$0")/.." && pwd)"
    if [ "$script_dir" != "$base_dir" ] && [ -f "$script_dir/docker-compose.yml" ]; then
        cp "$script_dir/docker-compose.yml" "$base_dir/"
    elif [ ! -f "$base_dir/docker-compose.yml" ]; then
        cd "$script_dir" && cp docker-compose.yml "$base_dir/"
    fi

    cd "$base_dir"
    log "工作目录: $base_dir"

    # 创建 docker-compose.yml（如果不存在）
    if [ ! -f docker-compose.yml ]; then
        # Build extra volumes line from EXTRA_DIRS
        extra_volumes=""
        if [ -n "${EXTRA_DIRS}" ]; then
            IFS=',' read -ra dirs <<< "${EXTRA_DIRS}"
            for dir in "${dirs[@]}"; do
                dir=$(echo "$dir" | xargs)  # trim
                name=$(basename "$dir")
                extra_volumes="$extra_volumes\n      - ${dir}:/data/${name}:ro"
            done
        fi
        cat > docker-compose.yml << COMPOSE
services:
  fulltext-search:
    image: fulltext-search:latest
    build:
      context: .
      dockerfile: backend/Dockerfile
      args:
        - REGISTRY=${REGISTRY:-}
    platform: linux/amd64
    ports:
      - "${PORT:-8080}:8000"
    volumes:
      - ${DATA_DIR:-./data/docs}:/data/docs:ro$(echo -e "$extra_volumes")
      - ./data/index_data:/data/index
      - ./data/app_data:/data/app
    environment:
      - INDEX_DIR=/data/index
      - DATA_DIR=/data/app
      - OCR_LANG=${OCR_LANG:-ch}
      - SCHEDULED_SCAN_TIME=${SCHEDULED_SCAN_TIME:-00:00}
      - OCR_CONCURRENT=${OCR_CONCURRENT:-2}
    restart: unless-stopped
    mem_limit: 4g
    mem_reservation: 1g
COMPOSE
        log "docker-compose.yml 已创建"
    fi

    # 复制 backend 和 frontend（如果是源码目录，且与 base_dir 不同）
    local src_dir="$(cd "$(dirname "$0")/.." && pwd)"
    if [ -d "$src_dir/backend" ] && [ "$src_dir" != "$(pwd)" ]; then
        log "从 $src_dir 复制源码..."
        cp -r "$src_dir/backend" "$src_dir/frontend" . 2>/dev/null || true
    fi
}

# 检查源码是否存在
check_source() {
    local target_dir="$1"
    if [ -f "$target_dir/backend/Dockerfile" ] && [ -f "$target_dir/docker-compose.yml" ]; then
        return 0
    fi
    # 如果有 docker-compose.yml 且已有镜像，也可以跳过源码
    if [ -f "$target_dir/docker-compose.yml" ] && docker image inspect fulltext-search >/dev/null 2>&1; then
        log "使用现有镜像"
        return 0
    fi
    warn "请在项目根目录执行此脚本"
    exit 1
}

# 构建并启动
build_and_run() {
    cd "$1"

    if [ "${SKIP_BUILD:-0}" != "1" ]; then
        log "构建 Docker 镜像..."
        if [ -n "${REGISTRY}" ]; then
            docker compose build --build-arg "REGISTRY=${REGISTRY}"
        else
            docker compose build
        fi
    else
        log "跳过构建，使用现有镜像..."
    fi

    log "启动服务..."
    docker compose up -d

    echo ""
    log "========================================"
    log " FullText Search 部署完成！"
    log "========================================"
    echo ""
    echo "  访问地址: http://$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}'):${PORT:-8080}"
    echo "  默认密码: admin"
    echo ""
    echo "  管理命令:"
    echo "    docker compose logs -f     # 查看日志"
    echo "    docker compose restart     # 重启"
    echo "    docker compose down        # 停止"
    echo ""
    echo "  数据目录:"
    echo "    $1/data/docs/     — 放入需要索引的文档"
    echo "    $1/data/app_data/  — 索引数据 + 数据库"
    echo "    $1/data/index_data/— Tantivy 索引"
    echo ""
}

# 主流程
main() {
    echo ""
    echo "========================================"
    echo " FullText Search 一键部署"
    echo "========================================"
    echo ""

    # 如果当前目录有 .env，加载环境变量
    if [ -f .env ]; then
        log "加载 .env 配置..."
        set -a
        source .env
        set +a
    fi

    # 如果以 root 运行，建议使用普通用户
    if [ "$(id -u)" = "0" ]; then
        warn "建议使用普通用户运行（当前为 root）"
    fi

    detect_os

    # 确定安装目录（默认当前目录）
    INSTALL_DIR="${1:-$(pwd)}"
    INSTALL_DIR="$(cd "$INSTALL_DIR" && pwd)"

    install_docker
    setup_dirs "$INSTALL_DIR"
    check_source "$INSTALL_DIR"
    build_and_run "$INSTALL_DIR"
}

main "$@"
