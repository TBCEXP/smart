#!/usr/bin/env bash
# Phase 5 验收 — 大货实拍 AI（OpenCV 对齐 + 人工终审）
# 用法: bash scripts/phase5_verify.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
PASS=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== Phase 5 Verification ==="
echo "Base: $BASE"
echo ""

if curl -sf "$BASE/api/inspections/production" | grep -q 'approved_image'; then
  ok "GET /api/inspections/production"
else
  fail "GET /api/inspections/production"
fi

if curl -sf "$BASE/api/inspections/production" | grep -q '大货包装实拍'; then
  ok "GET /api/inspections/production (seed)"
else
  fail "GET /api/inspections/production (seed)"
fi

if curl -sf "$BASE/admin/dashboard" | grep -q '大货实拍'; then
  ok "GET /admin/dashboard (production tab)"
else
  fail "GET /admin/dashboard (production tab)"
fi

READY=$(curl -sf "$BASE/api/system/readiness")
if echo "$READY" | grep -q 'phase5_inspection_seeded'; then
  ok "GET /api/system/readiness (phase5 checklist)"
else
  fail "GET /api/system/readiness (phase5 checklist)"
fi

INSP_ID=$(curl -sf "$BASE/api/inspections/production" | python3 -c "
import sys, json
rows = json.load(sys.stdin)
print(rows[0]['id'] if rows else '')
" 2>/dev/null || echo "")

if [ -n "$INSP_ID" ]; then
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
  if [ -n "${PHASE5_OTP:-}" ]; then CODE="$PHASE5_OTP"; fi
  TOKEN=""
  if [ -n "$CODE" ]; then
    TOKEN=$(curl -sf -X POST "$BASE/api/auth/otp/verify" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"admin@example.com\",\"code\":\"$CODE\",\"portal\":\"admin\"}" \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_token',''))" 2>/dev/null || echo "")
  fi
  if [ -n "$TOKEN" ]; then
    RUN=$(curl -sf -X POST "$BASE/api/inspections/production/$INSP_ID/run" \
      -H "X-Session-Token: $TOKEN")
    if echo "$RUN" | grep -q 'opencv_align'; then
      ok "POST /api/inspections/production/{id}/run"
    else
      fail "POST /api/inspections/production/{id}/run"
    fi
    REV=$(curl -sf -X PATCH "$BASE/api/inspections/production/$INSP_ID/review" \
      -H "X-Session-Token: $TOKEN" \
      -H 'Content-Type: application/json' \
      -d '{"human_review_status":"approved","human_review_notes":"phase5 verify"}')
    if echo "$REV" | grep -q '"human_review_status":"approved"'; then
      ok "PATCH /api/inspections/production/{id}/review"
    else
      fail "PATCH /api/inspections/production/{id}/review"
    fi
  else
    fail "POST /api/inspections/production/{id}/run (OTP required)"
    fail "PATCH /api/inspections/production/{id}/review (OTP required)"
  fi
else
  fail "POST /api/inspections/production/{id}/run (no id)"
  fail "PATCH /api/inspections/production/{id}/review (no id)"
fi

if curl -sf "$BASE/api/system/handoff-report" | grep -q 'Phase 5'; then
  ok "GET /api/system/handoff-report (phase5 section)"
else
  fail "GET /api/system/handoff-report (phase5 section)"
fi

echo ""
echo "=== Phase 5: ${PASS} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
