#!/usr/bin/env bash
# 生产环境变量与安全检查
# 用法: bash scripts/check_env.sh [OPT_DIR]
set -euo pipefail

OPT_DIR="${1:-/opt/smart-crm}"
PASS=0
WARN=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
warn() { echo "  ! $1"; WARN=$((WARN+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== SMART CRM 环境检查 ==="
echo "目录: $OPT_DIR"
echo ""

echo "[1] .env 配置"
ENV_FILE="$OPT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  ok ".env 存在"
  SECRET=$(grep -E '^SESSION_SECRET=' "$ENV_FILE" | cut -d= -f2- || true)
  BASE_URL=$(grep -E '^APP_BASE_URL=' "$ENV_FILE" | cut -d= -f2- || true)
  if [ -n "$SECRET" ] && [ "$SECRET" != "change-me-to-random-32-chars-min" ] && [ "${#SECRET}" -ge 24 ]; then
    ok "SESSION_SECRET 已自定义"
  else
    fail "SESSION_SECRET 仍为默认值 — 运行 install.sh 或 openssl rand -hex 24"
  fi
  if [ -n "$BASE_URL" ] && [[ "$BASE_URL" == https://* ]]; then
    ok "APP_BASE_URL 使用 HTTPS: $BASE_URL"
  elif [ -n "$BASE_URL" ]; then
    warn "APP_BASE_URL 非 HTTPS: $BASE_URL（生产建议 HTTPS）"
  else
    warn "APP_BASE_URL 未设置"
  fi
else
  warn ".env 不存在 — install.sh 会从 .env.example 创建"
fi

echo ""
echo "[2] 数据目录"
DATA_ROOT="${DATA_DIR:-/var/lib/smart-crm}"
for sub in smart-crm-data postgres backups; do
  if [ -d "$DATA_ROOT/$sub" ]; then
    ok "$DATA_ROOT/$sub 存在"
  else
    warn "$DATA_ROOT/$sub 未创建"
  fi
done

echo ""
echo "[3] Docker 服务"
if command -v docker >/dev/null && [ -f "$OPT_DIR/docker-compose.yml" ]; then
  if docker compose -f "$OPT_DIR/docker-compose.yml" ps 2>/dev/null | grep -q smart-crm; then
    ok "smart-crm 容器运行中"
  else
    warn "smart-crm 容器未运行"
  fi
  if docker compose -f "$OPT_DIR/docker-compose.yml" ps 2>/dev/null | grep -q postgres; then
    ok "postgres 容器运行中（pgvector）"
  else
    warn "postgres 容器未运行"
  fi
else
  warn "Docker 或 docker-compose.yml 不可用（开发环境可忽略）"
fi

echo ""
echo "[4] API 配置"
CFG="${DATA_ROOT}/smart-crm-data/config.json"
if [ -f "$CFG" ]; then
  ok "config.json 存在"
  for key in exa_api_key firecrawl_api_key openai_api_key feishu_app_id; do
    if python3 -c "
import json, sys
d = json.load(open('$CFG'))
v = d.get('$key', '')
sys.exit(0 if v and str(v).strip() else 1)
" 2>/dev/null; then
      ok "  $key 已配置"
    else
      warn "  $key 未配置"
    fi
  done
else
  warn "config.json 不存在 — 首次启动后 Tab2 配置"
fi

echo ""
echo "[5] 备份 cron"
if crontab -l 2>/dev/null | grep -q backup_daily.sh; then
  ok "backup_daily.sh 已加入 crontab"
else
  warn "未配置每日备份 — 运行: sudo bash scripts/setup_backup_cron.sh"
fi

echo ""
echo "=== 环境检查: ${PASS} 通过, ${WARN} 警告, ${FAIL} 失败 ==="
[ "$FAIL" -eq 0 ]
