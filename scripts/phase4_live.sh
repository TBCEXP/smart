#!/usr/bin/env bash
# Phase 4 登录验收 — 前稿比对规则引擎
# 用法: bash scripts/phase4_live.sh [BASE_URL] [DATA_DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE="${1:-http://127.0.0.1:8000}"
DATA_DIR="${2:-$ROOT/smart-crm/data}"
ADMIN_EMAIL="${PHASE4_ADMIN_EMAIL:-admin@example.com}"
LOG_FILE="${DATA_DIR}/auth_emails.log"

otp_login() {
  local email="$1"
  local portal="$2"
  curl -sf -X POST "$BASE/api/auth/otp/send" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"portal\":\"$portal\"}" >/dev/null
  sleep 1
  local code=""
  if [ -f "$LOG_FILE" ]; then
    code=$(grep -oE '[0-9]{6}' "$LOG_FILE" | tail -1 || true)
  fi
  if [ -z "$code" ] && [ -n "${PHASE4_OTP:-}" ]; then
    code="$PHASE4_OTP"
  fi
  if [ -z "$code" ]; then
    echo "✗ 无法读取 OTP ($email)" >&2
    return 1
  fi
  curl -sf -X POST "$BASE/api/auth/otp/verify" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"code\":\"$code\",\"portal\":\"$portal\"}"
}

echo "=== Phase 4 Live (prepress rule engine) ==="
echo "Base: $BASE"
echo ""

echo ">>> [1] 员工登录"
ADMIN_SESSION=$(otp_login "$ADMIN_EMAIL" "admin")
ADMIN_TOKEN=$(echo "$ADMIN_SESSION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_token',''))")
if [ -z "$ADMIN_TOKEN" ]; then
  echo "✗ 员工登录失败"
  exit 1
fi
echo "✓ admin session"
HDR=(-H "X-Session-Token: $ADMIN_TOKEN" -H "Content-Type: application/json")

echo ">>> [2] 前稿任务"
REVIEW_ID=$(curl -sf "$BASE/api/prepress/reviews" | python3 -c "
import sys, json
rows = json.load(sys.stdin)
print(rows[0]['id'] if rows else '')
")
if [ -z "$REVIEW_ID" ]; then
  echo "✗ 无前稿种子"
  exit 1
fi
echo "✓ review_id=$REVIEW_ID"

echo ">>> [3] 运行规则引擎"
RUN=$(curl -sf -X POST "${HDR[@]}" "$BASE/api/prepress/reviews/$REVIEW_ID/run")
echo "$RUN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('result', {}).get('engine') == 'rule_based', d
print('verdict:', d.get('verdict'), '| barcode:', d.get('result', {}).get('summary', {}).get('barcode_ok'))
"

echo ">>> [4] 条码 SVG"
curl -sf -X POST "$BASE/api/prepress/barcode/generate" \
  -H "Content-Type: application/json" \
  -d '{"value":"5901234123457","symbology":"ean13"}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('ok'), d
print('svg bytes:', len(d.get('svg', '')))
"

echo ""
echo "=== Phase 4 Live 完成 ==="
