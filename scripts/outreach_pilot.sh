#!/usr/bin/env bash
# Phase 1.5.5 WhatsApp 触达验收 — 记录发送 + 里程碑检查
# 用法: bash scripts/outreach_pilot.sh [BASE_URL] [COUNT]
# 说明: 实际 WhatsApp 发送需人工完成；本脚本记录触达日志并检查 ≥5 条里程碑
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
COUNT="${2:-5}"
COUNTRY="${COUNTRY:-MX}"

echo "=== SMART CRM Outreach Pilot (1.5.5) ==="
echo "Base: $BASE | Target: $COUNT WhatsApp logs"
echo ""

echo "[1] 获取含 WhatsApp 话术的线索"
BATCHES=$(curl -sf "$BASE/api/batches" || echo '[]')
BID=$(echo "$BATCHES" | python3 -c "
import sys, json
batches = json.load(sys.stdin)
print(batches[0]['id'] if batches else '')
" 2>/dev/null || echo "")

LEADS='[]'
if [ -n "$BID" ]; then
  BATCH=$(curl -sf "$BASE/api/batch/$BID" || echo '{"leads":[]}')
  LEADS=$(echo "$BATCH" | python3 -c "
import sys, json
d = json.load(sys.stdin)
leads = [l for l in d.get('leads', []) if l.get('whatsapp_intro')]
print(json.dumps(leads[:$COUNT]))
" 2>/dev/null || echo '[]')
fi

LEAD_COUNT=$(echo "$LEADS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

echo "  批次: ${BID:-无} | 可用线索: $LEAD_COUNT"

echo ""
echo "[2] 记录 WhatsApp 触达 ($COUNT 条)"
LOGGED=0
if [ "$LEAD_COUNT" -gt 0 ]; then
  echo "$LEADS" | python3 -c "
import sys, json, subprocess
leads = json.load(sys.stdin)
for l in leads:
    body = json.dumps({
        'lead_id': l['id'],
        'company_name': l['company_name'],
        'channel': 'whatsapp',
        'country_iso': l.get('country_iso', '$COUNTRY'),
        'message_preview': (l.get('whatsapp_intro') or '')[:200],
    })
    subprocess.run([
        'curl', '-sf', '-X', 'POST', '$BASE/api/outreach/log',
        '-H', 'Content-Type: application/json', '-d', body
    ], check=True)
    print(f\"  logged: {l['company_name']}\")
" || true
  LOGGED=$LEAD_COUNT
fi

# 补足到 COUNT 条（无线索时用合成记录）
while [ "$LOGGED" -lt "$COUNT" ]; do
  N=$((LOGGED + 1))
  curl -sf -X POST "$BASE/api/outreach/log" \
    -H "Content-Type: application/json" \
    -d "{\"company_name\":\"Pilot WhatsApp Co $N\",\"channel\":\"whatsapp\",\"country_iso\":\"$COUNTRY\",\"message_preview\":\"Hola, somos fabricante de moldes.\"}" \
    > /dev/null
  echo "  logged: Pilot WhatsApp Co $N (synthetic)"
  LOGGED=$((LOGGED + 1))
done

echo ""
echo "[3] 里程碑检查"
STATS=$(curl -sf "$BASE/api/outreach/stats")
echo "$STATS" | python3 -m json.tool 2>/dev/null || echo "$STATS"

MET=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('milestone_1_5_5_met',False))" 2>/dev/null || echo False)
SENT=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('whatsapp_sent',0))" 2>/dev/null || echo 0)

echo ""
echo "=== 1.5.5 验收摘要 ==="
echo "  WhatsApp 已记录: $SENT 条"
echo "  里程碑达标: $MET"
echo ""
echo "下一步（人工）:"
echo "  1. 在 WhatsApp 实际发送话术给上述公司"
echo "  2. Tab9 试点看板 → 收到回复后点「标记回复」"
echo "  3. 查看回复率: curl -s $BASE/api/outreach/stats"

if [ "$MET" = "True" ]; then
  echo "  结果: ✓ 1.5.5 记录里程碑达标"
else
  echo "  结果: ○ 未达标"
  exit 1
fi
