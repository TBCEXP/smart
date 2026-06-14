#!/usr/bin/env bash
set -euo pipefail

OPT_DIR="${OPT_DIR:-/opt/smart-crm}"
DATA_DIR="${DATA_DIR:-/var/lib/smart-crm}"
BACKUP="$DATA_DIR/backups/pre-upgrade-$(date +%F-%H%M).tar.gz"

echo "==> 备份数据目录"
sudo tar czf "$BACKUP" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")"
echo "备份: $BACKUP"

cd "$OPT_DIR"
export VERSION="${VERSION:-latest}"
docker compose build smart-crm
docker compose up -d smart-crm

sleep 3
curl -sf http://127.0.0.1:8000/api/health && echo " 升级成功" || echo " 健康检查失败"
