#!/usr/bin/env bash
# 导出 Phase 1.5 验收报告（Markdown / JSON）
# 用法: bash scripts/acceptance_report.sh [BASE_URL] [OUTPUT.md]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
OUT="${2:-pilot-report-$(date +%Y%m%d-%H%M).md}"

echo "=== SMART CRM 验收报告导出 ==="
echo "Base: $BASE"
echo "输出: $OUT"
echo ""

curl -sf "$BASE/api/pilot/export?format=md" -o "$OUT"
echo "✓ Markdown 报告已保存: $OUT"
echo ""
head -30 "$OUT"
echo ""
echo "JSON 版本: curl -s $BASE/api/pilot/export > pilot-report.json"
