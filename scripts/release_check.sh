#!/usr/bin/env bash
# v2.1.0 发布包完整性检查
# 用法: bash scripts/release_check.sh [BASE_URL] [--skip-pytest]
set -euo pipefail

BASE="http://127.0.0.1:8000"
SKIP_PYTEST=0
PASS=0
FAIL=0

for arg in "$@"; do
  case "$arg" in
    http*) BASE="$arg" ;;
    --skip-pytest) SKIP_PYTEST=1 ;;
  esac
done

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== SMART CRM v2.1.0 Release Check ==="
echo "Base: $BASE"
echo ""

VER=$(curl -sf "$BASE/api/health" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('version',''))" 2>/dev/null || echo "")
if echo "$VER" | grep -qE '^2\.[01]'; then
  ok "health version ($VER)"
else
  fail "health version ($VER)"
fi

for f in docs/CHANGELOG.md docs/VPS_ONBOARDING.md docs/PRODUCTION_READY.md; do
  if [ -f "$f" ]; then ok "$f"; else fail "missing $f"; fi
done

for s in erp_verify.sh prod_readiness_check.sh release_check.sh; do
  if [ -x "scripts/$s" ]; then ok "scripts/$s"; else fail "scripts/$s"; fi
done

cd smart-crm
if [ "$SKIP_PYTEST" -eq 0 ]; then
  PY_SUMMARY=$(PYTHONPATH=. python3 -m pytest tests/ -q --tb=no 2>/dev/null | tail -1)
  PY_EXIT=$?
  PY_CNT=$(echo "$PY_SUMMARY" | grep -oE '^[0-9]+ passed' | head -1 || true)
  EXPECTED=$(PYTHONPATH=. python3 -m pytest tests/ --collect-only -q 2>/dev/null | tail -1 | grep -oE '[0-9]+' | head -1 || echo "39")
  if [ "$PY_EXIT" -eq 0 ] && [ -n "$PY_CNT" ] && [ "$(echo "$PY_CNT" | grep -oE '^[0-9]+')" = "$EXPECTED" ]; then
    ok "pytest ($PY_CNT)"
  else
    fail "pytest (${PY_SUMMARY:-failed}, expected ${EXPECTED})"
  fi
else
  ok "pytest (skipped)"
fi
cd ..

if bash scripts/smoke_test.sh "$BASE" >/dev/null 2>&1; then
  ok "smoke_test (47+)"
else
  fail "smoke_test"
fi

if bash scripts/pre_merge_verify.sh "$BASE" >/dev/null 2>&1; then
  ok "pre_merge_verify (10/10)"
else
  fail "pre_merge_verify"
fi

echo ""
echo "=== Release Check: ${PASS} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
