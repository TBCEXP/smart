# Changelog

## v2.1.0 — 2026-06-14

路线图增量功能与生产验收加固（`main` @ `50b4b5c+`）。

### Added

- **Phase 3** Tus 断点续传（`PATCH/HEAD /api/files/tus/*`）
- **Phase 4** Tesseract OCR 标签提取
- **Phase 4** ZBar 条码图片识图
- **ERP** 深度字段映射（25 字段）+ `POST /api/bridge/tbcexp/orders/sync`
- **Scripts** `erp_verify.sh`、`prod_readiness_check.sh`
- **Smoke** tus / field-map / ocr / zbar 状态检查（47+ 项）
- **CI** erp_verify 步骤

### Fixed

- `VERSION` vs `IMAGE_TAG` 分离（部署 smoke v2.0.x 检查）
- Tus `HEAD` 响应 `Upload-Offset` 头
- OpenCV / Tesseract / libzbar Docker 运行时依赖

### Added (onboard)

- `go_live.sh` — 代码终检三连（release + erp + final）
- `release_check.sh` — v2.1.0 发布完整性
- `docs/VPS_ONBOARDING.md`、`docs/HANDOFF.md`
- 应用版本号统一 **2.1.0**
- Postman ERP + v2.1 端点

### Added (deploy pipeline)

- `deploy_verify.sh` — VPS/CI 部署后快速验收（phase15 quick + phase3–5 + erp）
- `upgrade.sh` / GitHub Actions 部署后自动跑 `deploy_verify`
- `release_check.sh --skip-pytest` — CI 复用发布检查

### Fixed (handoff)

- `release_check.sh` pytest 计数解析（动态 collect-only 预期值）

### Tests

- pytest **39/39**
- pre_merge_verify **10/10**

---

## v2.0.0 — 2026-06-14

路线图 Phase 0–5 MVP 生产就绪包。

### Phases

| Phase | 功能 |
|-------|------|
| 0 | Docker、Nginx、CI/CD、备份 |
| 1.5 | MX/CO 试点、里程碑、KB、Track C |
| 1 | 工厂/订单/品类、ERP 桥接 Mock |
| 2 | R2 目录、客户门户、分享 |
| 3 | 大文件元数据、分享邮件通知 |
| 4 | 条码 + 文本/图形 diff 规则引擎 |
| 5 | OpenCV 对齐、人工终审 |

### Scripts

- `final_acceptance.sh`、`pre_merge_verify.sh`
- `phase1`–`phase5` verify + live
- `prod_onboard.sh --full`

---

## 生产部署

```bash
sudo bash scripts/bootstrap_vps.sh
bash scripts/upgrade.sh
bash scripts/final_acceptance.sh http://127.0.0.1:8000
bash scripts/prod_onboard.sh https://crm.yourdomain.com --full
```

详见 [PRODUCTION_READY.md](docs/PRODUCTION_READY.md)。
