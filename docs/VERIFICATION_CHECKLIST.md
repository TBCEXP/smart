# SMART CRM 验证清单（verification）

每次改代码、部署前跑一遍。自动化部分：`bash scripts/smoke_test.sh`

## A. 自动化 Smoke（必跑）

```bash
bash scripts/smoke_test.sh http://127.0.0.1:8000
# 生产: bash scripts/smoke_test.sh https://crm.yourdomain.com
```

| # | 检查项 | 通过标准 |
|---|--------|----------|
| A1 | 健康检查 | `/api/health` → `status: ok` |
| A2 | 集成状态 | `/api/integrations/status` → `configured_count ≥ 4`（生产） |
| A3 | Brainstorm | 生成 session + 5 张卡片 |
| A4 | 获客批次 | `POST /api/run` count=2 → 至少 1 条 lead |
| A5 | 知识库 | `/api/kb/search?q=...` 有 results |
| A6 | 登录 | OTP send 返回 sent |
| A7 | 锚点 | MX 有 Vasconia |

## B. 浏览器手动（browser-automation / 人工）

| # | 路径 | 操作 | 预期 |
|---|------|------|------|
| B1 | `/` Tab1 | 填 MX+CDMX+bakeware，跑 5 条 | SSE 日志有进度 |
| B2 | `/` Tab3 | 查看 lead 卡片 | 有西语开发信 + WhatsApp |
| B3 | `/` Tab6 | Brainstorm MX 烘焙模具 | 5 卡片 + 入队按钮 |
| B4 | `/admin` | OTP 登录 admin@example.com | 收到验证码/日志 |
| B5 | Tab2 保存配置 | 无 401（已登录）或未登录 401 | 鉴权生效 |

## C. 生产环境额外项

| # | 检查项 |
|---|--------|
| C1 | `bash scripts/preflight.sh` 无 FAIL |
| C2 | `curl https://域名/api/integrations/status` 四项 live |
| C3 | review 模式确认 1 条 → 飞书表出现记录 |
| C4 | `git push main` → GitHub Actions 部署绿色 |

## D. 1.5 期墨西哥试点验收

| # | 指标 |
|---|------|
| D1 | Track B Vasconia 情报 1 份 |
| D2 | Brainstorm 关键词人工认可 |
| D3 | ≥10 条 A/B 级西语开发信 |
| D4 | WhatsApp 手动发 ≥3 家，记录回复 |

## 失败时排查

| 症状 | 查什么 |
|------|--------|
| Mock 数据 | Tab2 API Key；`/api/integrations/status` |
| 飞书写入失败 | 字段名、应用表格权限、App ID/Secret |
| SSE 卡住 | Nginx `proxy_buffering off` |
| 401  everywhere | 先 `/api/auth/otp/verify` 拿 session_token |
