# SMART CRM 生产上线指南

> 从零到 Phase 1.5 验收的完整操作手册。配合 `scripts/prod_onboard.sh` 使用。

---

## 一、准备清单（上线前）

| 项目 | 要求 | 获取方式 |
|------|------|----------|
| RackNerd VPS | ≥2GB RAM，≥40GB 磁盘 | 已有 |
| 域名 | `crm.yourdomain.com` A 记录 → VPS IP | DNS 面板 |
| Exa API Key | 语义搜索 | https://exa.ai |
| Firecrawl API Key | 网站分析 | https://firecrawl.dev |
| OpenAI API Key | 开发信 / Brainstorm / embedding | https://platform.openai.com |
| 飞书应用 | app_id + secret + 多维表格 token | 飞书开放平台 |
| GitHub Secrets | VPS_HOST / VPS_USER / VPS_SSH_KEY | 自动部署 |

---

## 二、一键安装（VPS 首次）

```bash
# SSH 登录 VPS 后
sudo bash scripts/bootstrap_vps.sh
# 或远程拉取:
# curl -fsSL https://raw.githubusercontent.com/TBCEXP/smart/main/scripts/bootstrap_vps.sh | sudo bash
```

安装完成后访问 `http://VPS_IP:8000`，默认账号 `admin@example.com`（OTP 写入 `/var/lib/smart-crm/smart-crm-data/auth_emails.log`）。

---

## 三、配置 API Key（Tab2）

1. `/admin` 登录
2. Tab2 填写四项 Key + 飞书表格信息
3. 点击「检测连通性」→ 期望 4/4 live
4. 点击「飞书写入测试」→ 飞书表出现测试行

---

## 四、验收命令

```bash
# 一站式就绪（推荐）
bash scripts/ready.sh http://127.0.0.1:8000

# 生产待办清单
bash scripts/onboard_checklist.sh http://127.0.0.1:8000

# 快速验收（Mock 或生产均可）
bash scripts/prod_onboard.sh http://127.0.0.1:8000

# 配置 Key 后全量验收
bash scripts/prod_onboard.sh http://127.0.0.1:8000 --full
bash scripts/go_live.sh http://127.0.0.1:8000

# 分项脚本
bash scripts/deploy_preflight.sh
bash scripts/deploy_verify.sh http://127.0.0.1:8000
bash scripts/vps_verify.sh http://127.0.0.1:8000
bash scripts/phase15_verify.sh http://127.0.0.1:8000
bash scripts/pre_merge_verify.sh http://127.0.0.1:8000
bash scripts/pilot_live.sh http://127.0.0.1:8000        # MX
bash scripts/pilot_live.sh http://127.0.0.1:8000 --co   # CO
bash scripts/status.sh http://127.0.0.1:8000
bash scripts/acceptance_report.sh http://127.0.0.1:8000
```

---

## 五、Phase 1 员工业务

1. `/admin` 登录 → `/admin/dashboard`
2. 验证线索 / 工厂 / 订单 / 工厂目录 Tab
3. `bash scripts/phase1_live.sh` — OTP 创建订单 + 分享 + 确认

## 六、Phase 2 门户 / 报价

1. `/portal` 登录 `customer@example.com`
2. 授权目录 + 报价单 Tab
3. `bash scripts/phase2_live.sh`
4. R2 配置后: `bash scripts/upload_catalog_r2.sh BASE DOC_ID file.pdf TOKEN`

---

## 七、HTTPS

```bash
sudo bash scripts/setup_https.sh crm.yourdomain.com
# 修改 .env 中 APP_BASE_URL=https://crm.yourdomain.com
cd /opt/smart-crm && docker compose up -d smart-crm
```

---

## 八、GitHub 自动部署

1. VPS 生成部署密钥并加入 `authorized_keys`
2. GitHub → Settings → Secrets → Actions 添加三个 Secret
3. `git push origin main` → Actions 自动 `upgrade.sh` + 验收

---

## 九、Phase 1.5 里程碑

| 步骤 | 脚本 / 操作 | 达标标准 |
|------|-------------|----------|
| 1.5.1–1.5.3 | `pilot_live.sh` / Tab5 MX | Track B + Brainstorm + 入队 |
| 1.5.4 | `pilot_live.sh --co` | CO 试点启动 |
| 1.5.5 | Tab3「记录 WhatsApp」/ `outreach_pilot.sh` | ≥5 条触达记录 |
| 1.5.6 | `trackc_pilot.sh 50 --no-website` | 50 条 CSV，匹配率 >60% |
| 1.5.7 | Tab9 KB 搜索 / `kb_pilot.sh` | 语义召回有结果 |
| 1.5.4 飞书 | Tab3 confirm 入库 | 累计 ≥30 条 feishu_record_id |

查看进度：`bash scripts/status.sh` 或 Tab9 试点看板。

---

## 十、运维

```bash
# 每日备份（cron 03:00）
sudo bash scripts/setup_backup_cron.sh   # 安装 cron
sudo bash scripts/backup_daily.sh        # 手动测试

# 手动升级
cd /opt/smart-crm && sudo bash scripts/upgrade.sh

# 日志
docker compose -f /opt/smart-crm/docker-compose.yml logs smart-crm --tail 100
```

---

## 十一、故障排查

| 症状 | 处理 |
|------|------|
| Mock 数据 | Tab2 检查 Key；`POST /api/integrations/probe` |
| 401 写配置 | `/admin` 登录获取 session_token |
| 飞书写入空 ID | 检查表格字段名与 app 权限 |
| 批次卡住 | `docker compose logs`；检查 SSE / SQLite 并发 |
| 部署后验收失败 | SSH 手动 `bash scripts/phase15_verify.sh --quick` |
