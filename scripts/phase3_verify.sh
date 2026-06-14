#!/usr/bin/env bash
# Phase 3 验收 — 大文件元数据、分享邮件通知、员工后台 Tab
# 用法: bash scripts/phase3_verify.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
PASS=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== Phase 3 Verification ==="
echo "Base: $BASE"
echo ""

if curl -sf "$BASE/api/files/transfers" | grep -q 'download_url'; then
  ok "GET /api/files/transfers (download_url field)"
else
  fail "GET /api/files/transfers (download_url field)"
fi

if curl -sf "$BASE/api/files/transfers" | grep -q '包装设计稿'; then
  ok "GET /api/files/transfers (seed)"
else
  fail "GET /api/files/transfers (seed)"
fi

if curl -sf "$BASE/admin/dashboard" | grep -q '大文件'; then
  ok "GET /admin/dashboard (files tab)"
else
  fail "GET /admin/dashboard (files tab)"
fi

READY=$(curl -sf "$BASE/api/system/readiness")
if echo "$READY" | grep -q 'phase3_files_seeded'; then
  ok "GET /api/system/readiness (phase3 checklist)"
else
  fail "GET /api/system/readiness (phase3 checklist)"
fi

FILE_ID=$(curl -sf "$BASE/api/files/transfers" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print((d[0]['id'] if d else ''))
" 2>/dev/null || echo "")

if [ -n "$FILE_ID" ]; then
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
  if [ -n "${PHASE3_OTP:-}" ]; then CODE="$PHASE3_OTP"; fi
  TOKEN=""
  if [ -n "$CODE" ]; then
    TOKEN=$(curl -sf -X POST "$BASE/api/auth/otp/verify" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"admin@example.com\",\"code\":\"$CODE\",\"portal\":\"admin\"}" \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_token',''))" 2>/dev/null || echo "")
  fi
  if [ -n "$TOKEN" ]; then
    SHARE=$(curl -sf -X POST "$BASE/api/share/links" \
      -H "X-Session-Token: $TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"resource_type\":\"file\",\"resource_id\":\"$FILE_ID\",\"customer_email\":\"notify@test.com\",\"notify_email\":true,\"ttl_days\":7}")
    if echo "$SHARE" | grep -q 'notify'; then
      ok "POST /api/share/links (notify field)"
    else
      fail "POST /api/share/links (notify field)"
    fi
    SHARE_TOKEN=$(echo "$SHARE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null || echo "")
    if [ -n "$SHARE_TOKEN" ] && curl -sf "$BASE/api/share/$SHARE_TOKEN" | grep -q '"file"'; then
      ok "GET /api/share/{token} (file resource)"
    else
      fail "GET /api/share/{token} (file resource)"
    fi
  else
    fail "POST /api/share/links (OTP login required)"
    fail "GET /api/share/{token} (file resource)"
  fi
else
  fail "POST /api/share/links (no file id)"
  fail "GET /api/share/{token} (file resource)"
fi

if curl -sf "$BASE/api/system/handoff-report" | grep -q 'Phase 3'; then
  ok "GET /api/system/handoff-report (phase3 section)"
else
  fail "GET /api/system/handoff-report (phase3 section)"
fi

echo ""
echo "=== Phase 3: ${PASS} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
