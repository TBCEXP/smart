# PR / 发布合并清单

> 主分支 `main` — **路线图 Phase 0–5 已完成**（v2.0.0）

## 发布前自动验收

```bash
cd smart-crm && USE_SQLITE=1 uvicorn main:app --port 8000 &
bash scripts/final_acceptance.sh http://127.0.0.1:8000
```

期望：**pytest 39/39 · smoke 47+ · phase1–5 全通过 · erp_verify · pre_merge 10/10**

## 功能范围（main）

| 阶段 | 功能 |
|------|------|
| Phase 0 / 1.5 | 获客引擎、西语试点、验收脚本 |
| Phase 1 | 工厂/订单/品类、ERP 桥接、员工后台 |
| Phase 2 | 客户门户、分享、目录/报价 R2、Apollo |
| Phase 3 | 大文件中转、Tus 断点续传、分享邮件通知 |
| Phase 4 | 印刷前稿 AI（条码 + OCR + ZBar + diff） |
| ERP | 字段映射 25+、订单 sync |
| Phase 5 | 大货实拍 AI（OpenCV + 人工终审） |

## VPS 部署

```bash
cd /opt/smart-crm
git pull origin main
bash scripts/upgrade.sh
bash scripts/final_acceptance.sh http://127.0.0.1:8000
bash scripts/prod_onboard.sh http://127.0.0.1:8000
# 配置 Key 后
bash scripts/prod_onboard.sh https://crm.domain.com --full
```

## 生产必配

- [ ] GitHub Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
- [ ] Tab2 API Keys（Exa / Firecrawl / OpenAI / 飞书）
- [ ] R2 凭据（目录 + 大文件）
- [ ] Resend（分享邮件，可选）
- [ ] TBCEXP ERP URL（可选）
- [ ] HTTPS + 备份 cron

详见 [PRODUCTION_READY.md](PRODUCTION_READY.md)。

## 导出交接报告

```bash
bash scripts/acceptance_report.sh http://127.0.0.1:8000
```
