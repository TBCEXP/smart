# SMART CRM 实施路线图（科学分期）

> 本文档综合《B2B 智能获客面板》PDF v1.1、§0A–§0G 扩展规划、以及当前代码现状，  
> 用于 **先复盘、再分期、后执行** — 避免跳步堆功能。

---

## 一、总体架构（冻结，不再改方向）

```
┌─────────────────────────────────────────────────────────────┐
│  Nginx (443) + 邮箱登录网关                                   │
├─────────────────────────────────────────────────────────────┤
│  smart-crm :8000（获客引擎，PDF §1–§13 基座 + §0G 扩展）        │
│    Tab1–4 原有 │ Tab5 市场情报 │ Tab6 Brainstorm │ Tab7 海关   │
├─────────────────────────────────────────────────────────────┤
│  扩展门户（第二期起，独立模块，不推翻获客链路）                    │
│    /admin 员工 │ /portal 客户 │ /s/{token} 分享链接            │
├─────────────────────────────────────────────────────────────┤
│  数据层                                                       │
│    PostgreSQL + pgvector（线索 KB）│ 飞书（销售协作）│ TBCEXP ERP │
│    对象存储 R2/B2（目录/报价/大文件，不进 VPS 盘）               │
└─────────────────────────────────────────────────────────────┘
```

**原则：**
1. smart-crm = 找新客户；飞书 = 跟进线索；ERP = 成交客户与订单
2. 先进一国、先 Track B 再 Track A（墨西哥 → 哥伦比亚西语试点）
3. 每阶段有 **验收门槛**，不达标不进入下一阶段

---

## 二、当前代码诚实评估（PR #2 之后）

| 项目 | 规划要求 | 当前状态 | 风险 |
|------|----------|----------|------|
| 获客主链路 Exa→Firecrawl→LLM | PDF §2.1 完整 | 框架有，**无 API Key 时走 Mock** | 未在真实环境验质量 |
| 飞书自动入库 | PDF 必填 10 字段 | **已实现** `feishu_client.py`；未配置时 mock 确认 | 需真实表字段对齐 |
| pgvector 语义检索 | §0A 知识库 | **Postgres 原生 pgvector** + SQLite JSON 回退 | 需 OpenAI Key 做语义召回 |
| TBCEXP 桥接 | 可选 | **`tbcexp_client.py` + bridge API**；未配置时 Mock | 需真实 ERP URL |
| 邮箱登录 | §2.2 + 双门户 | OTP/Link + **鉴权中间件**保护敏感 POST | GET 接口仍公开 |
| Brainstorm Lab | §0G Tab6 | 已实现 | 依赖 Mock LLM 时策略质量未知 |
| Track B/C、展会、地理队列 | §0E/§0G | 已实现 + 验收脚本 | 需真实 API 验证 |
| Tab9 试点看板 + WhatsApp 触达 | 1.5.5 | **已实现** API + UI + `outreach_pilot.sh` | 人工发送 WhatsApp |
| RackNerd 实机部署 | §0C Docker+Nginx | 脚本齐全 + CI，`bootstrap_vps.sh` | **未在 VPS 跑通** |
| 每日备份 | 0.7 | `scripts/backup_daily.sh` | 需配置 cron |
| 工厂目录/报价/大文件 | 第二期–第三期 | **Phase 2/3/4 已落地**；大货实拍 AI 未开始 |

**结论：** 功能骨架与 1.5 验收脚本已齐，**不等于生产验收通过**。  
科学做法：第零期 VPS 部署 + 真实 API Key → 跑 1.5 验收脚本 → 再进第一期门户。

---

## 三、科学分期与验收门槛

### 第零期 — 基础设施 + 安全（必须先完成）

| 步骤 | 内容 | 验收标准 |
|------|------|----------|
| 0.1 | VPS 体检：`df -h` `free -h` `docker system df` | 确认 ≥2GB RAM；磁盘 ≥40GB 或对象存储方案 |
| 0.2 | `/opt/smart-crm` + `/var/lib/smart-crm` 实机部署 | `curl /api/health` 200；容器 `restart unless-stopped` |
| 0.3 | Nginx 反代 + `proxy_buffering off`（SSE） | 外网 HTTPS 可访问；8000 不暴露公网 |
| 0.4 | 登录网关：**管理 API 需 Session** | 无 token 访问 `/api/config` 返回 401 |
| 0.5 | Tab2 配置真实 API Key | Exa/Firecrawl/OpenAI/飞书 全部非 Mock |
| 0.6 | **飞书写入** 10 必填字段 + 扩展字段 | review 确认后飞书表出现 1 条真实线索 |
| 0.7 | 备份脚本每日 tar `var/lib/smart-crm` | 升级前强制备份可恢复 |

**本阶段不做：** Brainstorm 批量跑、18 国定时队列、ImportGenius 付费、门户目录。

---

### 第 1.5 期 — 西语双线获客试点（第零期通过后）

| 步骤 | 内容 | 验收标准 |
|------|------|----------|
| 1.5.1 | 仅 **墨西哥 MX**：Track B 采集 Vasconia + 1 分销 | 产出 1 份 `MarketProductIntel` 报告 |
| 1.5.2 | Brainstorm：CDMX × 烘焙模具 | 5 张策略卡片；人工认可关键词 |
| 1.5.3 | Track A：Top 3 L3 × CDMX/Monterrey，**每任务 5 条** | 西语开发信质量可发；`review` 模式 |
| 1.5.4 | 哥伦比亚 CO 重复 B→Brainstorm→A | 累计 ≥30 条 A 级线索进飞书 |
| 1.5.5 | WhatsApp 话术人工发送 ≥5 家 | 记录回复率（不自动群发） |
| 1.5.6 | Track C：手工 CSV 50 条试跑（不买 Panjiva） | 域名匹配率 >60% |
| 1.5.7 | pgvector：线索摘要 embedding + 语义检索 API | 「哥伦比亚 烘焙模具 分销商」能召回 |

**本阶段不做：** 美洲 T2–T4 全国、欧洲 Macro2、Apollo 企业版。

---

### 第一期 — 员工业务基础

- 客户/线索查询（飞书 + ERP 只读）
- 工厂主数据、三级品类树维护 UI
- 订单主表 + 货号子表（无 AI）
- 角色权限：业务员只看自己的客户

**前置：** TBCEXP API 或脱敏 Excel 样例字段冻结。

---

### 第二期 — 工厂目录 + 报价分发

- 多工厂 PDF 目录、客户授权矩阵
- `/portal` 登录浏览 + `/s/{token}` 分享
- 对象存储（R2），不进 VPS

---

### 第三期 — 大文件中转 ✅（已落地）

- 复用分享引擎 + R2 预签名上传 + 邮件通知（Resend / log 回退）
- 验收：`bash scripts/phase3_verify.sh`

---

### 第四期 — 印刷前稿 AI ✅（已落地 MVP）

- 条码引擎（EAN-13 / Code128）+ 文本 diff + Pillow 图形 diff
- 规则引擎综合判定（非 LLM 一票否决）
- 验收：`bash scripts/phase4_verify.sh`

---

### 第五期 — 大货实拍 AI

- OpenCV 对齐 + 与确稿找不同 + 人工终审

---

## 四、获客方法使用顺序（§0G 矩阵落地）

按 **证据强度 × 成本** 递进，不要一上来全开：

```
L0  UN Comtrade 筛国（免费，Brainstorm 输入）
      ↓
L1  Exa 语义搜 + Firecrawl（smart-crm 主力，Track A）
      ↓ 并行
L1b Track B 锚点产品情报 → 指导 L3 优先级
      ↓
L1c Brainstorm Lab → 关键词/渠道/种子 → 入队
      ↓
L2  展会名单 Firecrawl（ANTAD / HD Expo）
      ↓
L3  海关 CSV 导入 Track C（验证后再考虑 ImportGenius 月费）
      ↓
L4  Apollo 补邮箱（按需单条，非批量扫）
      ↓
触达 邮件(西语) → WhatsApp 手动 → LinkedIn 人工
```

---

## 五、资源与成本约束

| 资源 | 建议 |
|------|------|
| VPS 1–2GB | 仅 smart-crm + Nginx；Postgres 用 Neon/Supabase 免费层 |
| VPS 4GB+ | 本地 Postgres/pgvector |
| Exa/Firecrawl/OpenAI | 试点期每任务 **5 条**，并发 **3** |
| 大文件/目录 | **必须** Cloudflare R2（10GB 免费） |
| ImportGenius/Apollo | 月收入验证后再开；先 CSV 免费试点 |

---

## 六、立即执行清单（第零期代码补齐）

当前分支 `main` 下一步可做（1.5 生产验收前）：

1. ✅ 本路线图文档
2. ✅ `feishu_client.py` — 真实写入 10+ 扩展字段（含首选渠道、L3、国家）
3. ✅ Pipeline `confirm` / `auto` 模式对接飞书
4. ✅ Auth 中间件保护 `/api/config`、`/api/confirm` 等管理接口
5. ✅ `scripts/preflight.sh` — 部署前检查清单
6. ✅ embedding 写入 + `GET /api/kb/search` 语义检索（1.5.7 提前打底）
7. ✅ Phase 1.5 MX 试点向导 — `POST /api/pilot/mx/start` + Tab5 UI + `scripts/mx_pilot.sh`
8. ✅ Exa L3 西语模板 + `resolve_exa_query` + Tab1 查询预览
9. ✅ `scripts/latam_full_pilot.sh` — MX+CO 联合验收
10. ✅ Phase 1 起步 — `GET /api/leads` + `/admin/dashboard` 员工线索查询
11. ✅ 工厂主数据 + 订单主表/货号子表 API（待 ERP 对接）
12. ✅ 三级品类树 `GET /api/catalog/tree`

**用户需配合（阻塞项）：**
- [ ] RackNerd `df -h` / `free -h` 输出
- [ ] 域名 + DNS 指向 VPS
- [ ] Exa / Firecrawl / OpenAI / 飞书 凭据
- [ ] TBCEXP ERP URL（可选）
- [ ] 是否可访问 `TBCEXP/ERP` 私有仓库（对照 PDF 原版）

---

## 七、与上期实现的差异说明

上期一次性实现了 Tab1–7 全部 UI 和数据模型，**跳过了第零期验收**。  
本期按本路线图 **回填生产必需项**，而不是继续堆新模块。

确认第零期验收通过后，回复「**继续 1.5 期墨西哥试点**」进入下一执行波次。
