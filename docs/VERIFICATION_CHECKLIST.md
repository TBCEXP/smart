# SMART CRM 验证清单（verification）

每次改代码、部署前跑一遍。

## A. 自动化 Smoke（必跑）

```bash
bash scripts/smoke_test.sh http://127.0.0.1:8000
# 生产: bash scripts/smoke_test.sh https://crm.yourdomain.com
# VPS 全量: bash scripts/vps_verify.sh https://crm.yourdomain.com
```

| # | 检查项 | 通过标准 |
|---|--------|----------|
| A1 | 健康检查 | `/api/health` → `status: ok` |
| A2 | 集成状态 | `/api/integrations/status` → `configured_count ≥ 4`（生产） |
| A3 | API 探测 | `POST /api/integrations/probe` → 四项 live（生产） |
| A4 | 就绪检查 | `GET /api/system/readiness` → `production_blockers` |
| A5 | Brainstorm | 生成 session + 5 张卡片 |
| A6 | 获客批次 | `POST /api/run` count=2 → batch 完成 |
| A7 | MX/CO 试点 | `POST /api/pilot/mx/start` → session_id |
| A8 | 定时入队 | `POST /api/schedules/run-due` → queued |
| A9 | Tab9 看板 | `GET /api/stats/overview` → milestones |
| A10 | WhatsApp 触达 | `POST/GET/PATCH /api/outreach/*` |
| A11 | Track C 试点 | `bash scripts/trackc_pilot.sh` |
| A12 | KB 检索 | `bash scripts/kb_pilot.sh` |
| A13 | WhatsApp 里程碑 | `bash scripts/outreach_pilot.sh` |
| A14 | KB 状态 | `GET /api/kb/status` → search_engine |
| A15 | 全量测试 | `bash scripts/run_all_tests.sh` |
| A16 | Exa 查询预览 | `GET /api/exa/preview-query` → resolved + semantic |
| A17 | 线索列表 | `GET /api/leads` · `/admin/leads` 员工视图 |
| A18 | LATAM 联合试点 | `bash scripts/latam_full_pilot.sh` |
| A19 | Phase 1 工厂/品类 | `GET /api/factories` + `/api/catalog/tree` |
| A21 | 客户门户 | `GET /portal/dashboard` |
| A22 | 分享链接 | `GET /api/share/{token}` · `POST /api/share/links` |
| A23 | Phase 3 大文件 | `bash scripts/phase3_verify.sh` |
| A24 | Phase 4 前稿 AI | `bash scripts/phase4_verify.sh` |
| A25 | Phase 5 实拍 AI | `bash scripts/phase5_verify.sh` |
| A26 | 一站式就绪 | `bash scripts/ready.sh` |
| A27 | 代码终检 | `bash scripts/go_live.sh` |
| A28 | 阻塞导出 | `bash scripts/export_blockers.sh` |

快捷全量：`bash scripts/ready.sh` → `bash scripts/go_live.sh`
深度验收（可选）：`bash scripts/final_acceptance.sh`

## B. 浏览器手动

| # | 路径 | 操作 | 预期 |
|---|------|------|------|
| B1 | 首页横幅 | 未配置时显示「首次部署」 | 点击跳转 Tab2 |
| B2 | Tab2 | 保存 Key + 检测连通性 | live 四项通过 |
| B3 | Tab2 | 登录后「飞书写入测试」 | 飞书表出现测试行 |
| B4 | Tab5 | MX / CO 试点 | 验收 JSON 三项 ✓ |
| B5 | Tab4 | 执行到期任务 | batch_id 返回 |
| B6 | Tab3 | 确认入库 | feishu_record_id 非空 |

## C. 生产环境

| # | 命令 / 检查项 |
|---|----------------|
| C1 | `sudo bash scripts/bootstrap_vps.sh` 或 `install.sh` |
| C2 | `bash scripts/vps_verify.sh` 无 FAIL |
| C3 | `bash scripts/pilot_live.sh` 或 `--co` |
| C4 | `sudo bash scripts/setup_https.sh crm.domain.com` |
| C5 | GitHub Actions CI + Deploy 绿色 |
| C6 | `sudo bash scripts/backup_daily.sh` + cron 每日备份 |
| C7 | `bash scripts/ready.sh` + `bash scripts/export_blockers.sh` |
| C8 | `bash scripts/onboard_checklist.sh` 人工待办已核对 |

## D. 1.5 期验收（MX → CO）

| # | 指标 |
|---|------|
| D1 | Track B 锚点情报 ≥1 份/国 |
| D2 | Brainstorm 关键词人工认可 |
| D3 | ≥10 条西语开发信可发 |
| D4 | 飞书累计 ≥30 条（MX+CO） |
| D5 | Tab8 热点产品 es/en/pt SEO 包 |
| D6 | 1.5.5 WhatsApp ≥5 家（`outreach_pilot.sh`） |
| D7 | 1.5.6 Track C 50 条匹配 >60%（`trackc_pilot.sh --no-website`） |
| D8 | 1.5.7 KB 语义召回（`kb_pilot.sh`） |

## 失败排查

| 症状 | 查什么 |
|------|--------|
| Mock 数据 | Tab2 Key；`/api/integrations/probe` |
| 飞书失败 | Tab2 飞书写入测试；字段名与表格权限 |
| 批次卡住 | SSE；SQLite 并发；`/api/stream/{id}` |
| 401 写配置 | 先 `/admin` 登录拿 session_token |
| 部署失败 | GitHub Actions 日志；`docker compose logs` |
