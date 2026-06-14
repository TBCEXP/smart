#!/usr/bin/env bash
# 生产环境首次上线引导 — 第零期 preflight + VPS 验收 + 1.5 试点
# 用法: bash scripts/prod_onboard.sh [BASE_URL] [--full]
#   --full  配置真实 API Key 后跑完整 phase15 + pilot_live（默认仅 quick 验收）
set -euo pipefail

BASE="http://127.0.0.1:8000"
FULL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

for arg in "$@"; do
  case "$arg" in
    http*) BASE="$arg" ;;
    --full) FULL=1 ;;
  esac
done

echo "╔══════════════════════════════════════════════════╗"
echo "║     SMART CRM 生产上线引导 (Phase 0 → 1.5)      ║"
echo "╚══════════════════════════════════════════════════╝"
echo "Base: $BASE"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 第零期 — 基础设施"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo ">>> [0.1] 环境检查"
bash "$SCRIPT_DIR/check_env.sh" "${OPT_DIR:-/opt/smart-crm}" 2>/dev/null || bash "$SCRIPT_DIR/check_env.sh" "$(cd "$SCRIPT_DIR/.." && pwd)" 2>/dev/null || true
echo ""

echo ">>> [0.2] 系统 preflight"
bash "$SCRIPT_DIR/preflight.sh" || true
echo ""

echo ">>> [0.3] VPS 服务验收"
bash "$SCRIPT_DIR/vps_verify.sh" "$BASE"
echo ""

echo ">>> [0.4] 当前状态"
bash "$SCRIPT_DIR/status.sh" "$BASE"
echo ""

INT=$(curl -sf "$BASE/api/integrations/status" 2>/dev/null || echo '{}')
LIVE_READY=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('production_ready',False))" 2>/dev/null || echo False)
CONFIGURED=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('configured_count',0))" 2>/dev/null || echo 0)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Phase 1.5 — 西语试点"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$LIVE_READY" = "True" ]; then
  echo ">>> API Key 已就绪 ($CONFIGURED/8)，运行 1.5 验收"
  if [ "$FULL" -eq 1 ]; then
    bash "$SCRIPT_DIR/phase15_verify.sh" "$BASE"
    echo ""
    echo ">>> LATAM 联合试点"
    bash "$SCRIPT_DIR/latam_full_pilot.sh" "$BASE" --run-due=2
    echo ""
    echo ">>> 启动 MX 真实试点"
    bash "$SCRIPT_DIR/pilot_live.sh" "$BASE"
  else
    bash "$SCRIPT_DIR/phase15_verify.sh" "$BASE" --quick
    echo ""
    echo "配置完成后运行完整验收:"
    echo "  bash scripts/prod_onboard.sh $BASE --full"
  fi
else
  echo ">>> Mock 模式 ($CONFIGURED/8 Key) — 运行 quick 验收演示"
  bash "$SCRIPT_DIR/phase15_verify.sh" "$BASE" --quick
  echo ""
  echo "┌─────────────────────────────────────────────────┐"
  echo "│  下一步（生产必做）                              │"
  echo "├─────────────────────────────────────────────────┤"
  echo "│  1. 浏览器打开 $BASE"
  echo "│  2. /admin 登录 → Tab2 配置 API Key             │"
  echo "│     Exa + Firecrawl + OpenAI + 飞书             │"
  echo "│  3. Tab2「检测连通性」四项 live 通过             │"
  echo "│  4. Tab2「飞书写入测试」确认表格字段             │"
  echo "│  5. 重新运行:                                   │"
  echo "│     bash scripts/prod_onboard.sh $BASE --full  │"
  echo "│  6. HTTPS: sudo bash scripts/setup_https.sh     │"
  echo "│  7. 备份 cron: sudo bash scripts/setup_backup_cron.sh │"
  echo "└─────────────────────────────────────────────────┘"
fi

echo ""
echo "=== 上线引导完成 ==="
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Phase 1 + 2 — 员工业务 / 目录门户"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
bash "$SCRIPT_DIR/phase1_verify.sh" "$BASE"
echo ""
bash "$SCRIPT_DIR/phase2_verify.sh" "$BASE"
if [ -f "$SCRIPT_DIR/../smart-crm/data/auth_emails.log" ]; then
  echo ""
  bash "$SCRIPT_DIR/phase2_live.sh" "$BASE" || true
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Phase 3 — 大文件 / 分享通知"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
bash "$SCRIPT_DIR/phase3_verify.sh" "$BASE"
if [ -f "$SCRIPT_DIR/../smart-crm/data/auth_emails.log" ]; then
  echo ""
  bash "$SCRIPT_DIR/phase3_live.sh" "$BASE" || true
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Phase 4 — 印刷前稿 AI"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
bash "$SCRIPT_DIR/phase4_verify.sh" "$BASE"
if [ -f "$SCRIPT_DIR/../smart-crm/data/auth_emails.log" ]; then
  echo ""
  bash "$SCRIPT_DIR/phase4_live.sh" "$BASE" || true
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Phase 5 — 大货实拍 AI"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
bash "$SCRIPT_DIR/phase5_verify.sh" "$BASE"
if [ -f "$SCRIPT_DIR/../smart-crm/data/auth_emails.log" ]; then
  echo ""
  bash "$SCRIPT_DIR/phase5_live.sh" "$BASE" || true
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ERP 桥接"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
bash "$SCRIPT_DIR/erp_verify.sh" "$BASE"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " 路线图终验收"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
bash "$SCRIPT_DIR/final_acceptance.sh" "$BASE" 2>/dev/null | tail -8 || bash "$SCRIPT_DIR/pre_merge_verify.sh" "$BASE" | tail -8
echo ""
echo "交接报告: bash scripts/acceptance_report.sh $BASE"
echo "代码终检: bash scripts/go_live.sh $BASE"
