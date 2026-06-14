# SMART CRM

B2B 智能获客面板 — 实施须遵循 **[docs/IMPLEMENTATION_ROADMAP.md](docs/IMPLEMENTATION_ROADMAP.md)** 分期验收，勿跳步堆功能。

## 功能

| Tab | 功能 |
|-----|------|
| Tab1 | Track A 公司线获客（含相似公司搜索） |
| Tab2 | API Key 与系统配置 |
| Tab3 | 结果面板（开发信 + WhatsApp 话术） |
| Tab4 | 历史批次与定时任务 |
| Tab5 | Track B 市场情报 / 锚点采集 |
| Tab6 | Brainstorm Lab AI 策略工作台 |
| Tab7 | Track C 海关 CSV 导入 + 展会参展商 |

## 快速启动（开发）

```bash
cd smart-crm
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://smartcrm:smartcrm@localhost:5432/smartcrm
export SYNC_DATABASE_URL=postgresql://smartcrm:smartcrm@localhost:5432/smartcrm
uvicorn main:app --reload --port 8000
```

## 生产部署（RackNerd）

```bash
# 程序 → /opt/smart-crm，数据 → /var/lib/smart-crm
sudo bash scripts/install.sh
```

详见 `docker-compose.yml` 与 `nginx/crm.conf`。

## 更新发布（改代码后如何上传网页）

**推荐：GitHub 自动部署** — 完整说明见 **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**

```bash
# 日常：Cursor 改完代码
git add . && git commit -m "更新说明" && git push origin main
# → GitHub Actions 自动 SSH 到 VPS 执行 upgrade.sh（约 1–3 分钟）

# 手动备用：SSH 登录 VPS 后
cd /opt/smart-crm && sudo bash scripts/upgrade.sh
```

一次性在 GitHub 配置 Secrets：`VPS_HOST`、`VPS_USER`、`VPS_SSH_KEY`。

## 默认测试账号

| 邮箱 | 门户 |
|------|------|
| admin@example.com | /admin |
| customer@example.com | /portal |

OTP / 魔法链接邮件写入 `data/auth_emails.log`（未配置 Resend 时）。
