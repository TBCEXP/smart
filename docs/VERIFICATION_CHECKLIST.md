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
| A4 | 就绪检查 | `GET /api/system/readiness` → checklist |
| A5 | Brainstorm | 生成 session + 5 张卡片 |
| A6 | 获客批次 | `POST /api/run` count=2 → batch 完成 |
| A7 | MX/CO 试点 | `POST /api/pilot/mx/start` → session_id |
| A8 | 定时入队 | `POST /api/schedules/run-due` → queued |

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

## D. 1.5 期验收（MX → CO）

| # | 指标 |
|---|------|
| D1 | Track B 锚点情报 ≥1 份/国 |
| D2 | Brainstorm 关键词人工认可 |
| D3 | ≥10 条西语开发信可发 |
| D4 | 飞书累计 ≥30 条（MX+CO） |
| D5 | Tab8 热点产品 es/en/pt SEO 包 |

## 失败排查

| 症状 | 查什么 |
|------|--------|
| Mock 数据 | Tab2 Key；`/api/integrations/probe` |
| 飞书失败 | Tab2 飞书写入测试；字段名与表格权限 |
| 批次卡住 | SSE；SQLite 并发；`/api/stream/{id}` |
| 401 写配置 | 先 `/admin` 登录拿 session_token |
| 部署失败 | GitHub Actions 日志；`docker compose logs` |
