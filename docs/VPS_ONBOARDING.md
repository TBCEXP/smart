# VPS 上线引导（v2.1.0）

> 代码验收已完成。按本清单在 RackNerd VPS 上完成生产部署。  
> 快速入口: `bash scripts/production_start.sh [URL] [VPS_IP]`

## 前置条件

| 项 | 说明 |
|----|------|
| VPS | Ubuntu 22.04+，建议 2GB+ RAM |
| 域名 | `crm.yourdomain.com` → VPS IP |
| GitHub Secrets | `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` |

## 一键流程

```bash
# 1. VPS 首次初始化（root）
sudo bash scripts/bootstrap_vps.sh

# 2. 克隆/升级代码
cd /opt/smart-crm
git pull origin main
bash scripts/upgrade.sh

# 3. 本地验收
bash scripts/vps_verify.sh http://127.0.0.1:8000
bash scripts/deploy_verify.sh http://127.0.0.1:8000
bash scripts/go_live.sh http://127.0.0.1:8000
bash scripts/prod_onboard.sh http://127.0.0.1:8000

# 4. Tab2 配置 API Key 后全量验收
bash scripts/ready.sh https://crm.yourdomain.com
bash scripts/prod_onboard.sh https://crm.yourdomain.com --full
bash scripts/acceptance_report.sh https://crm.yourdomain.com
bash scripts/export_blockers.sh https://crm.yourdomain.com
```

## HTTPS

```bash
sudo bash scripts/setup_https.sh crm.yourdomain.com
sudo bash scripts/setup_backup_cron.sh
```

## 必配 API Key（Tab2）

| Key | 用途 |
|-----|------|
| Exa | Track A 获客 |
| Firecrawl | 网页抓取 |
| OpenAI | LLM + KB 语义 |
| 飞书 | 1.5.4 同步验收 |
| R2 | 目录 PDF + 大文件 |
| Resend | 分享邮件（可选） |
| TBCEXP ERP | 线索/订单同步（可选） |

`configured_count ≥ 4` 时 `production_ready: true`。

## 诊断命令

```bash
bash scripts/deploy_preflight.sh
bash scripts/onboard_checklist.sh https://crm.yourdomain.com
bash scripts/prod_readiness_check.sh https://crm.yourdomain.com
bash scripts/status.sh https://crm.yourdomain.com
curl -s https://crm.yourdomain.com/api/system/readiness | python3 -m json.tool
```

## 回滚

```bash
cd /opt/smart-crm
git checkout v2.1.0   # 或上一 tag
bash scripts/upgrade.sh
```

详见 [PRODUCTION_READY.md](PRODUCTION_READY.md)、[DEPLOYMENT.md](DEPLOYMENT.md)。
