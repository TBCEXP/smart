# PR 合并清单

> 分支 `cursor/phase3-files-notify-c2f3` → `main`（[PR #4](https://github.com/TBCEXP/smart/pull/4)）

## 合并前自动验收

```bash
cd smart-crm && USE_SQLITE=1 uvicorn main:app --port 8000 &
bash scripts/pre_merge_verify.sh http://127.0.0.1:8000
```

期望：**pytest 21/21 · smoke 41/41 · phase1 7/7 · phase2 8/8 · phase3 7/7**

## 本分支包含

| 阶段 | 功能 |
|------|------|
| Phase 1.5 | Exa 西语模板、MX/CO 试点、验收脚本 |
| Phase 1 | 工厂/订单/品类、ERP 桥接、员工后台、角色过滤 |
| Phase 2 | 客户门户、分享链接、目录/报价 R2、Apollo |
| **Phase 3** | 大文件元数据、R2 上传 URL、分享邮件通知 |

## 合并后 VPS 操作

```bash
cd /opt/smart-crm
git pull origin main
bash scripts/upgrade.sh
bash scripts/phase3_verify.sh http://127.0.0.1:8000
bash scripts/prod_onboard.sh http://127.0.0.1:8000
# 配置 Key 后
bash scripts/prod_onboard.sh https://crm.domain.com --full
```

## 合并后仍需用户配置

- [ ] GitHub Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
- [ ] Tab2 API Keys（Exa / Firecrawl / OpenAI / 飞书）
- [ ] R2 凭据（目录 PDF + 大文件真实上传）
- [ ] Resend API Key（分享链接邮件实发，可选）
- [ ] TBCEXP ERP URL + 字段对齐
- [ ] HTTPS: `sudo bash scripts/setup_https.sh crm.domain.com`

## 导出交接报告

```bash
bash scripts/acceptance_report.sh http://127.0.0.1:8000
# 生成 pilot-report-*.md + pilot-report-*-handoff.md
```
