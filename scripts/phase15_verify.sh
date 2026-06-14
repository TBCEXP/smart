#!/usr/bin/env bash
# Phase 1.5 全量验收 — smoke + 1.5.5/6/7 子脚本 + 里程碑汇总
# 用法: bash scripts/phase15_verify.sh [BASE_URL] [--quick]
set -euo pipefail

BASE="http://127.0.0.1:8000"
QUICK=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

for arg in "$@"; do
  case "$arg" in
    http*) BASE="$arg" ;;
    --quick) QUICK=1 ;;
  esac
done

TRACKC_ROWS=50
[ "$QUICK" -eq 1 ] && TRACKC_ROWS=10

echo "============================================"
echo "  SMART CRM Phase 1.5 Full Verification"
echo "  Base: $BASE | Quick: $([ "$QUICK" -eq 1 ] && echo yes || echo no)"
echo "============================================"
echo ""

echo ">>> [A] Smoke 测试 (25 项)"
bash "$SCRIPT_DIR/smoke_test.sh" "$BASE"
echo ""

echo ">>> [B] 1.5.5 WhatsApp 触达"
bash "$SCRIPT_DIR/outreach_pilot.sh" "$BASE" 5
echo ""

echo ">>> [C] 1.5.7 知识库检索"
bash "$SCRIPT_DIR/kb_pilot.sh" "$BASE"
echo ""

echo ">>> [D] 1.5.6 Track C 海关导入"
bash "$SCRIPT_DIR/trackc_pilot.sh" "$BASE" "$TRACKC_ROWS" --with-website
echo ""

echo ">>> [E] 里程碑汇总"
STATS=$(curl -sf "$BASE/api/stats/overview")
echo "$STATS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
m = d.get('milestones', {})
labels = {
    '1_5_4_feishu_30': '1.5.4 飞书≥30',
    '1_5_5_whatsapp_5': '1.5.5 WhatsApp≥5',
    '1_5_6_track_c': '1.5.6 Track C 50条>60%',
    '1_5_7_kb_recall': '1.5.7 KB召回',
}
print('里程碑:')
for k, label in labels.items():
    mark = '✓' if m.get(k) else '○'
    print(f'  {mark} {label}')
print()
print(f\"  飞书同步: {m.get('feishu_synced', 0)}\")
print(f\"  WhatsApp: {m.get('whatsapp_sent', 0)}\")
print(f\"  Track C:  {m.get('track_c_imported', 0)} 条, 匹配率 {int(m.get('track_c_match_rate', 0)*100)}%\")
print(f\"  KB 召回:  {m.get('kb_results', 0)} 条\")
"

echo ""
bash "$SCRIPT_DIR/status.sh" "$BASE"
echo ""
echo "============================================"
echo "  Phase 1.5 验收完成"
echo "  生产环境请配置 API Key 后:"
echo "    bash scripts/pilot_live.sh $BASE"
echo "    bash scripts/trackc_pilot.sh $BASE 50 --no-website"
echo "============================================"
