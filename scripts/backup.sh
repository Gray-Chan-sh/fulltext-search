#!/bin/bash
# FullText Search — 数据备份脚本
# 用法: ./scripts/backup.sh [备份目录]
# 默认备份到 ./backups/YYYY-MM-DD/

set -e
BACKUP_DIR="${1:-./backups/$(date +%Y-%m-%d)}"
mkdir -p "$BACKUP_DIR"

echo "=== FullText Search 备份 ==="
echo "备份到: $BACKUP_DIR"

# 检查容器是否在运行
CONTAINER=$(docker ps --filter name=fulltext-search --format "{{.Names}}" | head -1)
if [ -z "$CONTAINER" ]; then
  echo "错误: 找不到运行中的 fulltext-search 容器"
  exit 1
fi

echo "容器: $CONTAINER"

# 备份 app_data（SQLite + 设置）
echo "--- 备份 app_data ---"
docker exec "$CONTAINER" sh -c "sqlite3 /data/app/tracker.db 'VACUUM;'" 2>/dev/null || true
docker cp "$CONTAINER":/data/app "$BACKUP_DIR/app_data"
echo "  app_data: $(du -sh "$BACKUP_DIR/app_data" | cut -f1)"

# 备份 index_data（Tantivy 索引）
echo "--- 备份 index_data ---"
docker cp "$CONTAINER":/data/index "$BACKUP_DIR/index_data"
echo "  index_data: $(du -sh "$BACKUP_DIR/index_data" | cut -f1)"

# 创建压缩包
echo "--- 打包 ---"
tar czf "$BACKUP_DIR.tar.gz" -C "$(dirname "$BACKUP_DIR")" "$(basename "$BACKUP_DIR")"
echo "  压缩包: $(du -sh "$BACKUP_DIR.tar.gz" | cut -f1)"

# 清理临时目录
rm -rf "$BACKUP_DIR"

echo ""
echo "=== 备份完成 ==="
echo "文件: $BACKUP_DIR.tar.gz"
echo ""
echo "恢复方式:"
echo "  tar xzf $BACKUP_DIR.tar.gz -C /"
echo "  docker cp $(dirname $BACKUP_DIR)/app_data $CONTAINER:/data/"
echo "  docker cp $(dirname $BACKUP_DIR)/index_data $CONTAINER:/data/"
