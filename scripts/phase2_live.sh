#!/usr/bin/env bash
# Phase 2 登录验收 — 员工目录分享 + 客户门户授权目录
# 用法: bash scripts/phase2_live.sh [BASE_URL] [DATA_DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE="${1:-http://127.0.0.1:8000}"
DATA_DIR="${2:-$ROOT/smart-crm/data}"
ADMIN_EMAIL="${PHASE2_ADMIN_EMAIL:-admin@example.com}"
CUSTOMER_EMAIL="${PHASE2_CUSTOMER_EMAIL:-customer@example.com}"
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
  if [ -z "$code" ] && [ -n "${PHASE2_OTP:-}" ]; then
    code="$PHASE2_OTP"
  fi
  if [ -z "$code" ]; then
    echo "✗ 无法读取 OTP ($email)" >&2
    return 1
  fi
  curl -sf -X POST "$BASE/api/auth/otp/verify" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"code\":\"$code\",\"portal\":\"$portal\"}"
}

echo "=== Phase 2 Live (portal + catalog share) ==="
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

echo ">>> [2] 目录列表"
DOC_ID=$(curl -sf "$BASE/api/catalog/documents" | python3 -c "
import sys, json
docs = json.load(sys.stdin)
print(docs[0]['id'] if docs else '')
")
if [ -z "$DOC_ID" ]; then
  echo "✗ 无目录种子数据"
  exit 1
fi
echo "✓ catalog doc_id=$DOC_ID"

echo ">>> [3] 目录分享链接"
SHARE=$(curl -sf -X POST "${HDR[@]}" "$BASE/api/share/links" \
  -d "{\"resource_type\":\"catalog\",\"resource_id\":\"$DOC_ID\",\"ttl_days\":7}")
SHARE_TOKEN=$(echo "$SHARE" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('url') or '').split('/s/')[-1])")
echo "$SHARE" | python3 -m json.tool | head -8

echo ">>> [4] 公开访问目录分享"
curl -sf "$BASE/api/share/$SHARE_TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('valid'), d
assert d.get('catalog'), 'missing catalog payload'
print('valid:', d['valid'], '| title:', d['catalog'].get('title'))
"

echo ">>> [5] 客户门户登录"
CUSTOMER_SESSION=$(otp_login "$CUSTOMER_EMAIL" "portal")
CUSTOMER_TOKEN=$(echo "$CUSTOMER_SESSION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_token',''))")
if [ -z "$CUSTOMER_TOKEN" ]; then
  echo "✗ 客户登录失败"
  exit 1
fi
CHDR=(-H "X-Session-Token: $CUSTOMER_TOKEN")

echo ">>> [6] 授权目录"
curl -sf "${CHDR[@]}" "$BASE/api/portal/catalogs" | python3 -c "
import sys, json
cats = json.load(sys.stdin)
print('authorized catalogs:', len(cats))
assert len(cats) >= 1, 'customer should see at least 1 catalog'
print('first:', cats[0].get('title'), '| storage:', cats[0].get('storage'))
"

echo ">>> [7] 下载链接 API"
curl -sf "${CHDR[@]}" "$BASE/api/catalog/documents/$DOC_ID/download-url" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('storage:', d.get('storage'), '| mode:', d.get('mode'))
"

echo ""
echo "=== Phase 2 Live 完成 ==="
