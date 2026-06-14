#!/usr/bin/env bash
# Phase 4 验收 — 印刷前稿 AI（条码 + 文本/图形 diff）
# 用法: bash scripts/phase4_verify.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
PASS=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== Phase 4 Verification ==="
echo "Base: $BASE"
echo ""

if curl -sf "$BASE/api/prepress/reviews" | grep -q 'barcode_expected'; then
  ok "GET /api/prepress/reviews"
else
  fail "GET /api/prepress/reviews"
fi

if curl -sf "$BASE/api/prepress/reviews" | grep -q '包装标签'; then
  ok "GET /api/prepress/reviews (seed)"
else
  fail "GET /api/prepress/reviews (seed)"
fi

if curl -sf -X POST "$BASE/api/prepress/barcode/validate" \
  -H 'Content-Type: application/json' \
  -d '{"value":"5901234123457","symbology":"ean13"}' | grep -q '"valid":true'; then
  ok "POST /api/prepress/barcode/validate (valid)"
else
  fail "POST /api/prepress/barcode/validate (valid)"
fi

if curl -sf -X POST "$BASE/api/prepress/barcode/validate" \
  -H 'Content-Type: application/json' \
  -d '{"value":"5901234123458","symbology":"ean13"}' | grep -q '"valid":false'; then
  ok "POST /api/prepress/barcode/validate (invalid)"
else
  fail "POST /api/prepress/barcode/validate (invalid)"
fi

if curl -sf -X POST "$BASE/api/prepress/barcode/generate" \
  -H 'Content-Type: application/json' \
  -d '{"value":"5901234123457","symbology":"ean13"}' | grep -q '<svg'; then
  ok "POST /api/prepress/barcode/generate"
else
  fail "POST /api/prepress/barcode/generate"
fi

if curl -sf "$BASE/admin/dashboard" | grep -q '印刷前稿'; then
  ok "GET /admin/dashboard (prepress tab)"
else
  fail "GET /admin/dashboard (prepress tab)"
fi

READY=$(curl -sf "$BASE/api/system/readiness")
if echo "$READY" | grep -q 'phase4_prepress_seeded'; then
  ok "GET /api/system/readiness (phase4 checklist)"
else
  fail "GET /api/system/readiness (phase4 checklist)"
fi

REVIEW_ID=$(curl -sf "$BASE/api/prepress/reviews" | python3 -c "
import sys, json
rows = json.load(sys.stdin)
print(rows[0]['id'] if rows else '')
" 2>/dev/null || echo "")

if [ -n "$REVIEW_ID" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  DATA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/smart-crm/data"
  LOG_FILE="${DATA_DIR}/auth_emails.log"
  curl -sf -X POST "$BASE/api/auth/otp/send" \
    -H 'Content-Type: application/json' \
    -d '{"email":"admin@example.com","portal":"admin"}' >/dev/null 2>&1 || true
  sleep 1
  CODE=""
  if [ -f "$LOG_FILE" ]; then
    CODE=$(grep -oE '[0-9]{6}' "$LOG_FILE" | tail -1 || true)
  fi
  if [ -n "${PHASE4_OTP:-}" ]; then CODE="$PHASE4_OTP"; fi
  TOKEN=""
  if [ -n "$CODE" ]; then
    TOKEN=$(curl -sf -X POST "$BASE/api/auth/otp/verify" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"admin@example.com\",\"code\":\"$CODE\",\"portal\":\"admin\"}" \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_token',''))" 2>/dev/null || echo "")
  fi
  if [ -n "$TOKEN" ]; then
    RUN=$(curl -sf -X POST "$BASE/api/prepress/reviews/$REVIEW_ID/run" \
      -H "X-Session-Token: $TOKEN")
    if echo "$RUN" | grep -q 'rule_based'; then
      ok "POST /api/prepress/reviews/{id}/run"
    else
      fail "POST /api/prepress/reviews/{id}/run"
    fi
  else
    fail "POST /api/prepress/reviews/{id}/run (OTP required)"
  fi
else
  fail "POST /api/prepress/reviews/{id}/run (no review id)"
fi

if curl -sf "$BASE/api/system/handoff-report" | grep -q 'Phase 4'; then
  ok "GET /api/system/handoff-report (phase4 section)"
else
  fail "GET /api/system/handoff-report (phase4 section)"
fi

echo ""
echo "=== Phase 4: ${PASS} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
