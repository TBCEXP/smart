#!/usr/bin/env bash
set -euo pipefail

OPT_DIR="${OPT_DIR:-/opt/smart-crm}"
DATA_DIR="${DATA_DIR:-/var/lib/smart-crm}"

echo "==> SMART CRM 全新安装"
echo "程序目录: $OPT_DIR"
echo "数据目录: $DATA_DIR"

sudo mkdir -p "$OPT_DIR" "$DATA_DIR/smart-crm-data" "$DATA_DIR/postgres" "$DATA_DIR/backups"

if [ ! -f "$OPT_DIR/docker-compose.yml" ]; then
  echo "请将 docker-compose.yml 复制到 $OPT_DIR"
  exit 1
fi

cd "$OPT_DIR"
export VERSION="${VERSION:-latest}"
docker compose build smart-crm
docker compose up -d

echo "==> 等待服务启动..."
sleep 5
curl -sf http://127.0.0.1:8000/api/health && echo " OK" || echo " 健康检查失败，请检查日志"

echo ""
echo "安装完成:"
echo "  - 获客面板: http://127.0.0.1:8000"
echo "  - 员工登录: http://127.0.0.1:8000/admin"
echo "  - 数据目录: $DATA_DIR/smart-crm-data"
echo "  - 下一步: 浏览器 Tab2 配置 API Key"
