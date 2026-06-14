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

## Phase 1 员工业务

| 脚本 / 页面 | 说明 |
|-------------|------|
| `/admin/dashboard` | 线索 / 工厂 / 订单 / 品类 / **工厂目录** / **大文件** |
| `bash scripts/phase1_verify.sh` | Phase 1 API 验收 |
| `bash scripts/phase1_live.sh` | OTP 登录后创建订单 + 分享 |

## Phase 2 目录 / 报价 / 门户

| 脚本 / 页面 | 说明 |
|-------------|------|
| `/portal/dashboard` | 客户订单 + 授权目录 + **报价单** |
| `/s/{token}` | 订单 / 目录分享外链 |
| `bash scripts/phase2_verify.sh` | 目录元数据 + R2 + Apollo 验收 |
| `bash scripts/phase2_live.sh` | OTP 门户 + 目录分享验收 |
| `bash scripts/upload_catalog_r2.sh` | R2 PDF 上传 |
| `GET /api/system/handoff-report` | Phase 0–3 交接 Markdown |

## Phase 3 大文件 / 分享通知

| 脚本 / 页面 | 说明 |
|-------------|------|
| `/admin/dashboard` → 大文件 | 元数据、R2 上传 URL、分享+邮件通知 |
| `/s/{token}` | 支持 `resource_type=file` 公开下载 |
| `bash scripts/phase3_verify.sh` | 大文件 API + 通知 + readiness 验收 |
| `bash scripts/phase3_live.sh` | OTP 登录后创建/分享/通知全流程 |
| `docs/PHASE3_FILES.md` | Phase 3 功能说明 |

## Phase 4 印刷前稿 AI

| 脚本 / 页面 | 说明 |
|-------------|------|
| `/admin/dashboard` → 印刷前稿 | 条码 + 文本/图形 diff 规则引擎 |
| `bash scripts/phase4_verify.sh` | 前稿 AI 验收 |
| `docs/PHASE4_PREPRESS.md` | Phase 4 功能说明 |

## Phase 5 大货实拍 AI

| 脚本 / 页面 | 说明 |
|-------------|------|
| `/admin/dashboard` → 大货实拍 | OpenCV 对齐 + 人工终审 |
| `bash scripts/phase5_verify.sh` | 实拍 AI 验收 |
| `docs/PHASE5_PRODUCTION.md` | Phase 5 功能说明 |

## 路线图终验收（Phase 0–5）

```bash
bash scripts/ready.sh http://127.0.0.1:8000
bash scripts/go_live.sh http://127.0.0.1:8000
bash scripts/export_blockers.sh http://127.0.0.1:8000
```

| 文档 / 脚本 | 说明 |
|-------------|------|
| [docs/PRODUCTION_READY.md](docs/PRODUCTION_READY.md) | VPS + API Key 上线清单 |
| `bash scripts/go_live.sh` | 代码侧完整终检 |
| `bash scripts/final_acceptance.sh` | 路线图深度验收（可选） |
| 应用版本 | **2.1.0** |

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
| PR 合并清单 | [docs/MERGE_CHECKLIST.md](docs/MERGE_CHECKLIST.md) |
| 生产就绪 | [docs/PRODUCTION_READY.md](docs/PRODUCTION_READY.md) |
| 路线图终验收 | `bash scripts/final_acceptance.sh [URL]` |
| 合并前验收 | `bash scripts/pre_merge_verify.sh [URL]`（10 项） |
| ERP 桥接验收 | `bash scripts/erp_verify.sh [URL]` |
| 生产就绪诊断 | `bash scripts/prod_readiness_check.sh [URL]` |
| 验收报告导出 | `bash scripts/acceptance_report.sh [URL]` |
| TBCEXP 桥接文档 | [docs/TBCEXP_BRIDGE.md](docs/TBCEXP_BRIDGE.md) |
| Phase 2 验收 | `bash scripts/phase2_verify.sh [URL]` |
| Phase 2 目录说明 | [docs/PHASE2_CATALOG.md](docs/PHASE2_CATALOG.md) |
| VPS 一键引导 | `sudo bash scripts/bootstrap_vps.sh` |
| VPS 部署验收 | `bash scripts/vps_verify.sh [URL]` |
| 环境安全检查 | `bash scripts/check_env.sh` |
| 备份 cron 安装 | `sudo bash scripts/setup_backup_cron.sh` |
| HTTPS 配置 | `sudo bash scripts/setup_https.sh crm.domain.com` |
| 快速状态 | `bash scripts/status.sh [URL]` |
| 真实 API 试点 | `bash scripts/pilot_live.sh [URL]` 或 `--co` |
| 生产上线引导 | [docs/PRODUCTION_ONBOARDING.md](docs/PRODUCTION_ONBOARDING.md) |
| 部署验收 | `bash scripts/deploy_verify.sh [URL]` |
| 部署前检查 | `bash scripts/deploy_preflight.sh` |
| 一站式就绪 | `bash scripts/ready.sh [URL]` |
| 阻塞导出 | `bash scripts/export_blockers.sh [URL]` |
| 上线待办 | `bash scripts/onboard_checklist.sh [URL]` |
| 代码终检 | `bash scripts/go_live.sh [URL]` |
| 发布完整性 | `bash scripts/release_check.sh [URL]` |
| 代码交付确认 | `bash scripts/delivery_complete.sh [URL]` |
| 生产上线入口 | `bash scripts/production_start.sh [URL] [VPS_IP]` |
| Tab2 Key 配置 | `bash scripts/setup_tab2_keys.sh [URL]` |
| GitHub 部署配置 | `bash scripts/setup_github_deploy.sh [VPS_IP]` |
| 项目交接 | [docs/HANDOFF.md](docs/HANDOFF.md) |
| VPS 上线 | [docs/VPS_ONBOARDING.md](docs/VPS_ONBOARDING.md) |
| Postman API 测试 | 导入 [postman/SMART_CRM.postman_collection.json](postman/SMART_CRM.postman_collection.json) |
| API 集成状态 | `GET /api/integrations/status`（是否 Mock 模式） |

## 默认测试账号

| 邮箱 | 门户 |
|------|------|
| admin@example.com | /admin |
| customer@example.com | /portal |

OTP / 魔法链接邮件写入 `data/auth_emails.log`（未配置 Resend 时）。
