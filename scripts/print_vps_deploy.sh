#!/usr/bin/env bash
# 针对指定 VPS 打印完整首次部署命令（本地运行，不需 SSH）
# 用法: bash scripts/print_vps_deploy.sh <VPS_IP> [SSH_USER]
set -euo pipefail

IP="${1:-}"
USER="${2:-root}"
REPO="${SMART_REPO:-TBCEXP/smart}"

if [ -z "$IP" ]; then
  echo "用法: bash scripts/print_vps_deploy.sh <VPS_IP> [SSH_USER]"
  exit 1
fi

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM VPS 部署包 — ${IP}"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "连通性: SSH 22 应开放（应用 8000 在 bootstrap 后开放）"
echo ""

echo "=== A. 在 VPS 上执行（SSH 登录 ${USER}@${IP}）==="
echo ""
cat <<EOF
curl -fsSL https://raw.githubusercontent.com/${REPO}/main/scripts/bootstrap_vps.sh | sudo bash
# 或已克隆:
# cd /opt/smart-crm && sudo bash scripts/upgrade.sh
curl -sf http://127.0.0.1:8000/api/health
bash scripts/production_start.sh http://127.0.0.1:8000 ${IP}
EOF
echo ""

echo "=== B. GitHub Secrets（https://github.com/${REPO}/settings/secrets/actions）==="
echo ""
echo "  VPS_HOST      = ${IP}"
echo "  VPS_USER      = ${USER}"
echo "  VPS_SSH_KEY   = （VPS 上 github_deploy 私钥全文）"
echo ""
echo "VPS 生成密钥:"
echo "  ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N \"\""
echo "  cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys"
echo "  cat ~/.ssh/github_deploy   # → 复制到 GitHub Secret"
echo ""

echo "=== C. 公网验收（bootstrap 完成后）==="
echo ""
echo "  curl -sf http://${IP}:8000/api/health"
echo "  bash scripts/vps_verify.sh http://${IP}:8000"
echo ""

echo "=== D. HTTPS（有域名后）==="
echo ""
echo "  sudo bash scripts/setup_https.sh crm.yourdomain.com"
echo "  # 修改 /opt/smart-crm/.env APP_BASE_URL=https://crm.yourdomain.com"
echo ""

echo "=== E. Tab2 API Key + 全量验收 ===="
echo ""
echo "  bash scripts/setup_tab2_keys.sh http://${IP}:8000"
echo "  bash scripts/prod_onboard.sh http://${IP}:8000 --full"
echo "  bash scripts/go_live.sh https://crm.yourdomain.com"
echo ""
