#!/usr/bin/env bash
# 生产上线终检 — 本地或 VPS 一键跑完全部验收
# 用法: bash scripts/go_live.sh [BASE_URL]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE="${1:-http://127.0.0.1:8000}"

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM 生产上线终检 (v2.1.0)               ║"
echo "╚══════════════════════════════════════════════════╝"
echo "Base: $BASE"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " deploy_preflight (静态检查)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash "$SCRIPT_DIR/deploy_preflight.sh"
echo ""

steps=(
  "release_check:$SCRIPT_DIR/release_check.sh"
  "erp_verify:$SCRIPT_DIR/erp_verify.sh"
  "final_acceptance:$SCRIPT_DIR/final_acceptance.sh"
)

for entry in "${steps[@]}"; do
  name="${entry%%:*}"
  script="${entry#*:}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo " $name"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  bash "$script" "$BASE"
  echo ""
done

echo ">>> 验收报告导出（可选）"
echo "  bash scripts/acceptance_report.sh $BASE go-live-$(date +%Y%m%d)"
echo ""
echo "=== 代码验收全部通过 ==="
echo ""
echo "生产阻塞项（需人工）:"
echo "  [ ] VPS_HOST / VPS_USER / VPS_SSH_KEY → GitHub Secrets"
echo "  [ ] 域名 DNS → sudo bash scripts/setup_https.sh crm.domain.com"
echo "  [ ] Tab2 API Keys ≥4 → production_ready"
echo "  [ ] R2 凭据（目录 + 大文件）"
echo ""
echo "VPS 首次: sudo bash scripts/bootstrap_vps.sh"
echo "待办清单: bash scripts/onboard_checklist.sh $BASE"
echo "阻塞导出: bash scripts/export_blockers.sh $BASE"
echo "详见: docs/VPS_ONBOARDING.md"
