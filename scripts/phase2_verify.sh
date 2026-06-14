#!/usr/bin/env bash
# Phase 2 验收 — 目录元数据、门户、分享、Apollo 补充
# 用法: bash scripts/phase2_verify.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
PASS=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== Phase 2 Verification ==="
echo "Base: $BASE"
echo ""

if curl -sf "$BASE/api/catalog/documents" | grep -q 'download_url'; then
  ok "GET /api/catalog/documents (download_url field)"
else
  fail "GET /api/catalog/documents (download_url field)"
fi

if curl -sf "$BASE/api/catalog/documents" | grep -q '商用锅具'; then
  ok "GET /api/catalog/documents (seed)"
else
  fail "GET /api/catalog/documents"
fi

if curl -sf "$BASE/api/bridge/tbcexp/status/$(curl -sf "$BASE/api/leads?limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['leads'][0]['id'] if d.get('leads') else '')" 2>/dev/null || echo 'x')" 2>/dev/null | grep -q 'tbcexp_synced'; then
  ok "GET /api/bridge/tbcexp/status/{id}"
else
  # no leads yet still ok if endpoint works with fake id returning 404 - check with any lead
  LEAD=$(curl -sf "$BASE/api/leads?limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('leads') or [{}])[0].get('id',''))" 2>/dev/null || echo "")
  if [ -n "$LEAD" ] && curl -sf "$BASE/api/bridge/tbcexp/status/$LEAD" | grep -q 'erp_configured'; then
    ok "GET /api/bridge/tbcexp/status/{id}"
  else
    fail "GET /api/bridge/tbcexp/status/{id}"
  fi
fi

LEAD=$(curl -sf "$BASE/api/leads?limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('leads') or [{}])[0].get('id',''))" 2>/dev/null || echo "")
if [ -n "$LEAD" ] && curl -sf -X POST "$BASE/api/leads/$LEAD/enrich-contact" | grep -q 'contact_email'; then
  ok "POST /api/leads/{id}/enrich-contact"
else
  fail "POST /api/leads/{id}/enrich-contact"
fi

if curl -sf "$BASE/admin/dashboard" | grep -q '工厂目录'; then
  ok "GET /admin/dashboard (catalog documents tab)"
else
  fail "GET /admin/dashboard (catalog documents tab)"
fi

if curl -sf "$BASE/portal/dashboard" | grep -q 'order-detail'; then
  ok "GET /portal/dashboard (order detail panel)"
else
  fail "GET /portal/dashboard (order detail panel)"
fi

if curl -sf "$BASE/portal/dashboard" | grep -q '报价单'; then
  ok "GET /portal/dashboard (quotes tab)"
else
  fail "GET /portal/dashboard (quotes tab)"
fi

if curl -sf "$BASE/api/catalog/documents?doc_type=quote" | grep -q 'FOB 报价'; then
  ok "GET /api/catalog/documents?doc_type=quote"
else
  fail "GET /api/catalog/documents?doc_type=quote"
fi

echo ""
echo "=== Phase 2: ${PASS} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
