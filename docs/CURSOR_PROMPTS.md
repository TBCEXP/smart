# Cursor 提示词模板（复制即用）

在 Cursor 里改 SMART CRM 时，把下面提示词粘贴到对话框，并带上对应 **Skill** 名称（Cursor 会自动匹配）。

---

## 一、获客质量（Exa + Firecrawl）

### 优化墨西哥烘焙模具搜索
```
用 Exa 最佳实践优化 smart-crm：
- 国家 MX，城市 CDMX，L3 bakeware
- 检查 app/services/exa_utils.py 的语义 query 和 excludeDomains
- 更新 prompts.yaml 的西语 exa_query_templates
- 跑 scripts/smoke_test.sh 验证
```

### Firecrawl 抓不到客户网站
```
按 Firecrawl skill 排查 Track A 抓取：
- 检查 hospitality_es 的 firecrawl_paths
- 优化 app/services/clients.py FirecrawlClient 重试和 onlyMainContent
- 对 Vasconia / City Club 锚点 URL 试跑 Track B
- 把失败 URL 和修复方案写进注释
```

### 相似公司搜索命中率低
```
优化 Brainstorm Lab 的 similar_search_queries：
- 阅读 prompts.yaml similar_company_templates
- 为 MX 和 CO 各加 3 条 category:company 模板
- 确保 brainstorm actions similar_search 正确入队 Tab4
```

---

## 二、AI 话术（ai-sdk）

### 西语开发信质量差
```
按 ai-sdk 结构化输出规范改 prompts.yaml outreach.hospitality_es：
- LLM 必须返回 JSON：email_body, subject_lines, lead_score, whatsapp_intro
- 检查 pipeline.py parse_outreach_response 解析是否正确
- 用 mock 模式跑 1 条 MX lead 看字段是否写入 subject_lines 和 lead_score
```

### Brainstorm 卡片内容空洞
```
强化 Brainstorm Lab 的 brainstorm_system 提示词：
- keywords.es 必须 5-10 条可执行的 Exa 西语 query
- channel_plan 必须含 email/whatsapp/linkedin/tradeshow/customs 优先级
- action_plan 必须按周拆分
- 跑 POST /api/brainstorm/generate MX+CDMX+bakeware 验证 JSON 结构
```

---

## 三、验证与测试（verification + browser-automation）

### 改完代码全流程验收
```
用 verification 清单验收 SMART CRM：
1. 跑 bash scripts/smoke_test.sh
2. 对照 docs/VERIFICATION_CHECKLIST.md 的 A/B 节
3. 列出失败项并修复
4. 提交前确认 /api/integrations/status production_ready
```

### 浏览器测登录和 Tab
```
用 browser-automation 测试：
1. 打开 /admin，测 admin@example.com OTP 登录
2. 打开 / Tab6 Brainstorm，生成 MX 策略并入队
3. Tab1 跑 3 条获客，Tab3 看开发信和 WhatsApp
4. 截图或记录任何 UI 错误
```

---

## 四、API 测试（Postman）

### 导入 Postman 集合
```
阅读 postman/SMART_CRM.postman_collection.json，
说明如何在 Postman 里设置 {{base_url}} 和 {{session_token}}，
并跑通 Health → Brainstorm → Run → Batch 链路。
```

---

## 五、部署（deployments-cicd）

### Push 后网页没更新
```
按 docs/DEPLOYMENT.md 排查 GitHub Actions 部署：
- 检查 VPS_HOST / VPS_USER / VPS_SSH_KEY Secrets
- 看 upgrade.sh 是否 git pull + docker compose build 成功
- SSH 到 VPS 跑 bash scripts/preflight.sh 和 smoke_test.sh
```

### 升级回滚
```
VPS 升级失败需要回滚：
- git log 找上一版 commit
- 执行 upgrade.sh 前备份在 /var/lib/smart-crm/backups/
- 写清回滚命令到 docs/DEPLOYMENT.md
```

---

## 六、数据库（Supabase / Postgres）

### 线索表慢或 KB 搜不到
```
用 Supabase postgres-best-practices 检查：
- Lead 表 domain/country_iso/category_l3 索引
- embedding 字段写入率
- /api/kb/search 余弦相似度逻辑
- 若 VPS 内存 <2GB，评估 Postgres 迁 Neon/Supabase
```

---

## 七、第二期预告（暂不做，除非明确说「做第二期」）

### 工厂目录 + R2 存储
```
（第二期）用 shadcn + vercel-storage skill：
- 设计 /portal 客户目录浏览 UI
- 报价 PDF 存 Cloudflare R2
- 分享链接 /s/{token} 引擎
先只出设计文档，不写代码。
```

---

## 八、日常开发口诀

| 改什么 | 说什么 |
|--------|--------|
| 搜索/爬虫 | Exa + Firecrawl skill |
| 开发信/Brainstorm | ai-sdk skill |
| 改完提交前 | verification + `smoke_test.sh` |
| 测网页 | browser-automation |
| 测 API | Postman 集合 |
| 上线 | DEPLOYMENT.md + preflight.sh |
| 数据库 | Supabase postgres skill |
