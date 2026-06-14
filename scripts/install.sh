#!/usr/bin/env bash
set -euo pipefail

OPT_DIR="${OPT_DIR:-/opt/smart-crm}"
DATA_DIR="${DATA_DIR:-/var/lib/smart-crm}"

echo "==> SMART CRM 全新安装"
echo "程序目录: $OPT_DIR"
echo "数据目录: $DATA_DIR"

sudo mkdir -p "$OPT_DIR" "$DATA_DIR/smart-crm-data" "$DATA_DIR/postgres" "$DATA_DIR/backups"

if [ ! -f "$OPT_DIR/docker-compose.yml" ]; then
  echo "未找到 $OPT_DIR/docker-compose.yml"
  echo "首次安装请先克隆仓库:"
  echo "  sudo git clone https://github.com/TBCEXP/smart.git $OPT_DIR"
  exit 1
fi

cd "$OPT_DIR"

if [ ! -f .env ] && [ -f .env.example ]; then
  echo "==> 创建 .env（请修改 SESSION_SECRET 和 APP_BASE_URL）"
  sudo cp .env.example .env
  if command -v openssl >/dev/null; then
    SECRET=$(openssl rand -hex 24)
    sudo sed -i "s/change-me-to-random-32-chars-min/$SECRET/" .env 2>/dev/null || true
  fi
fi

export IMAGE_TAG="${IMAGE_TAG:-latest}"
export VERSION="${VERSION:-2.0.0}"
echo "==> 构建并启动容器"
docker compose build smart-crm
docker compose up -d

echo "==> 等待 Postgres + smart-crm 就绪..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "  服务已就绪 (${i}s)"
    break
  fi
  sleep 2
done

if curl -sf http://127.0.0.1:8000/api/health | grep -q '"status":"ok"'; then
  echo "  ✓ 健康检查通过"
else
  echo "  ✗ 健康检查失败"
  echo "  排查: docker compose logs smart-crm --tail 50"
  exit 1
fi

echo ""
echo "==> 运行部署验收"
if bash scripts/vps_verify.sh http://127.0.0.1:8000; then
  echo ""
  echo "安装验收完成。"
else
  echo ""
  echo "验收有警告/失败项，请按提示处理。"
fi

echo ""
echo "安装完成:"
echo "  - 获客面板: http://127.0.0.1:8000  (Nginx 反代: http://服务器IP)"
echo "  - 员工登录: http://127.0.0.1:8000/admin"
echo "  - 数据目录: $DATA_DIR/smart-crm-data"
echo "  - 下一步:"
echo "      1. Tab2 配置 Exa / Firecrawl / OpenAI / 飞书 API Key"
echo "      2. bash scripts/vps_verify.sh  （确认 live 探测通过）"
echo "      3. bash scripts/prod_onboard.sh http://127.0.0.1:8000 --full"
echo "      4. 配置 HTTPS: certbot --nginx -d crm.yourdomain.com"
