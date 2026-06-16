#!/usr/bin/env bash
# 运行全部自动化测试（开发 / CI / 部署后）
# 用法: bash scripts/run_all_tests.sh [BASE_URL] [--full]
set -euo pipefail

BASE="http://127.0.0.1:8000"
FULL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

for arg in "$@"; do
  case "$arg" in
    http*) BASE="$arg" ;;
    --full) FULL=1 ;;
  esac
done

echo "=== SMART CRM 全量测试 ==="
echo "Base: $BASE"
echo ""

bash "$SCRIPT_DIR/smoke_test.sh" "$BASE"

if [ "$FULL" -eq 1 ]; then
  bash "$SCRIPT_DIR/phase15_verify.sh" "$BASE"
else
  bash "$SCRIPT_DIR/phase15_verify.sh" "$BASE" --quick
fi

echo ""
echo ">>> Phase 1 员工业务"
bash "$SCRIPT_DIR/phase1_verify.sh" "$BASE"

echo ""
echo ">>> Phase 2 目录/门户"
bash "$SCRIPT_DIR/phase2_verify.sh" "$BASE"

echo ""
echo ">>> ERP 桥接"
bash "$SCRIPT_DIR/erp_verify.sh" "$BASE"

if [ -f "$ROOT/smart-crm/data/auth_emails.log" ]; then
  echo ""
  echo ">>> Phase 2 Live（OTP）"
  bash "$SCRIPT_DIR/phase2_live.sh" "$BASE" || echo "  (phase2_live 失败 — 检查 auth_emails.log)"
fi

echo ""
echo ">>> KB / 系统状态"
curl -sf "$BASE/api/kb/status" | python3 -m json.tool 2>/dev/null || true
curl -sf "$BASE/api/health" | python3 -m json.tool 2>/dev/null || true

echo ""
echo "=== 全量测试完成 ==="
