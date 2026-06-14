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
| Tab8 | **AI 内容工坊** — KEYWORD / SEO META / SLUG / 产品描述 / 文章（含多语言批量） |
| Tab9 | **试点看板** — 里程碑、WhatsApp 触达、KB 语义检索 |

## Phase 1.5 西语试点

| 脚本 | 说明 |
|------|------|
| `bash scripts/mx_pilot.sh` | 墨西哥 MX：Track B → Brainstorm → Track A 入队 |
| `bash scripts/co_pilot.sh` | 哥伦比亚 CO：同上 |
| `bash scripts/latam_full_pilot.sh` | **MX + CO 联合试点** + 报告导出（`--run-due=N`） |
| `/admin/leads` | **员工后台**（登录后：线索/工厂/订单/品类） |
| `bash scripts/pilot_live.sh` | 真实 API 环境全流程（含飞书 confirm） |
| `bash scripts/outreach_pilot.sh` | 1.5.5 WhatsApp 触达里程碑（≥5 条） |
| `bash scripts/trackc_pilot.sh` | 1.5.6 海关 CSV 导入 + 域名匹配 |
| `bash scripts/kb_pilot.sh` | 1.5.7 知识库索引 + 语义召回 |
| `bash scripts/phase15_verify.sh` | **全量 1.5 验收**（`--quick` 快速模式） |
| Tab5 面板 | MX / CO 一键试点按钮 |
| Tab4 面板 | 「执行到期任务」跑入队后的 Track A |
| Tab9 面板 | 试点里程碑 + WhatsApp 记录 + KB 搜索 |

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

## Cursor Skill 与测试（改代码时用）

| 用途 | 文档/脚本 |
|------|-----------|
| 复制提示词给 Cursor | [docs/CURSOR_PROMPTS.md](docs/CURSOR_PROMPTS.md) |
| 改完自动验收 | `bash scripts/smoke_test.sh` 或 `bash scripts/run_all_tests.sh` |
| 飞书字段对照 | [docs/FEISHU_FIELDS.md](docs/FEISHU_FIELDS.md) · 面板 `GET /docs/feishu-fields` |
| 项目交接状态 | [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) |
| 验收报告导出 | `bash scripts/acceptance_report.sh [URL]` |
| TBCEXP 桥接文档 | [docs/TBCEXP_BRIDGE.md](docs/TBCEXP_BRIDGE.md) |
| Phase 1 登录验收 | `bash scripts/phase1_live.sh [URL]` |
| VPS 一键引导 | `sudo bash scripts/bootstrap_vps.sh` |
| VPS 部署验收 | `bash scripts/vps_verify.sh [URL]` |
| 环境安全检查 | `bash scripts/check_env.sh` |
| 备份 cron 安装 | `sudo bash scripts/setup_backup_cron.sh` |
| HTTPS 配置 | `sudo bash scripts/setup_https.sh crm.domain.com` |
| 快速状态 | `bash scripts/status.sh [URL]` |
| 真实 API 试点 | `bash scripts/pilot_live.sh [URL]` 或 `--co` |
| 生产上线引导 | [docs/PRODUCTION_ONBOARDING.md](docs/PRODUCTION_ONBOARDING.md) |
| 生产一键引导 | `bash scripts/prod_onboard.sh [URL]` 或 `--full` |
| Postman API 测试 | 导入 [postman/SMART_CRM.postman_collection.json](postman/SMART_CRM.postman_collection.json) |
| API 集成状态 | `GET /api/integrations/status`（是否 Mock 模式） |

## 默认测试账号

| 邮箱 | 门户 |
|------|------|
| admin@example.com | /admin |
| customer@example.com | /portal |

OTP / 魔法链接邮件写入 `data/auth_emails.log`（未配置 Resend 时）。
