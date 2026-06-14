# 生产就绪清单（Phase 0–5 代码完成）

> 路线图 **Phase 0 → Phase 5** 功能与验收脚本已全部合并 `main`。  
> 以下为 VPS + 真实 API Key 上线前检查项。

## 代码验收（本地 / Mock）

```bash
cd smart-crm && USE_SQLITE=1 uvicorn main:app --port 8000 &
bash scripts/ready.sh http://127.0.0.1:8000
bash scripts/go_live.sh http://127.0.0.1:8000
bash scripts/export_blockers.sh http://127.0.0.1:8000
```

期望：

| 项 | 标准 |
|----|------|
| pytest | 40/40 |
| smoke | 47+ |
| phase1–5 verify | 全部通过 |
| pre_merge_verify | 10/10 |

## VPS 首次部署

```bash
sudo bash scripts/bootstrap_vps.sh
cd /opt/smart-crm && bash scripts/upgrade.sh
bash scripts/vps_verify.sh http://127.0.0.1:8000
bash scripts/prod_onboard.sh http://127.0.0.1:8000
```

## 生产必配

- [ ] GitHub Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
- [ ] Tab2: Exa + Firecrawl + OpenAI + 飞书（≥4 Key → `production_ready`）
- [ ] R2: 目录 PDF + 大文件上传
- [ ] Resend（可选）: 分享链接邮件
- [ ] TBCEXP ERP URL（可选）
- [ ] HTTPS: `sudo bash scripts/setup_https.sh crm.domain.com`
- [ ] 备份 cron: `sudo bash scripts/setup_backup_cron.sh`

## 真实 Key 后全量验收

```bash
bash scripts/prod_onboard.sh https://crm.domain.com --full
bash scripts/pilot_live.sh https://crm.domain.com
bash scripts/acceptance_report.sh https://crm.domain.com report.md
```

## 阶段功能索引

| Phase | 文档 | 验收脚本 |
|-------|------|----------|
| 1.5 | IMPLEMENTATION_ROADMAP | `phase15_verify.sh` |
| 1 | PROJECT_STATUS | `phase1_verify.sh` / `phase1_live.sh` |
| 2 | PHASE2 内嵌于 README | `phase2_verify.sh` / `phase2_live.sh` |
| 3 | [PHASE3_FILES.md](PHASE3_FILES.md) | `phase3_verify.sh` / `phase3_live.sh` |
| 4 | [PHASE4_PREPRESS.md](PHASE4_PREPRESS.md) | `phase4_verify.sh` / `phase4_live.sh` |
| 5 | [PHASE5_PRODUCTION.md](PHASE5_PRODUCTION.md) | `phase5_verify.sh` / `phase5_live.sh` |

## API 版本

应用版本 **2.1.0** — Phase 0–5 + OCR/ZBar/Tus/ERP 字段映射。后续待 TBCEXP OpenAPI 微调。
