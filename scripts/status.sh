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
echo "Phase1: $(echo "$READY" | python3 -c "import sys,json; b=json.load(sys.stdin).get('business',{}).get('phase1',{}); print(f\"factories={b.get('factories',0)} orders={b.get('orders',0)} leads={b.get('leads',0)}\")" 2>/dev/null || echo N/A)"
echo "Phase2: $(echo "$READY" | python3 -c "import sys,json; b=json.load(sys.stdin).get('business',{}).get('phase2',{}); print(f\"catalogs={b.get('catalog_documents',0)} shares={b.get('share_links',0)} r2={b.get('r2_configured')}\")" 2>/dev/null || echo N/A)"
echo "Phase3: $(echo "$READY" | python3 -c "import sys,json; b=json.load(sys.stdin).get('business',{}).get('phase3',{}); print(f\"files={b.get('file_transfers',0)} notify={b.get('notify_service')}\")" 2>/dev/null || echo N/A)"

REPORT=$(curl -sf "$BASE/api/pilot/report" 2>/dev/null || echo '{}')
echo "Pilot MX intel: $(echo "$REPORT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('countries',{}).get('MX',{}).get('totals',{}).get('intel_reports',0))" 2>/dev/null || echo 0)"
echo "Pilot CO intel: $(echo "$REPORT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('countries',{}).get('CO',{}).get('totals',{}).get('intel_reports',0))" 2>/dev/null || echo 0)"

STATS=$(curl -sf "$BASE/api/stats/overview" 2>/dev/null || echo '{}')
echo "Feishu synced: $(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('leads',{}).get('feishu_synced',0))" 2>/dev/null || echo 0)"
echo "WhatsApp sent: $(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('outreach',{}).get('whatsapp_sent',0))" 2>/dev/null || echo 0)"
echo "Track C match: $(echo "$STATS" | python3 -c "import sys,json; d=json.load(sys.stdin).get('track_c',{}); print(f\"{d.get('domain_matched',0)}/{d.get('imported',0)} ({int(d.get('match_rate',0)*100)}%)\")" 2>/dev/null || echo N/A)"

MILE=$(echo "$STATS" | python3 -c "
import sys, json
m = json.load(sys.stdin).get('milestones', {})
flags = []
for k, label in [
    ('1_5_4_feishu_30', '1.5.4'),
    ('1_5_5_whatsapp_5', '1.5.5'),
    ('1_5_6_track_c', '1.5.6'),
    ('1_5_7_kb_recall', '1.5.7'),
]:
    flags.append(f\"{label}:{'✓' if m.get(k) else '○'}\")
print(' | '.join(flags))
" 2>/dev/null || echo "milestones: N/A")
echo "Milestones: $MILE"

echo ""
echo "详细: curl -s $BASE/api/stats/overview | python3 -m json.tool"
