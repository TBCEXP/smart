#!/usr/bin/env bash
# GitHub Actions 自动部署配置助手 — 打印 Secrets 步骤与验证命令
# 用法: bash scripts/setup_github_deploy.sh [VPS_HOST]
set -euo pipefail

REPO="${SMART_REPO:-TBCEXP/smart}"
HOST="${1:-}"

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM — GitHub 自动部署配置               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "仓库: https://github.com/${REPO}"
echo "Secrets: https://github.com/${REPO}/settings/secrets/actions"
echo "Actions: https://github.com/${REPO}/actions/workflows/deploy.yml"
echo ""

echo "=== 步骤 1: VPS 生成部署密钥 ==="
echo ""
cat <<'EOF'
ssh-keygen -t ed25519 -C "github-deploy-smart-crm" -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/github_deploy
EOF
echo ""
echo "将私钥全文复制到 GitHub Secret: VPS_SSH_KEY"
echo "  cat ~/.ssh/github_deploy"
echo ""

echo "=== 步骤 2: GitHub Secrets（Repository secrets）==="
echo ""
echo "| Secret     | 值 |"
echo "|------------|-----|"
if [ -n "$HOST" ]; then
  echo "| VPS_HOST   | $HOST |"
else
  echo "| VPS_HOST   | <RackNerd 公网 IP 或域名> |"
fi
echo "| VPS_USER   | root（或你的 SSH 用户） |"
echo "| VPS_SSH_KEY| ~/.ssh/github_deploy 全文 |"
echo ""

echo "=== 步骤 3: VPS 首次安装（在 VPS 上 root 执行）==="
echo ""
cat <<'EOF'
sudo bash scripts/bootstrap_vps.sh
# 或已克隆后:
cd /opt/smart-crm && bash scripts/upgrade.sh
bash scripts/ready.sh http://127.0.0.1:8000
EOF
echo ""

echo "=== 步骤 4: 验证自动部署 ==="
echo ""
echo "本地 push 后查看 Actions:"
echo "  https://github.com/${REPO}/actions"
echo ""
echo "VPS 上验收:"
echo "  bash scripts/deploy_verify.sh http://127.0.0.1:8000"
echo ""

if [ -n "$HOST" ]; then
  echo "=== 步骤 5: SSH 连通性测试 ==="
  echo ""
  echo "  ssh -i ~/.ssh/github_deploy ${VPS_USER:-root}@${HOST} 'curl -sf http://127.0.0.1:8000/api/health'"
  echo ""
fi

echo "配置完成后: git push origin main → 约 1–3 分钟自动 upgrade"
echo "详见: docs/DEPLOYMENT.md · docs/VPS_ONBOARDING.md"
