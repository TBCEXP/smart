# SMART CRM

B2B 智能获客面板 — Exa + Firecrawl + LLM + 飞书，扩展 §0G Brainstorm Lab、双线获客、Track C 海关导入、邮箱认证。

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

## 默认测试账号

| 邮箱 | 门户 |
|------|------|
| admin@example.com | /admin |
| customer@example.com | /portal |

OTP / 魔法链接邮件写入 `data/auth_emails.log`（未配置 Resend 时）。
