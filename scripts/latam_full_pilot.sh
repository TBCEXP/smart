#!/usr/bin/env bash
# Phase 1.5 LATAM 全试点 — MX + CO Track B/Brainstorm/Track A 入队 + 验收汇总
# 用法: bash scripts/latam_full_pilot.sh [BASE_URL] [--run-due N]
set -euo pipefail

BASE="http://127.0.0.1:8000"
RUN_DUE=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

for arg in "$@"; do
  case "$arg" in
    http*) BASE="$arg" ;;
    --run-due) RUN_DUE=1 ;;
    --run-due=*) RUN_DUE="${arg#--run-due=}" ;;
  esac
done

echo "============================================"
echo "  SMART CRM LATAM Full Pilot (MX + CO)"
echo "  Base: $BASE"
echo "============================================"
echo ""

echo ">>> [1] 墨西哥试点"
bash "$SCRIPT_DIR/mx_pilot.sh" "$BASE"
echo ""

echo ">>> [2] 哥伦比亚试点"
bash "$SCRIPT_DIR/co_pilot.sh" "$BASE"
echo ""

if [ "$RUN_DUE" != "0" ]; then
  LIMIT="${RUN_DUE:-2}"
  echo ">>> [3] 执行到期 Track A 任务 (limit=$LIMIT)"
  DUE=$(curl -sf -X POST "$BASE/api/schedules/run-due?limit=$LIMIT&count_per_task=5" || echo '{}')
  echo "$DUE" | python3 -m json.tool 2>/dev/null || echo "$DUE"
  echo ""
fi

echo ">>> [4] 试点报告摘要"
REPORT=$(curl -sf "$BASE/api/pilot/report")
echo "$REPORT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
mx = d.get('mx', {})
co = d.get('co', {})
print('MX:', 'started' if mx.get('started') else 'not started', '| session:', mx.get('session_id', '-'))
print('CO:', 'started' if co.get('started') else 'not started', '| session:', co.get('session_id', '-'))
m = d.get('milestones', {})
for k, label in [
    ('1_5_4_feishu_30', '1.5.4 飞书≥30'),
    ('1_5_5_whatsapp_5', '1.5.5 WhatsApp≥5'),
    ('1_5_6_track_c', '1.5.6 Track C'),
    ('1_5_7_kb_recall', '1.5.7 KB召回'),
]:
    mark = '✓' if m.get(k) else '○'
    print(f'  {mark} {label}')
" 2>/dev/null || echo "$REPORT"
echo ""

echo ">>> [5] 导出 Markdown 验收报告"
OUT="latam-pilot-$(date +%Y%m%d-%H%M).md"
bash "$SCRIPT_DIR/acceptance_report.sh" "$BASE" "$OUT"
echo ""

echo "============================================"
echo "  LATAM 全试点完成"
echo "  下一步:"
echo "    bash scripts/phase15_verify.sh $BASE --quick"
echo "    bash scripts/pilot_live.sh $BASE        # 真实 API + 飞书"
echo "============================================"
