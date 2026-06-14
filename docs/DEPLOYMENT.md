# SMART CRM 更新与发布指南

> 目标：在 Cursor 里改好代码 → **推送到 GitHub → VPS 网页自动更新**，  
> 且 **不碰** `/var/lib/smart-crm/` 里的配置、线索、数据库。

---

## 一、推荐方案：GitHub + 自动部署（首选）

```
┌─────────────┐    git push     ┌──────────────┐    SSH 执行      ┌─────────────┐
│ Cursor 改代码 │ ──────────────► │ GitHub 仓库   │ ───────────────► │ RackNerd VPS │
│ 本地/云端    │                 │ TBCEXP/smart  │   upgrade.sh    │ 网页立即更新  │
└─────────────┘                 └──────────────┘                  └─────────────┘
```

| 角色 | 路径 | 更新时 |
|------|------|--------|
| **程序**（可替换） | `/opt/smart-crm/` | `git pull` + 重建 Docker 镜像 |
| **数据**（永久保留） | `/var/lib/smart-crm/` | **永远不覆盖** |

这是你们规划里 §0C「程序与数据分离」的标准做法。

---

## 二、三种发布方式对比

| 方式 | 操作 | 速度 | 适合 |
|------|------|------|------|
| **A. GitHub Actions 自动部署** | Cursor 改完 → Push → 等 1–3 分钟 | 最快、最省心 | **日常推荐** |
| **B. VPS 上一键升级** | SSH 登录 → `bash scripts/upgrade.sh` | 约 1 分钟 | 自动部署失败时备用 |
| **C. 纯手动** | FTP/SCP 上传文件 | 慢、易漏文件 | **不推荐** |

**不要用 FTP 直接传网页文件** — 你们是 Docker + Python 后端，必须重建镜像或 `git pull` 整仓库。

---

## 三、一次性配置（只需做一次）

### 3.1 VPS 首次克隆仓库

```bash
sudo mkdir -p /opt/smart-crm /var/lib/smart-crm
sudo git clone https://github.com/TBCEXP/smart.git /opt/smart-crm
cd /opt/smart-crm
sudo git checkout main   # 或你的发布分支

# 首次安装
sudo bash scripts/install.sh
sudo bash scripts/preflight.sh
```

### 3.2 配置 HTTPS（生产必做）

```bash
sudo apt install certbot python3-certbot-nginx -y
# 先把 nginx/crm.conf 里 server_name 改成你的域名
sudo certbot --nginx -d crm.yourdomain.com
```

### 3.3 GitHub Actions 自动部署（推荐）

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 添加：

| Secret 名称 | 内容 |
|-------------|------|
| `VPS_HOST` | RackNerd VPS IP 或域名 |
| `VPS_USER` | SSH 用户名（如 `root`） |
| `VPS_SSH_KEY` | 私钥全文（`-----BEGIN OPENSSH PRIVATE KEY-----` …） |

在 VPS 上生成部署专用密钥：

```bash
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/github_deploy   # 复制到 GitHub Secret VPS_SSH_KEY
```

配置完成后：**每次 push 到 `main` 分支**，GitHub 会自动 SSH 到 VPS 执行 `scripts/upgrade.sh`。

### 3.4 可选：只手动发布、不自动

若暂时不想开自动部署，可关闭 workflow，改用：

```bash
ssh your-user@your-vps
cd /opt/smart-crm && sudo bash scripts/upgrade.sh
```

---

## 四、日常更新流程（你以后怎么用）

### 在 Cursor 里改代码

1. 改 `smart-crm/` 下代码
2. 本地自测（可选）：`cd smart-crm && uvicorn main:app --reload`
3. 提交并推送：

```bash
git add .
git commit -m "描述你改了什么"
git push origin main
```

4. 若已配置 GitHub Actions：等 1–3 分钟，打开 `https://crm.yourdomain.com/api/health` 确认
5. 在 GitHub **Actions** 页查看部署日志；失败则用方式 B 手动升级

### 发版打标签（大版本）

```bash
git tag v2.0.0
git push origin v2.0.0
```

VPS 会按 tag 部署，便于回滚对照。当前路线图 MVP 版本为 **2.0.0**。

### 部署后终验收

```bash
bash scripts/final_acceptance.sh https://crm.yourdomain.com
bash scripts/acceptance_report.sh https://crm.yourdomain.com
```

详见 [PRODUCTION_READY.md](PRODUCTION_READY.md)。

---

## 五、升级时到底发生了什么？

`scripts/upgrade.sh` 自动执行：

1. **备份** `/var/lib/smart-crm/` → `backups/pre-upgrade-日期.tar.gz`
2. **`git pull`** 拉最新程序（不动数据目录）
3. **`docker compose build smart-crm`** 重建镜像
4. **`docker compose up -d smart-crm`** 滚动重启（数据卷挂载不变）
5. **`curl /api/health`** 健康检查

**不会丢失：** API Key 配置、线索批次、PostgreSQL 数据、登录白名单。

---

## 六、回滚（升级出问题）

```bash
cd /opt/smart-crm
git log --oneline -5          # 找到上一版 commit
git checkout <上一版commit>
sudo bash scripts/upgrade.sh

# 若数据损坏，从备份恢复：
sudo tar xzf /var/lib/smart-crm/backups/pre-upgrade-XXXX.tar.gz -C /
```

---

## 七、和其他平台对接？

| 平台 | 是否推荐 | 说明 |
|------|----------|------|
| **GitHub** | ✅ 首选 | 代码版本 + Actions 自动部署 |
| **Vercel / Netlify** | ❌ | 只适合静态站；你们是 FastAPI + 定时任务 + SSE |
| **Railway / Render** | ⚠️ 可以但贵 | 能跑 Docker，但不如自己 VPS 可控 |
| **Docker Hub** | 可选进阶 | CI 构建镜像推 Hub，VPS `docker pull`；单机不必强求 |

你们已有 RackNerd VPS + Docker，**GitHub → SSH → upgrade.sh** 是最简单、最贴合现状的方案。

---

## 八、每日数据备份（第零期 0.7）

数据目录 `/var/lib/smart-crm` 含数据库、配置、OTP 日志，**升级脚本不会覆盖**，但需防磁盘故障：

```bash
# 手动备份
sudo bash /opt/smart-crm/scripts/backup_daily.sh

# 每日 03:00 自动备份（cron）
sudo crontab -e
# 添加:
0 3 * * * /opt/smart-crm/scripts/backup_daily.sh >> /var/log/smart-crm-backup.log 2>&1
```

备份文件默认保存在 `/var/backups/smart-crm/`，保留 14 天（`KEEP_DAYS` 可改）。

---

## 九、分支建议

| 分支 | 用途 |
|------|------|
| `main` | 生产环境，push 即部署 |
| `cursor/*` | Cursor 开发分支，合并到 main 后再上线 |
| `v*` tag | 里程碑版本，便于回滚 |

**不要直接在 VPS 上改代码** — 改完重启就丢，且无法版本管理。

---

## 十、检查清单

- [ ] VPS 已 `git clone` 到 `/opt/smart-crm`
- [ ] 数据在 `/var/lib/smart-crm/`，与程序分离
- [ ] GitHub Secrets 已配置（VPS_HOST / VPS_USER / VPS_SSH_KEY）
- [ ] push 到 main 后 Actions 显示绿色 ✓
- [ ] `https://你的域名/api/health` 返回 `{"status":"ok"}`
- [ ] `bash scripts/vps_verify.sh https://你的域名` 验收通过
- [ ] Tab2 配置 API Key 后 `POST /api/integrations/probe` 四项 live 通过
- [ ] `sudo bash scripts/backup_daily.sh` 可生成 tar 备份

完成以上后，你以后在 Cursor 改软件 → **Push 一下就能更新网页**。
