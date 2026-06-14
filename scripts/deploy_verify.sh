#!/usr/bin/env bash
# 部署后快速验收 — VPS / GitHub Actions 用（不含 pytest，约 1–3 分钟）
# 用法: bash scripts/deploy_verify.sh [BASE_URL]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE="${1:-http://127.0.0.1:8000}"
PASS=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== SMART CRM 部署验收 (deploy_verify) ==="
echo "Base: $BASE"
echo ""

echo "[1] 健康检查"
HEALTH=$(curl -sf "$BASE/api/health" 2>/dev/null || echo '{}')
if echo "$HEALTH" | grep -q '"status":"ok"'; then
  VER=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "?")
  ok "health ok (version $VER)"
else
  fail "health unreachable"
fi

echo ""
echo "[2] 核心脚本"
if bash "$SCRIPT_DIR/phase15_verify.sh" "$BASE" --quick >/dev/null 2>&1; then
  ok "phase15_verify --quick"
else
  fail "phase15_verify --quick"
fi
for script in phase3_verify.sh phase4_verify.sh phase5_verify.sh erp_verify.sh; do
  if bash "$SCRIPT_DIR/$script" "$BASE" >/dev/null 2>&1; then
    ok "$script"
  else
    fail "$script"
  fi
done

echo ""
echo "[3] 就绪快照"
if curl -sf "$BASE/api/system/readiness" | grep -q checklist; then
  ok "system/readiness"
else
  fail "system/readiness"
fi

echo ""
echo "=== Deploy Verify: ${PASS} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
