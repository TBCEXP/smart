#!/usr/bin/env bash
# 生产阻塞清单 — 打印人工待办与可复制命令
# 用法: bash scripts/onboard_checklist.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM 生产上线待办清单                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

if curl -sf "$BASE/api/health" >/dev/null 2>&1; then
  VER=$(curl -sf "$BASE/api/health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "?")
  INT=$(curl -sf "$BASE/api/integrations/status" 2>/dev/null || echo '{}')
  CC=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('configured_count',0))" 2>/dev/null || echo 0)
  PR=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('production_ready',False))" 2>/dev/null || echo False)
  echo "服务: $BASE (version $VER)"
  echo "API Key: $CC/9 configured | production_ready=$PR"
  echo ""
else
  echo "服务: 未运行 ($BASE)"
  echo ""
fi

cat <<'EOF'
## 1. VPS 基础设施

- [ ] RackNerd VPS（Ubuntu 22.04+，建议 2GB+ RAM）
- [ ] 记录公网 IP: curl -s ifconfig.me

```bash
# VPS 上（root）
sudo bash scripts/bootstrap_vps.sh
bash scripts/upgrade.sh
bash scripts/deploy_verify.sh http://127.0.0.1:8000
```

## 2. GitHub Secrets（自动部署）

仓库 Settings → Secrets and variables → Actions:

| Secret | 内容 |
|--------|------|
| VPS_HOST | VPS 公网 IP 或域名 |
| VPS_USER | SSH 用户（如 root） |
| VPS_SSH_KEY | 部署私钥全文 |

```bash
# VPS 生成密钥
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/github_deploy   # → 复制到 GitHub Secret
```

## 3. 域名 + HTTPS

- [ ] DNS A 记录: crm.yourdomain.com → VPS IP

```bash
sudo bash scripts/setup_https.sh crm.yourdomain.com
sudo bash scripts/setup_backup_cron.sh
```

## 4. Tab2 API Key（≥4 → production_ready）

| Key | 用途 |
|-----|------|
| Exa | Track A 获客 |
| Firecrawl | 网页抓取 |
| OpenAI | LLM + KB |
| 飞书 | 线索同步 |
| R2 | 目录/大文件（推荐） |
| TBCEXP ERP | 订单同步（可选） |
| Resend | 分享邮件（可选） |

浏览器: /admin → Tab2 → 配置 →「检测连通性」

## 5. 全量验收

```bash
bash scripts/go_live.sh https://crm.yourdomain.com
bash scripts/prod_onboard.sh https://crm.yourdomain.com --full
bash scripts/acceptance_report.sh https://crm.yourdomain.com
```

详见: docs/VPS_ONBOARDING.md · docs/HANDOFF.md
EOF
