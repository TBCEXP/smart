#!/usr/bin/env bash
# 导出完整验收包 — 试点报告 + 交接报告 + readiness JSON
# 用法: bash scripts/acceptance_report.sh [BASE_URL] [OUTPUT_PREFIX]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
PREFIX="${2:-acceptance-$(date +%Y%m%d-%H%M)}"
PILOT="${PREFIX}-pilot.md"
HANDOFF="${PREFIX}-handoff.md"
READY="${PREFIX}-readiness.json"

echo "=== SMART CRM 验收报告导出 ==="
echo "Base: $BASE"
echo "输出前缀: $PREFIX"
echo ""

curl -sf "$BASE/api/pilot/export?format=md" -o "$PILOT"
echo "✓ 试点报告: $PILOT"

curl -sf "$BASE/api/system/handoff-report" -o "$HANDOFF"
echo "✓ 交接报告: $HANDOFF"

curl -sf "$BASE/api/system/readiness" -o "$READY"
echo "✓ 就绪检查: $READY"

echo ""
python3 -c "
import json
with open('$READY') as f:
    d = json.load(f)
c = d.get('checklist', {})
b = d.get('business', {})
print('版本:', d.get('integrations', {}).get('note', 'ok'))
print('production_ready:', d.get('production_ready'))
blockers = d.get('production_blockers', {})
print('blocking_count:', blockers.get('blocking_count'))
print('live_ready:', blockers.get('live_ready'))
print('checklist:', json.dumps(c, ensure_ascii=False))
for k in ('phase1','phase2','phase3','phase4','phase5'):
    if k in b:
        print(k + ':', b[k])
"

echo ""
echo "文件列表:"
echo "  $PILOT"
echo "  $HANDOFF"
echo "  $READY"
echo ""
head -12 "$HANDOFF"
echo "..."
echo ""
echo "终验收: bash scripts/go_live.sh $BASE"
