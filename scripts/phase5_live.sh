#!/usr/bin/env bash
# Phase 5 登录验收 — OpenCV 对齐 + 人工终审
# 用法: bash scripts/phase5_live.sh [BASE_URL] [DATA_DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE="${1:-http://127.0.0.1:8000}"
DATA_DIR="${2:-$ROOT/smart-crm/data}"
ADMIN_EMAIL="${PHASE5_ADMIN_EMAIL:-admin@example.com}"
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
  if [ -z "$code" ] && [ -n "${PHASE5_OTP:-}" ]; then
    code="$PHASE5_OTP"
  fi
  if [ -z "$code" ]; then
    echo "✗ 无法读取 OTP ($email)" >&2
    return 1
  fi
  curl -sf -X POST "$BASE/api/auth/otp/verify" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"code\":\"$code\",\"portal\":\"$portal\"}"
}

echo "=== Phase 5 Live (production inspect + human review) ==="
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

echo ">>> [2] 实拍检测任务"
INSP_ID=$(curl -sf "$BASE/api/inspections/production" | python3 -c "
import sys, json
rows = json.load(sys.stdin)
print(rows[0]['id'] if rows else '')
")
if [ -z "$INSP_ID" ]; then
  echo "✗ 无检测种子"
  exit 1
fi
echo "✓ inspection_id=$INSP_ID"

echo ">>> [3] OpenCV 比对"
RUN=$(curl -sf -X POST "${HDR[@]}" "$BASE/api/inspections/production/$INSP_ID/run")
echo "$RUN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('result', {}).get('engine') == 'opencv_align', d
s = d.get('result', {}).get('summary', {})
print('verdict:', d.get('verdict'), '| alignment:', s.get('alignment'), '| diff:', s.get('diff_pct'), '%')
"

echo ">>> [4] 人工终审"
REV=$(curl -sf -X PATCH "${HDR[@]}" "$BASE/api/inspections/production/$INSP_ID/review" \
  -d '{"human_review_status":"approved","human_review_notes":"phase5_live OK"}')
echo "$REV" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('human_review_status') == 'approved', d
print('human_review:', d.get('human_review_status'), 'by', d.get('human_reviewed_by'))
"

echo ""
echo "=== Phase 5 Live 完成 ==="
