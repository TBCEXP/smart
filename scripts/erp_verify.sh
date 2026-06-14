#!/usr/bin/env bash
# TBCEXP ERP 桥接验收 — 字段映射 + Mock 推拉
# 用法: bash scripts/erp_verify.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
PASS=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== TBCEXP ERP Bridge Verification ==="
echo "Base: $BASE"
echo ""

if curl -sf "$BASE/api/bridge/tbcexp/field-map" | grep -q '"version"'; then
  ok "GET /api/bridge/tbcexp/field-map"
else
  fail "GET /api/bridge/tbcexp/field-map"
fi

FIELD_COUNT=$(curl -sf "$BASE/api/bridge/tbcexp/field-map" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(len(d.get('lead_push', {}).get('fields', [])))
" 2>/dev/null || echo 0)
if [ "$FIELD_COUNT" -ge 20 ]; then
  ok "field-map lead fields ($FIELD_COUNT)"
else
  fail "field-map lead fields ($FIELD_COUNT)"
fi

LEAD=$(curl -sf "$BASE/api/leads?limit=1" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d['leads'][0]['id'] if d.get('leads') else '')
" 2>/dev/null || echo "")

if [ -n "$LEAD" ] && curl -sf "$BASE/api/bridge/tbcexp/status/$LEAD" | grep -q 'erp_configured'; then
  ok "GET /api/bridge/tbcexp/status/{id}"
else
  fail "GET /api/bridge/tbcexp/status/{id}"
fi

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
TOKEN=""
if [ -n "$CODE" ]; then
  TOKEN=$(curl -sf -X POST "$BASE/api/auth/otp/verify" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"admin@example.com\",\"code\":\"$CODE\",\"portal\":\"admin\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_token',''))" 2>/dev/null || echo "")
fi

if [ -n "$TOKEN" ]; then
  ORDERS=$(curl -sf "$BASE/api/bridge/tbcexp/orders?limit=5" -H "X-Session-Token: $TOKEN")
  if echo "$ORDERS" | grep -q '"mode"'; then
    ok "GET /api/bridge/tbcexp/orders"
  else
    fail "GET /api/bridge/tbcexp/orders"
  fi
  SYNC=$(curl -sf -X POST "$BASE/api/bridge/tbcexp/orders/sync?limit=5" -H "X-Session-Token: $TOKEN")
  if echo "$SYNC" | grep -q '"created"'; then
    ok "POST /api/bridge/tbcexp/orders/sync"
  else
    fail "POST /api/bridge/tbcexp/orders/sync"
  fi
  if [ -n "$LEAD" ]; then
    PUSH=$(curl -sf -X POST "$BASE/api/bridge/tbcexp/$LEAD" -H "X-Session-Token: $TOKEN" || echo '{}')
    if echo "$PUSH" | grep -q '"status":"ok"'; then
      ok "POST /api/bridge/tbcexp/{lead_id}"
    else
      fail "POST /api/bridge/tbcexp/{lead_id}"
    fi
  else
    fail "POST /api/bridge/tbcexp/{lead_id} (no lead)"
  fi
else
  fail "GET /api/bridge/tbcexp/orders (OTP required)"
  fail "POST /api/bridge/tbcexp/orders/sync (OTP required)"
  fail "POST /api/bridge/tbcexp/{lead_id} (OTP required)"
fi

echo ""
echo "=== ERP Bridge: ${PASS} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
