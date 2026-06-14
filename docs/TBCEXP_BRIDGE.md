# TBCEXP ERP 桥接说明

> Phase 1 推送接口 · 待真实 ERP 字段冻结后对齐

## 配置（Tab2）

| 配置项 | 说明 |
|--------|------|
| `tbcexp_api_url` | ERP 根 URL，如 `https://erp.example.com` |
| `tbcexp_api_token` | Bearer Token |

## 推送端点

SMART CRM 调用：

```
POST {tbcexp_api_url}/api/external/leads
Authorization: Bearer {tbcexp_api_token}
Content-Type: application/json
```

面板触发：`POST /api/bridge/tbcexp/{lead_id}`（需员工登录）

## 请求体字段

| 字段 | 类型 | 来源 |
|------|------|------|
| `source` | string | 固定 `smart_crm` |
| `sourceType` | string | 固定 `smart_crm` |
| `external_id` | string | `lead.id` |
| `company_name` | string | `lead.company_name` |
| `website_url` | string | `lead.website_url` |
| `domain` | string | `lead.domain` |
| `country_iso` | string | `lead.country_iso` |
| `city` | string | `lead.city` |
| `category_l3` | string | `lead.category_l3` |
| `lead_score` | string | A/B/C |
| `status` | string | 如「待联系」 |
| `assigned_to` | string | 业务员邮箱 |
| `feishu_record_id` | string | 飞书同步 ID |
| `preferred_channel` | string | email/whatsapp |
| `language` | string | es/en/pt |
| `keyword` | string | Exa 搜索词 |
| `notes` | string | Firecrawl 摘要前 500 字 |

## 期望响应（建议）

```json
{
  "id": "erp-customer-uuid",
  "external_id": "smart-crm-lead-uuid",
  "status": "created"
}
```

SMART CRM 将 `id` 或 `external_id` 记入同步结果；成功时设置 `lead.tbcexp_synced = true`。

## Mock 模式

未配置 URL/Token 时返回：

```json
{
  "mode": "mock",
  "status": "ok",
  "external_id": "mock-erp-xxxxxxxx"
}
```

## 订单只读拉取（Phase 1+）

员工后台「拉取 ERP 订单」调用：

```
GET {tbcexp_api_url}/api/external/orders?limit=20
Authorization: Bearer {tbcexp_api_token}
```

SMART CRM 封装：`GET /api/bridge/tbcexp/orders`（需 admin session）

未配置时返回 2 条演示订单（`mode: mock`）。

## 健康检查

`POST /api/integrations/probe` 含 TBCEXP 探测：`GET {url}/api/health`

## ERP 侧待确认

- [ ] 真实路径是否为 `/api/external/leads`
- [ ] 客户主表 vs 线索表映射
- [ ] 重复 domain 去重策略
- [ ] 订单回写 SMART CRM 的 webhook（Phase 1+）

提供脱敏 Excel 或 OpenAPI 后，可更新 `tbcexp_client.py` 字段映射。
