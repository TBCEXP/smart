#!/usr/bin/env bash
# Phase 3 登录验收 — 大文件创建、分享+邮件通知、公开访问
# 用法: bash scripts/phase3_live.sh [BASE_URL] [DATA_DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE="${1:-http://127.0.0.1:8000}"
DATA_DIR="${2:-$ROOT/smart-crm/data}"
ADMIN_EMAIL="${PHASE3_ADMIN_EMAIL:-admin@example.com}"
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
  if [ -z "$code" ] && [ -n "${PHASE3_OTP:-}" ]; then
    code="$PHASE3_OTP"
  fi
  if [ -z "$code" ]; then
    echo "✗ 无法读取 OTP ($email)" >&2
    return 1
  fi
  curl -sf -X POST "$BASE/api/auth/otp/verify" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"code\":\"$code\",\"portal\":\"$portal\"}"
}

echo "=== Phase 3 Live (file transfer + notify) ==="
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

echo ">>> [2] 大文件列表"
FILE_ID=$(curl -sf "$BASE/api/files/transfers" | python3 -c "
import sys, json
rows = json.load(sys.stdin)
print(rows[0]['id'] if rows else '')
")
if [ -z "$FILE_ID" ]; then
  echo ">>> [2b] 创建大文件元数据"
  FILE=$(curl -sf -X POST "${HDR[@]}" "$BASE/api/files/transfers" \
    -d '{"title":"Live Test ZIP","customer_email":"customer@example.com","file_size_mb":10,"content_type":"application/zip","notes":"phase3_live"}')
  FILE_ID=$(echo "$FILE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")
fi
if [ -z "$FILE_ID" ]; then
  echo "✗ 无大文件记录"
  exit 1
fi
echo "✓ file_id=$FILE_ID"

echo ">>> [3] R2 上传 URL"
curl -sf -X POST "${HDR[@]}" "$BASE/api/files/transfers/$FILE_ID/upload-url" \
  -d '{"update_file_url":true}' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('storage:', d.get('storage', d.get('mode', '-')), '| upload_url:', bool(d.get('upload_url')))
"

echo ">>> [4] 分享+邮件通知"
SHARE=$(curl -sf -X POST "${HDR[@]}" "$BASE/api/share/links" \
  -d "{\"resource_type\":\"file\",\"resource_id\":\"$FILE_ID\",\"customer_email\":\"customer@example.com\",\"notify_email\":true,\"notify_message\":\"Phase 3 live test\",\"ttl_days\":7}")
echo "$SHARE" | python3 -m json.tool | head -10
SHARE_TOKEN=$(echo "$SHARE" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('url') or '').split('/s/')[-1])")
NOTIFY_MODE=$(echo "$SHARE" | python3 -c "import sys,json; n=json.load(sys.stdin).get('notify') or {}; print(n.get('mode','none'))")
echo "notify mode: $NOTIFY_MODE"

echo ">>> [5] 公开访问文件分享"
curl -sf "$BASE/api/share/$SHARE_TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('valid'), d
assert d.get('file'), 'missing file payload'
print('valid:', d['valid'], '| title:', d['file'].get('title'))
"

echo ""
echo "=== Phase 3 Live 完成 ==="
