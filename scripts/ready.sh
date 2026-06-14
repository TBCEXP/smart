#!/usr/bin/env bash
# 一站式就绪检查 — 静态 + 运行时 + 待办摘要
# 用法: bash scripts/ready.sh [BASE_URL] [--static-only] [--skip-preflight]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE="http://127.0.0.1:8000"
STATIC_ONLY=0
SKIP_PREFLIGHT=0

for arg in "$@"; do
  case "$arg" in
    http*) BASE="$arg" ;;
    --static-only) STATIC_ONLY=1 ;;
    --skip-preflight) SKIP_PREFLIGHT=1 ;;
  esac
done

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM 就绪检查 (ready)                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

if [ "$SKIP_PREFLIGHT" -eq 0 ]; then
  bash "$SCRIPT_DIR/deploy_preflight.sh"
  echo ""
fi

if [ "$STATIC_ONLY" -eq 1 ]; then
  echo "(--static-only) 跳过运行时检查"
  exit 0
fi

if ! curl -sf "$BASE/api/health" >/dev/null 2>&1; then
  echo "服务未运行: $BASE"
  echo "启动: cd smart-crm && USE_SQLITE=1 uvicorn main:app --port 8000 &"
  echo "待办: bash scripts/onboard_checklist.sh"
  exit 0
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 运行状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash "$SCRIPT_DIR/status.sh" "$BASE"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 部署验收"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash "$SCRIPT_DIR/deploy_verify.sh" "$BASE"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Phase 1 + 2"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash "$SCRIPT_DIR/phase1_verify.sh" "$BASE"
bash "$SCRIPT_DIR/phase2_verify.sh" "$BASE"
echo ""

READY_JSON=$(curl -sf "$BASE/api/system/readiness" 2>/dev/null || echo '{}')
INT=$(curl -sf "$BASE/api/integrations/status" 2>/dev/null || echo '{}')
CC=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('configured_count',0))" 2>/dev/null || echo 0)
PR=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('production_ready',False))" 2>/dev/null || echo False)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 生产阻塞摘要"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  API Key: $CC/9 | production_ready=$PR"
echo "$READY_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
b = d.get('production_blockers', {})
print('  阻塞项:', b.get('blocking_count', '?'), '| live_ready:', b.get('live_ready', False))
for item in b.get('detected', []):
    mark = '✓' if item.get('done') else ('✗' if item.get('blocking') else '○')
    print(f\"  {mark} {item.get('label')}\")
for item in b.get('manual', [])[:2]:
    print(f\"  [ ] {item.get('label')}\")
" 2>/dev/null || true
if [ "$PR" = "True" ]; then
  echo "  ✓ 代码 + API Key 就绪 — 可跑全量验收"
  echo "    bash scripts/prod_onboard.sh $BASE --full"
else
  echo "  ○ 待配置 VPS / Secrets / API Key"
  echo "    bash scripts/onboard_checklist.sh $BASE"
fi
echo ""
echo "代码终检: bash scripts/go_live.sh $BASE"
