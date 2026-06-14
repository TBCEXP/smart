#!/usr/bin/env bash
# 路线图 Phase 0–5 终验收 — 合并 pre_merge + 状态快照
# 用法: bash scripts/final_acceptance.sh [BASE_URL]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE="${1:-http://127.0.0.1:8000}"

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM 路线图终验收 (Phase 0–5)            ║"
echo "╚══════════════════════════════════════════════════╝"
echo "Base: $BASE"
echo ""

bash "$SCRIPT_DIR/pre_merge_verify.sh" "$BASE"

echo ""
echo ">>> 业务快照"
bash "$SCRIPT_DIR/status.sh" "$BASE"

echo ""
echo ">>> 交接报告（预览）"
curl -sf "$BASE/api/system/handoff-report" | head -40

echo ""
echo "=== 路线图 Phase 0–5 验收完成 ==="
echo "生产部署: bash scripts/prod_onboard.sh $BASE --full"
