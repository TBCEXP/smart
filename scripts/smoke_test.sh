#!/usr/bin/env bash
# SMART CRM 端到端 smoke 测试（verification skill 对应脚本）
# 用法: bash scripts/smoke_test.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
PASS=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== SMART CRM Smoke Test ==="
echo "Base: $BASE"
echo ""

# 1. Health
echo "[1] 基础"
if curl -sf "$BASE/api/health" | grep -q '"status":"ok"'; then
  ok "GET /api/health"
else
  fail "GET /api/health"
fi

# 2. Integrations status
if curl -sf "$BASE/api/integrations/status" | grep -q 'configured_count'; then
  ok "GET /api/integrations/status"
else
  fail "GET /api/integrations/status"
fi

# 3. Geo config
if curl -sf "$BASE/api/geo/config" | grep -q 'MX'; then
  ok "GET /api/geo/config (MX present)"
else
  fail "GET /api/geo/config"
fi

# 4. Brainstorm generate
BS=$(curl -sf -X POST "$BASE/api/brainstorm/generate" \
  -H "Content-Type: application/json" \
  -d '{"country_iso":"MX","city":"CDMX","category_l3":"bakeware","language":"es"}')
if echo "$BS" | grep -q 'session_id'; then
  ok "POST /api/brainstorm/generate"
  SID=$(echo "$BS" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])" 2>/dev/null || echo "")
else
  fail "POST /api/brainstorm/generate"
  SID=""
fi

# 5. Brainstorm action
if [ -n "$SID" ]; then
  if curl -sf -X POST "$BASE/api/brainstorm/actions" \
    -H "Content-Type: application/json" \
    -d "{\"session_id\":\"$SID\",\"action_type\":\"similar_search\",\"payload\":{}}" | grep -q 'done'; then
    ok "POST /api/brainstorm/actions"
  else
    fail "POST /api/brainstorm/actions"
  fi
fi

# 6. Run batch (mock mode OK)
RUN=$(curl -sf -X POST "$BASE/api/run" \
  -H "Content-Type: application/json" \
  -d '{"keyword":"mayorista moldes repostería CDMX","industry":"跨境电商","count":2,"country_iso":"MX","city":"CDMX","category_l3":"bakeware"}')
if echo "$RUN" | grep -q 'batch_id'; then
  ok "POST /api/run"
  BID=$(echo "$RUN" | python3 -c "import sys,json; print(json.load(sys.stdin)['batch_id'])" 2>/dev/null || echo "")
else
  fail "POST /api/run"
  BID=""
fi

# 7. Wait for batch + check leads
if [ -n "$BID" ]; then
  sleep 6
  BATCH=$(curl -sf "$BASE/api/batch/$BID")
  if echo "$BATCH" | grep -q 'leads'; then
    COUNT=$(echo "$BATCH" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('leads',[])))" 2>/dev/null || echo 0)
    if [ "$COUNT" -gt 0 ]; then
      ok "Batch produced $COUNT lead(s)"
    else
      fail "Batch has 0 leads"
    fi
  else
    fail "GET /api/batch/$BID"
  fi
fi

# 8. KB search
if curl -sf "$BASE/api/kb/search?q=bakeware%20Mexico" | grep -q 'results'; then
  ok "GET /api/kb/search"
else
  fail "GET /api/kb/search"
fi

# 9. Auth OTP send
if curl -sf -X POST "$BASE/api/auth/otp/send" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","portal":"admin"}' | grep -q 'sent'; then
  ok "POST /api/auth/otp/send"
else
  fail "POST /api/auth/otp/send"
fi

# 10. Market anchors
if curl -sf "$BASE/api/market/anchors?country_iso=MX" | grep -q 'Vasconia'; then
  ok "GET /api/market/anchors (MX)"
else
  fail "GET /api/market/anchors"
fi

# 11. Content Studio (Tab8)
if curl -sf "$BASE/api/content/types" | grep -q 'seo_pack'; then
  ok "GET /api/content/types"
else
  fail "GET /api/content/types"
fi
CT=$(curl -sf -X POST "$BASE/api/content/generate" \
  -H "Content-Type: application/json" \
  -d '{"content_type":"seo_pack","product_name":"Test product SEO","category_l3":"bakeware","language":"es"}')
if echo "$CT" | grep -q 'slug'; then
  ok "POST /api/content/generate"
else
  fail "POST /api/content/generate"
fi
CTB=$(curl -sf -X POST "$BASE/api/content/generate-batch" \
  -H "Content-Type: application/json" \
  -d '{"content_type":"seo_pack","product_name":"Batch test product","category_l3":"bakeware","languages":["es","en"]}')
if echo "$CTB" | grep -q 'batch_id' && echo "$CTB" | grep -q '"language":"es"' && echo "$CTB" | grep -q '"language":"en"'; then
  ok "POST /api/content/generate-batch"
else
  fail "POST /api/content/generate-batch"
fi

echo ""
echo "=== Smoke: ${PASS} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
