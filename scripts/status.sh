#!/usr/bin/env bash
# 快速查看 SMART CRM 运行状态（VPS / 本地均可）
# 用法: bash scripts/status.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"

echo "SMART CRM Status — $BASE"
echo ""

HEALTH=$(curl -sf "$BASE/api/health" 2>/dev/null || echo '{"status":"down"}')
echo "Health: $(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','down'))" 2>/dev/null || echo down)"

INT=$(curl -sf "$BASE/api/integrations/status" 2>/dev/null || echo '{}')
echo "API Keys: $(echo "$INT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('configured_count',0)}/{d.get('total',8)} live-ready={d.get('production_ready',False)}\")" 2>/dev/null || echo N/A)"

READY=$(curl -sf "$BASE/api/system/readiness" 2>/dev/null || echo '{}')
echo "Due schedules: $(echo "$READY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('due_schedules',0))" 2>/dev/null || echo 0)"

REPORT=$(curl -sf "$BASE/api/pilot/report" 2>/dev/null || echo '{}')
echo "Pilot MX intel: $(echo "$REPORT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('countries',{}).get('MX',{}).get('totals',{}).get('intel_reports',0))" 2>/dev/null || echo 0)"
echo "Pilot CO intel: $(echo "$REPORT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('countries',{}).get('CO',{}).get('totals',{}).get('intel_reports',0))" 2>/dev/null || echo 0)"

echo ""
echo "详细: curl -s $BASE/api/system/readiness | python3 -m json.tool"
