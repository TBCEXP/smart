#!/usr/bin/env bash
# VPS 部署后验收脚本 — 第零期 + 服务就绪检查
# 用法: bash scripts/vps_verify.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
PASS=0
FAIL=0
WARN=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }
warn() { echo "  ! $1"; WARN=$((WARN+1)); }

echo "=== SMART CRM VPS 验收 ==="
echo "Base: $BASE"
echo ""

echo "[1] 服务健康"
if curl -sf "$BASE/api/health" | grep -q '"status":"ok"'; then
  ok "GET /api/health"
else
  fail "GET /api/health — 服务未启动"
  echo "请先: cd /opt/smart-crm && docker compose up -d"
  exit 1
fi

echo ""
echo "[2] 系统集成状态"
INT=$(curl -sf "$BASE/api/integrations/status")
CC=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('configured_count',0))" 2>/dev/null || echo 0)
if [ "$CC" -ge 4 ]; then
  ok "API Key 已配置 $CC/8（≥4）"
else
  warn "API Key 仅 $CC/8 — Tab2 配置 Exa/Firecrawl/OpenAI/飞书"
fi

echo ""
echo "[3] API 连通性探测"
PROBE=$(curl -sf -X POST "$BASE/api/integrations/probe" || echo '{}')
LIVE=$(echo "$PROBE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('summary',{}).get('live_ok',0))" 2>/dev/null || echo 0)
if echo "$PROBE" | grep -q 'probes'; then
  ok "POST /api/integrations/probe"
  if [ "$LIVE" -ge 4 ]; then
    ok "四项 live API 探测通过 ($LIVE)"
  else
    warn "live 探测通过 $LIVE/4 — Mock 模式或 Key 无效"
  fi
else
  fail "POST /api/integrations/probe"
fi

echo ""
echo "[4] 就绪检查"
READY=$(curl -sf "$BASE/api/system/readiness" || echo '{}')
if echo "$READY" | grep -q 'checklist'; then
  ok "GET /api/system/readiness"
else
  fail "GET /api/system/readiness"
fi

echo ""
echo "[5] Docker（本机 VPS）"
if command -v docker >/dev/null; then
  if docker compose -f /opt/smart-crm/docker-compose.yml ps 2>/dev/null | grep -q smart-crm; then
    ok "smart-crm 容器运行中"
  elif docker ps 2>/dev/null | grep -q smart-crm; then
    ok "smart-crm 容器运行中"
  else
    warn "未检测到 smart-crm 容器（远程验收可忽略）"
  fi
else
  warn "无 docker 命令（远程验收可忽略）"
fi

echo ""
echo "[6] Smoke 测试"
if bash "$(dirname "$0")/smoke_test.sh" "$BASE"; then
  ok "smoke_test.sh 全部通过"
else
  fail "smoke_test.sh 有失败项"
fi

echo ""
echo "=== VPS 验收: ${PASS} 通过, ${WARN} 警告, ${FAIL} 失败 ==="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
echo ""
echo "下一步:"
echo "  1. Tab2 配置 API Key 后重新运行: bash scripts/vps_verify.sh"
echo "  2. 真实 Key 就绪后: bash scripts/pilot_live.sh"
exit 0
