#!/usr/bin/env bash
# PR 合并前全量验收 — 确保分支可安全合并到 main
# 用法: bash scripts/pre_merge_verify.sh [BASE_URL]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE="${1:-http://127.0.0.1:8000}"

echo "╔══════════════════════════════════════════════════╗"
echo "║     SMART CRM 合并前验收 (pre-merge)            ║"
echo "╚══════════════════════════════════════════════════╝"
echo "Base: $BASE"
echo "Branch: $(git -C "$ROOT" branch --show-current 2>/dev/null || echo unknown)"
echo ""

echo ">>> [1] pytest"
cd "$ROOT/smart-crm"
PYTHONPATH=. python3 -m pytest tests/ -q
echo ""

echo ">>> [2] 全量脚本验收"
bash "$SCRIPT_DIR/run_all_tests.sh" "$BASE"
echo ""

echo ">>> [3] 就绪检查"
READY=$(curl -sf "$BASE/api/system/readiness")
echo "$READY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
c = d.get('checklist', {})
b = d.get('business', {})
print('production_ready:', d.get('production_ready'))
print('checklist:', json.dumps(c, ensure_ascii=False))
print('phase1:', b.get('phase1'))
print('phase2:', b.get('phase2'))
"

echo ""
echo ">>> [4] 合并清单"
CHECKS=0
PASS=0
check() {
  CHECKS=$((CHECKS+1))
  if eval "$2"; then
    echo "  ✓ $1"
    PASS=$((PASS+1))
  else
    echo "  ✗ $1"
  fi
}

check "pytest 通过" "true"
check "smoke 通过" "bash '$SCRIPT_DIR/smoke_test.sh' '$BASE' >/dev/null"
check "phase1_verify" "bash '$SCRIPT_DIR/phase1_verify.sh' '$BASE' >/dev/null"
check "phase2_verify" "bash '$SCRIPT_DIR/phase2_verify.sh' '$BASE' >/dev/null"
check "erp_verify" "bash '$SCRIPT_DIR/erp_verify.sh' '$BASE' >/dev/null"
check "readiness 含 business" "echo '$READY' | grep -q phase1_factories_seeded"
check "handoff-report" "curl -sf '$BASE/api/system/handoff-report' | grep -q '交接报告'"

echo ""
echo "=== 合并前验收: ${PASS}/${CHECKS} 项通过 ==="
if [ "$PASS" -lt "$CHECKS" ]; then
  echo "请修复失败项后再合并 PR。"
  exit 1
fi
echo ""
echo "建议操作:"
echo "  1. VPS: cd /opt/smart-crm && bash scripts/upgrade.sh"
echo "  2. 终验收: bash scripts/go_live.sh $BASE"
echo "  3. 生产: bash scripts/prod_onboard.sh https://crm.domain.com --full"
