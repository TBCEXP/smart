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
if curl -sf "$BASE/api/health" | grep -qE '"version":"2\.[01]'; then
  ok "GET /api/health (v2.x)"
else
  fail "GET /api/health (v2.x)"
fi
if curl -sf "$BASE/docs/feishu-fields" | grep -q '飞书多维表格'; then
  ok "GET /docs/feishu-fields"
else
  fail "GET /docs/feishu-fields"
fi
if curl -sf "$BASE/api/kb/status" | grep -q 'search_engine'; then
  ok "GET /api/kb/status"
else
  fail "GET /api/kb/status"
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

# 4. Exa query preview + leads list
if curl -sf "$BASE/api/exa/preview-query?category_l3=bakeware&country_iso=MX&city=CDMX" | grep -q 'resolved_query'; then
  ok "GET /api/exa/preview-query"
else
  fail "GET /api/exa/preview-query"
fi
if curl -sf "$BASE/api/leads?limit=5" | grep -q '"leads"'; then
  ok "GET /api/leads"
else
  fail "GET /api/leads"
fi
if curl -sf "$BASE/admin/leads" | grep -q '员工后台'; then
  ok "GET /admin/leads (dashboard)"
else
  fail "GET /admin/leads (dashboard)"
fi
if curl -sf "$BASE/api/catalog/tree" | grep -q 'bakeware'; then
  ok "GET /api/catalog/tree"
else
  fail "GET /api/catalog/tree"
fi
if curl -sf "$BASE/api/factories" | grep -q 'F-SD-01'; then
  ok "GET /api/factories"
else
  fail "GET /api/factories"
fi
if curl -sf "$BASE/api/feishu/records/mock-test" | grep -q 'record_id'; then
  ok "GET /api/feishu/records/{id}"
else
  fail "GET /api/feishu/records/{id}"
fi
if curl -sf "$BASE/portal/dashboard" | grep -q '客户门户'; then
  ok "GET /portal/dashboard"
else
  fail "GET /portal/dashboard"
fi
if curl -sf "$BASE/api/share/invalid-token-test" | grep -q '"valid":false'; then
  ok "GET /api/share/{token} (invalid)"
else
  fail "GET /api/share/{token}"
fi
if curl -sf "$BASE/api/catalog/documents" | grep -q '商用锅具\|title'; then
  ok "GET /api/catalog/documents"
else
  fail "GET /api/catalog/documents"
fi

# 5. Brainstorm generate
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

# 6. Run batch (mock mode OK) — unique keyword avoids duplicate-domain skip
UNIQ_KW="mayorista moldes repostería CDMX smoke-$(date +%s)"
RUN=$(curl -sf -X POST "$BASE/api/run" \
  -H "Content-Type: application/json" \
  -d "{\"keyword\":\"$UNIQ_KW\",\"industry\":\"跨境电商\",\"count\":2,\"country_iso\":\"MX\",\"city\":\"CDMX\",\"category_l3\":\"bakeware\"}")
if echo "$RUN" | grep -q 'batch_id'; then
  ok "POST /api/run"
  BID=$(echo "$RUN" | python3 -c "import sys,json; print(json.load(sys.stdin)['batch_id'])" 2>/dev/null || echo "")
  if [ -n "$BID" ]; then
    curl -sf -N --max-time 45 "$BASE/api/stream/$BID" > /dev/null 2>&1 || true
  fi
else
  fail "POST /api/run"
  BID=""
fi

# 7. Check batch result
if [ -n "$BID" ]; then
  BATCH=$(curl -sf "$BASE/api/batch/$BID")
  if echo "$BATCH" | grep -q 'leads'; then
    COUNT=$(echo "$BATCH" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('leads',[])))" 2>/dev/null || echo 0)
    STATUS=$(echo "$BATCH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('batch',{}).get('status',''))" 2>/dev/null || echo "")
    if [ "$COUNT" -gt 0 ]; then
      ok "Batch produced $COUNT lead(s)"
    elif [ "$STATUS" = "completed" ]; then
      ok "Batch completed (mock/duplicate skip OK)"
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

# 12. MX Pilot (Phase 1.5)
if curl -sf "$BASE/api/pilot/mx/status" | grep -q 'phase'; then
  ok "GET /api/pilot/mx/status"
else
  fail "GET /api/pilot/mx/status"
fi
PILOT=$(curl -sf -X POST "$BASE/api/pilot/mx/start" \
  -H "Content-Type: application/json" \
  -d '{"country_iso":"MX","category_l3":"bakeware","anchor_limit":1,"enqueue_track_a":true}')
if echo "$PILOT" | grep -q 'pilot_id' && echo "$PILOT" | grep -q 'session_id'; then
  ok "POST /api/pilot/mx/start"
else
  fail "POST /api/pilot/mx/start"
fi

# 13. CO Pilot
if curl -sf "$BASE/api/pilot/co/status" | grep -q 'CO'; then
  ok "GET /api/pilot/co/status"
else
  fail "GET /api/pilot/co/status"
fi
CO_PILOT=$(curl -sf -X POST "$BASE/api/pilot/co/start" \
  -H "Content-Type: application/json" \
  -d '{"country_iso":"CO","city":"Bogotá","category_l3":"bakeware","anchor_limit":1,"enqueue_track_a":true}')
if echo "$CO_PILOT" | grep -q 'pilot_id'; then
  ok "POST /api/pilot/co/start"
else
  fail "POST /api/pilot/co/start"
fi

# 14. Run due schedules
DUE=$(curl -sf -X POST "$BASE/api/schedules/run-due?limit=1&count_per_task=2")
if echo "$DUE" | grep -q 'queued'; then
  ok "POST /api/schedules/run-due"
else
  fail "POST /api/schedules/run-due"
fi

# 15. Integrations probe + readiness
if curl -sf -X POST "$BASE/api/integrations/probe" | grep -q 'probes'; then
  ok "POST /api/integrations/probe"
else
  fail "POST /api/integrations/probe"
fi
if curl -sf "$BASE/api/system/readiness" | grep -q 'phase3_files_seeded'; then
  ok "GET /api/system/readiness (phase3 checklist)"
else
  fail "GET /api/system/readiness (phase3 checklist)"
fi
if curl -sf "$BASE/api/files/transfers" | grep -q 'download_url'; then
  ok "GET /api/files/transfers"
else
  fail "GET /api/files/transfers"
fi
if curl -sf "$BASE/api/files/tus/status" | grep -q '"protocol"'; then
  ok "GET /api/files/tus/status"
else
  fail "GET /api/files/tus/status"
fi
if curl -sf "$BASE/api/bridge/tbcexp/field-map" | grep -q '"version"'; then
  ok "GET /api/bridge/tbcexp/field-map"
else
  fail "GET /api/bridge/tbcexp/field-map"
fi
if curl -sf "$BASE/api/prepress/reviews" | grep -q 'barcode_expected'; then
  ok "GET /api/prepress/reviews"
else
  fail "GET /api/prepress/reviews"
fi
if curl -sf "$BASE/api/prepress/ocr/status" | grep -q '"available"'; then
  ok "GET /api/prepress/ocr/status"
else
  fail "GET /api/prepress/ocr/status"
fi
if curl -sf "$BASE/api/prepress/barcode/scan/status" | grep -q '"available"'; then
  ok "GET /api/prepress/barcode/scan/status"
else
  fail "GET /api/prepress/barcode/scan/status"
fi
if curl -sf "$BASE/api/inspections/production" | grep -q 'approved_image'; then
  ok "GET /api/inspections/production"
else
  fail "GET /api/inspections/production"
fi
if curl -sf "$BASE/api/system/handoff-report" | grep -q 'SMART CRM 交接报告'; then
  ok "GET /api/system/handoff-report"
else
  fail "GET /api/system/handoff-report"
fi
if curl -sf "$BASE/api/pilot/report" | grep -q 'milestones'; then
  ok "GET /api/pilot/report"
else
  fail "GET /api/pilot/report"
fi
if curl -sf "$BASE/api/pilot/export?format=md" | grep -q 'Phase 1.5'; then
  ok "GET /api/pilot/export (markdown)"
else
  fail "GET /api/pilot/export (markdown)"
fi

# 16. Stats overview + outreach (Tab9 / 1.5.5)
if curl -sf "$BASE/api/stats/overview" | grep -q '1_5_5_whatsapp_5'; then
  ok "GET /api/stats/overview (milestones)"
else
  fail "GET /api/stats/overview (milestones)"
fi
OUT=$(curl -sf -X POST "$BASE/api/outreach/log" \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Smoke Test Co","channel":"whatsapp","country_iso":"MX","message_preview":"Hola smoke test"}')
if echo "$OUT" | grep -q '"status":"logged"'; then
  ok "POST /api/outreach/log"
  LOG_ID=$(echo "$OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
else
  fail "POST /api/outreach/log"
  LOG_ID=""
fi
if curl -sf "$BASE/api/outreach/logs" | grep -q 'Smoke Test Co'; then
  ok "GET /api/outreach/logs"
else
  fail "GET /api/outreach/logs"
fi
if [ -n "$LOG_ID" ]; then
  if curl -sf -X PATCH "$BASE/api/outreach/logs/$LOG_ID" \
    -H "Content-Type: application/json" \
    -d '{"replied":true,"reply_notes":"smoke reply"}' | grep -q '"replied":true'; then
    ok "PATCH /api/outreach/logs/{id}"
  else
    fail "PATCH /api/outreach/logs/{id}"
  fi
fi
if curl -sf "$BASE/api/outreach/stats" | grep -q 'whatsapp_sent'; then
  ok "GET /api/outreach/stats"
else
  fail "GET /api/outreach/stats"
fi

echo ""
echo "=== Smoke: ${PASS} passed, ${FAIL} failed ==="
[ "$FAIL" -eq 0 ]
