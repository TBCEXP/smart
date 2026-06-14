# SMART CRM — 项目状态（交接）

> 最后更新：Phase 1.5 西语试点（MX/CO）代码与验收脚本已就绪，待 VPS + API Key 生产验收。

## 已完成

| 区域 | 状态 | 说明 |
|------|------|------|
| Phase 0 基础设施 | ✅ | Docker Compose、Nginx、备份 cron、CI/CD |
| Tab1–4 Track A | ✅ | Exa → Firecrawl → LLM → 飞书（review/auto） |
| Tab5 Track B | ✅ | 锚点采集、市场情报、MX/CO 试点向导 |
| Tab6 Brainstorm | ✅ | 西语关键词、similar search、入队 Track A |
| Tab7 Track C | ✅ | 海关 CSV、展会参展商、域名匹配 |
| Tab8 内容工坊 | ✅ | es/en/pt 批量 SEO + ZIP |
| Tab9 试点看板 | ✅ | 里程碑、WhatsApp、KB 检索、报告导出 |
| Exa 查询质量 | ✅ | L3 西语模板 + `resolve_exa_query` 管线接入 |
| 验收脚本 | ✅ | smoke 39+、phase15、phase1、phase2 |
| Phase 1 员工业务 | ✅ | 工厂/订单/品类树、ERP 桥接、飞书只读、角色过滤 |
| TBCEXP 桥接 | ✅ | `POST /api/bridge/tbcexp/{id}`（Mock 或 live HTTP） |
| 文档 | ✅ | 部署、上线引导、飞书字段、路线图 |

## 本地 / Mock 验收

```bash
cd smart-crm && USE_SQLITE=1 uvicorn main:app --port 8000 &
bash scripts/run_all_tests.sh http://127.0.0.1:8000
bash scripts/latam_full_pilot.sh http://127.0.0.1:8000 --run-due=2
```

典型 Mock 里程碑：**1.5.5 ✓、1.5.7 ✓、MX Track B/Brainstorm ✓**  
需真实 API：**1.5.4 飞书≥30、1.5.6 Track C 50 条、CO 正式跑量**

## 待用户提供

| 项 | 用途 |
|----|------|
| RackNerd VPS IP | `bootstrap_vps.sh` / GitHub Deploy |
| 域名 + DNS | HTTPS（`setup_https.sh`） |
| Exa / Firecrawl / OpenAI API Key | 真实获客与内容 |
| 飞书 App + 多维表格 | 1.5.4 同步验收 |
| GitHub Secrets | `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` |

## 生产上线命令（VPS 就绪后）

```bash
sudo bash scripts/bootstrap_vps.sh
bash scripts/prod_onboard.sh http://VPS_IP:8000
bash scripts/prod_onboard.sh https://crm.domain.com --full
bash scripts/latam_full_pilot.sh https://crm.domain.com --run-due=3
bash scripts/phase15_verify.sh https://crm.domain.com
bash scripts/acceptance_report.sh https://crm.domain.com report.md
sudo bash scripts/setup_backup_cron.sh
```

## 关键 API

| 端点 | 说明 |
|------|------|
| `GET /api/health` | 版本、数据库模式 |
| `GET /api/system/readiness` | 版本、数据库模式 + Phase 1/2 checklist |
| `GET /api/system/handoff-report` | Phase 0–2 交接 Markdown |
| `PATCH /api/orders/{id}` | 确认/取消订单（需登录） |
| `GET /api/pilot/report` | MX/CO 试点 + 里程碑 |
| `GET /api/pilot/export?format=md` | 验收报告 Markdown |
| `GET /docs/feishu-fields` | 飞书列名对照（Tab2） |
| `GET /api/exa/preview-query` | Tab1 Exa 查询预览（L3 西语模板） |
| `GET /api/leads` | 线索只读列表（`mine=1` 需登录） |
| `GET /admin/dashboard` | 员工后台（线索/工厂/订单/品类） |
| `GET /api/catalog/tree` | L1/L2/L3 品类树 |
| `GET /api/factories` | 工厂主数据 |
| `POST /api/bridge/tbcexp/{lead_id}` | 推送线索至 ERP（需登录） |
| `GET /api/feishu/records/{id}` | 飞书记录只读查询 |
| `GET /api/admin/summary` | 员工后台汇总（按角色） |
| `POST /api/orders/from-lead/{id}` | 线索转草稿订单 |
| `bash scripts/phase1_verify.sh` | Phase 1 验收脚本 |

## Phase 2 起步（本分支）

| 功能 | 状态 |
|------|------|
| `/portal/dashboard` | ✅ 客户只读订单 |
| `/s/{token}` | ✅ 订单/工厂分享外链 |
| Phase 2 目录元数据 | ✅ `CatalogDocument` + 门户授权 + R2 签名 URL |
| Cloudflare R2 对接 | ✅ `r2_client.py` + 下载/上传 API |
| 员工后台工厂目录 | ✅ `/admin/dashboard` → 工厂目录 Tab |
| ERP 订单只读 | ✅ `GET /api/bridge/tbcexp/orders` |
| Apollo 联系人补充 | ✅ 线索行 + `enrich-contact` API |
| 验收脚本 | ✅ `phase2_verify.sh` + `phase2_live.sh` |
| 报价单分发 | ✅ `doc_type=quote/price_list` + `/portal/quotes` |

## Phase 1+（ERP 深度对接）

员工门户、工厂目录、订单、包装 AI — 见 [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)，在 Phase 1.5 生产验收通过后启动。

## 仓库

- GitHub: `https://github.com/TBCEXP/smart`
- 主分支: `main`
