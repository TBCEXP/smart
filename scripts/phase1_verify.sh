#!/usr/bin/env bash
# Phase 1 员工业务验收 — 工厂/品类/订单/ERP 桥接
# 用法: bash scripts/phase1_verify.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
PASS=0
FAIL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "============================================"
echo "  SMART CRM Phase 1 Verification"
echo "  Base: $BASE"
echo "============================================"
echo ""

echo ">>> [1] 品类树"
if curl -sf "$BASE/api/catalog/tree" | grep -q 'bakeware'; then
  ok "GET /api/catalog/tree"
else
  fail "GET /api/catalog/tree"
fi

echo ">>> [2] 工厂主数据"
if curl -sf "$BASE/api/factories" | grep -q 'F-SD-01'; then
  ok "GET /api/factories (seed)"
else
  fail "GET /api/factories"
fi

echo ">>> [3] 线索列表"
if curl -sf "$BASE/api/leads?limit=5" | grep -q '"leads"'; then
  ok "GET /api/leads"
else
  fail "GET /api/leads"
fi

echo ">>> [4] 飞书只读 (mock)"
if curl -sf "$BASE/api/feishu/records/mock-rec-001" | grep -q 'record_id'; then
  ok "GET /api/feishu/records/{id}"
else
  fail "GET /api/feishu/records/{id}"
fi

echo ">>> [5] 员工后台页面"
if curl -sf "$BASE/admin/dashboard" | grep -q '员工后台'; then
  ok "GET /admin/dashboard"
else
  fail "GET /admin/dashboard"
fi

echo ">>> [6] Exa 查询预览"
if curl -sf "$BASE/api/exa/preview-query?category_l3=flatware&country_iso=CO" | grep -q 'semantic_query'; then
  ok "GET /api/exa/preview-query"
else
  fail "GET /api/exa/preview-query"
fi

echo ""
echo ">>> [7] 可选：登录后写操作（需 OTP）"
OTP_BODY=$(curl -sf -X POST "$BASE/api/auth/otp/send" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","portal":"admin"}' || echo '{}')
if echo "$OTP_BODY" | grep -q 'sent\|ok\|OTP'; then
  ok "POST /api/auth/otp/send (admin)"
  echo "  提示: 配置 session_token 后可测 POST /api/orders 与 ERP 桥接"
else
  fail "POST /api/auth/otp/send"
fi

echo ""
echo "=== Phase 1: ${PASS} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
