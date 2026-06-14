#!/usr/bin/env bash
# Phase 1 登录后写操作验收 — OTP 自动读取 auth_emails.log
# 用法: bash scripts/phase1_live.sh [BASE_URL] [DATA_DIR]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
DATA_DIR="${2:-smart-crm/data}"
EMAIL="${PHASE1_EMAIL:-admin@example.com}"
LOG_FILE="${DATA_DIR}/auth_emails.log"

echo "=== Phase 1 Live (authenticated) ==="
echo "Base: $BASE | Email: $EMAIL"
echo ""

echo ">>> [1] 发送 OTP"
curl -sf -X POST "$BASE/api/auth/otp/send" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"portal\":\"admin\"}" | python3 -m json.tool 2>/dev/null || true
sleep 1

CODE=""
if [ -f "$LOG_FILE" ]; then
  CODE=$(grep -oE '[0-9]{6}' "$LOG_FILE" | tail -1 || true)
fi
if [ -z "$CODE" ]; then
  echo "✗ 无法从 $LOG_FILE 读取 OTP，请手动: PHASE1_OTP=123456 bash $0"
  if [ -n "${PHASE1_OTP:-}" ]; then CODE="$PHASE1_OTP"; fi
fi
if [ -z "$CODE" ]; then
  exit 1
fi
echo ">>> [2] 验证码登录 (code=$CODE)"
SESSION=$(curl -sf -X POST "$BASE/api/auth/otp/verify" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"code\":\"$CODE\",\"portal\":\"admin\"}")
TOKEN=$(echo "$SESSION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_token',''))")
if [ -z "$TOKEN" ]; then
  echo "✗ 登录失败: $SESSION"
  exit 1
fi
echo "✓ session_token 获取成功"
echo ""

HDR=(-H "X-Session-Token: $TOKEN" -H "Content-Type: application/json")

echo ">>> [3] Admin summary"
curl -sf "${HDR[@]}" "$BASE/api/admin/summary" | python3 -m json.tool | head -20
echo ""

echo ">>> [4] 创建订单"
ORDER=$(curl -sf -X POST "${HDR[@]}" "$BASE/api/orders" \
  -d '{"customer_name":"Live Test Buyer","country_iso":"CO","customer_email":"buyer@example.com"}')
OID=$(echo "$ORDER" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")
echo "✓ order_id=$OID"
echo ""

echo ">>> [5] 创建分享链接"
SHARE=$(curl -sf -X POST "${HDR[@]}" "$BASE/api/share/links" \
  -d "{\"resource_type\":\"order\",\"resource_id\":\"$OID\",\"ttl_days\":7}")
echo "$SHARE" | python3 -m json.tool
SHARE_URL=$(echo "$SHARE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('url',''))")
echo ""

echo ">>> [5b] 确认订单"
curl -sf -X PATCH "${HDR[@]}" "$BASE/api/orders/$OID" \
  -d '{"status":"confirmed"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('status:', d.get('status'))"
echo ""

if [ -n "$SHARE_URL" ]; then
  echo ">>> [6] 公开访问分享"
  curl -sf "$SHARE_URL" | head -3
  TOKEN_PATH="${SHARE_URL##*/s/}"
  curl -sf "$BASE/api/share/$TOKEN_PATH" | python3 -c "import sys,json; d=json.load(sys.stdin); print('valid:', d.get('valid'))"
fi

echo ""
echo "=== Phase 1 Live 完成 ==="
