# 飞书多维表格字段映射

> 与 `smart-crm/app/services/feishu_client.py` 中 `_lead_fields()` 保持一致。  
> Tab2「飞书写入测试」失败时，对照本表检查列名与类型。

## 必填字段（10 项，PDF §3.2）

| 飞书列名 | 类型建议 | 来源字段 | 说明 |
|----------|----------|----------|------|
| 公司名称 | 文本 | `lead.company_name` | |
| 网站 URL | 文本/链接 | `lead.website_url` | |
| 行业分类 | 单选/文本 | `lead.industry` | 默认「跨境电商」 |
| 搜索关键词 | 文本 | `lead.keyword` | |
| Exa 搜索结果摘要 | 多行文本 | `lead.exa_summary` | ≤8000 字 |
| Firecrawl 分析摘要 | 多行文本 | `lead.firecrawl_summary` | ≤8000 字 |
| 个性化开发信 | 多行文本 | `lead.outreach_email` | ≤8000 字 |
| 状态 | 单选 | `lead.status` | 如「待联系」 |
| 备注 | 文本 | track + channel | 自动生成 |
| 创建时间 | 日期/时间戳 | Unix ms | 自动写入 |

## 扩展字段（`extended_feishu_fields=true` 时）

| 飞书列名 | 来源 | 说明 |
|----------|------|------|
| 线索评分 | `lead.lead_score` | A/B/C |
| 主题行 | `lead.subject_lines` | |
| 批次 ID | `batch_id` | |
| 处理状态 | 固定「成功」 | |
| 产品品类 L3 | `lead.category_l3` | 如 bakeware |
| 语言 | `lead.language` | es/en/pt |
| 国家 | `lead.country_iso` | MX/CO |
| 首选渠道 | `lead.preferred_channel` | email/whatsapp |

## Tab2 配置项

| 配置键 | 说明 |
|--------|------|
| `feishu_app_id` | 飞书应用 App ID |
| `feishu_app_secret` | 飞书应用 Secret |
| `feishu_base_token` | 多维表格 app_token（URL 中 `base/` 后一段） |
| `feishu_table_id` | 数据表 table_id |

## 验收步骤

1. 飞书开放平台创建企业自建应用，开通「多维表格」权限
2. 创建多维表格，列名与上表**完全一致**（中文）
3. Tab2 填写四项飞书配置
4. `/admin` 登录 → Tab2「飞书写入测试」
5. 确认表中出现测试行且字段非空
6. Tab3 确认入库 → `feishu_record_id` 非空

## 常见错误

| 错误 | 处理 |
|------|------|
| `Feishu write returned empty record_id` | 检查 app 是否已发布、表格是否授权给应用 |
| 字段名不匹配 | 列名必须中文完全一致，区分全角/半角 |
| 401 confirm | 先 `/admin` 登录获取 session |
| Mock 模式无写入 | Tab2 配置 `feishu_app_id` 等四项 |
