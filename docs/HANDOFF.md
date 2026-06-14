# SMART CRM — 项目交接（Agent → 团队）

> 版本 **v2.1.0** · `main` @ `d1f2076` · tag `v2.1.0` · 代码侧 **交付关闭**

## 交付范围

| 模块 | 状态 |
|------|------|
| Phase 0–5 路线图 | ✅ 全部合并 `main` |
| 增量：OCR / ZBar / Tus / ERP 映射 | ✅ |
| 验收脚本体系 | ✅ 40 pytest · 47 smoke · `ready` / `go_live` |
| CI/CD + Docker | ✅ |
| 文档 + Postman | ✅ |

## 一键验收（本地 Mock）

```bash
bash scripts/delivery_complete.sh --static-only
cd smart-crm && USE_SQLITE=1 DATA_DIR=./data uvicorn main:app --port 8000 &
bash scripts/delivery_complete.sh http://127.0.0.1:8000
```

## VPS 上线（需团队提供资源）

详见 [VPS_ONBOARDING.md](VPS_ONBOARDING.md)。

```bash
sudo bash scripts/bootstrap_vps.sh
bash scripts/upgrade.sh
bash scripts/ready.sh https://crm.yourdomain.com
bash scripts/prod_onboard.sh https://crm.yourdomain.com --full
bash scripts/acceptance_report.sh https://crm.yourdomain.com
```

## 必配清单

| 资源 | 用途 | 阻塞 |
|------|------|------|
| RackNerd VPS | 部署目标 | 是 |
| GitHub Secrets | CI 自动部署 | 是 |
| 域名 + DNS | HTTPS | 是 |
| Exa + Firecrawl + OpenAI + 飞书 | 真实获客 | 是（生产） |
| Cloudflare R2 | 目录/大文件 | 推荐 |
| TBCEXP ERP URL | 订单同步 | 可选 |
| Resend | 分享邮件 | 可选 |

## 关键脚本索引

| 脚本 | 用途 |
|------|------|
| `go_live.sh` | 代码侧终检三连 |
| `deploy_verify.sh` | VPS/CI 部署后快速验收 |
| `deploy_preflight.sh` | 部署前静态检查（无需启动服务） |
| `onboard_checklist.sh` | 生产阻塞待办 + 可复制命令 |
| `ready.sh` | 一站式就绪（preflight + status + deploy_verify） |
| `release_check.sh` | v2.1.0 发布完整性 |
| `prod_readiness_check.sh` | 生产阻塞诊断 |
| `final_acceptance.sh` | 路线图终验收 |
| `acceptance_report.sh` | 导出试点+交接+阻塞 JSON |
| `export_blockers.sh` | 单独导出 `production_blockers` |
| `delivery_complete.sh` | 代码交付确认（Agent 完结检查） |

## 仓库

- https://github.com/TBCEXP/smart
- Tag: `v2.1.0`
- 分支策略: `main` 生产 · `cursor/*` 功能分支

## 后续（非阻塞）

- TBCEXP OpenAPI 对齐后微调 `tbcexp_mapping.py`
- 真实 Key 后跑 `pilot_live.sh` 完成 1.5.4 / 1.5.6 里程碑

---

*本文件标志 Cloud Agent 代码交付完成。生产验收待 VPS + API Key 就绪。*
